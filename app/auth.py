"""User authentication: password hashing, login sessions, and the
dependency that tells a route which user is making the request (Issue #44).

How a login works:
  1. POST /auth/register or /auth/login checks the email and password and
     calls create_session(), which returns a random session token.
  2. The client sends that token on every later request as
     `Authorization: Bearer <token>`.
  3. get_current_user() hashes the token, finds the matching unexpired
     session row, and returns its User. Anything else is a 401.

Session tokens are stored only as SHA-256 hashes (see UserSession in
app/models.py). A fast hash is fine here, unlike for passwords: the token is
32 random bytes, so there's nothing to guess, whereas a human-chosen
password needs Argon2id's deliberate slowness to resist guessing.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserSession

SESSION_LIFETIME = timedelta(days=7)

# Argon2id with pwdlib's recommended settings.
_password_hasher = PasswordHash.recommended()

# Checked against when a login names an email with no account, so that
# request takes as long as a wrong password for a real account. Without it,
# a fast "no such user" response would reveal which emails have accounts.
_DUMMY_PASSWORD_HASH = _password_hasher.hash(secrets.token_urlsafe(32))

# auto_error=False: handle a missing header ourselves so it is reported as
# 401, the same status used for a bad token, instead of HTTPBearer's
# default 403 for a missing Authorization header.
_bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _password_hasher.verify(password, password_hash)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def authenticate(db: Session, email: str, password: str) -> User | None:
    """Return the User if email and password match, otherwise None.

    email must already be normalized (trimmed and lowercased), which the
    request schemas in app/schemas.py do.
    """
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None:
        verify_password(password, _DUMMY_PASSWORD_HASH)
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def create_session(db: Session, user: User) -> str:
    """Start a session for user and return its token.

    The token is returned exactly once, here. Only its hash is saved.
    """
    token = secrets.token_urlsafe(32)
    db.add(
        UserSession(
            user_id=user.id,
            token_hash=_hash_token(token),
            expires_at=datetime.now(UTC) + SESSION_LIFETIME,
        )
    )
    db.commit()
    return token


def get_current_session(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> UserSession:
    """FastAPI dependency: the session behind the request's bearer token,
    or a 401 if the token is missing, unknown, or expired."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not logged in, or the session has expired",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    session = db.execute(
        select(UserSession).where(UserSession.token_hash == _hash_token(credentials.credentials))
    ).scalar_one_or_none()
    if session is None or session.expires_at <= datetime.now(UTC):
        raise unauthorized
    return session


def get_current_user(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency: the logged-in User making this request.

    Use as a parameter (`user: User = Depends(get_current_user)`) on any
    route that reads or changes a user's data.
    """
    return db.get(User, session.user_id)
