"""Set a new password for an existing account (Issue #44).

The main use is giving demo@example.com a real password after the users
migration, since that migration gives it a password nobody knows. Run it
from the repository root, with DATABASE_URL pointing at the database to
change (see docs/development.md):

    python -m scripts.set_password

It asks for the email and the new password. The password is read with
getpass, so it is never shown on screen, passed on the command line, or
saved in shell history. Every existing session for the account is ended,
so old logins have to sign in again with the new password.
"""

import sys
from getpass import getpass

from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.database import SessionLocal
from app.models import User, UserSession
from app.schemas import RegisterRequest


class SetPasswordError(Exception):
    """A problem the person running the script needs to fix."""


def set_password(db: Session, email: str, password: str) -> None:
    """Replace the password of the account with this email and end its
    sessions. Uses the same email and password rules as sign-up."""
    try:
        valid = RegisterRequest(email=email, password=password)
    except ValidationError as exc:
        problems = "; ".join(f"{error['loc'][0]}: {error['msg']}" for error in exc.errors())
        raise SetPasswordError(problems) from exc

    user = db.execute(select(User).where(User.email == valid.email)).scalar_one_or_none()
    if user is None:
        raise SetPasswordError(f"No account with email {valid.email}")

    user.password_hash = hash_password(valid.password)
    db.execute(delete(UserSession).where(UserSession.user_id == user.id))
    db.commit()


def main() -> int:
    email = input("Email: ")
    password = getpass("New password: ")
    if getpass("Repeat new password: ") != password:
        print("Passwords do not match. Nothing was changed.", file=sys.stderr)
        return 1

    try:
        with SessionLocal() as db:
            set_password(db, email, password)
    except SetPasswordError as exc:
        print(f"{exc}. Nothing was changed.", file=sys.stderr)
        return 1

    print(f"Password updated for {email.strip().lower()}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
