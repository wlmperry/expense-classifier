"""Shared bearer-token authentication for the public API surface.

A single shared token, not a user/account auth system -- see
docs/architecture.md's note that user/account ownership and authentication
are explicitly deferred. This exists only to keep the shared demo dataset
from being casually corrupted once the backend is reachable on the public
internet (Issue #36). Credentials come from the API_AUTH_TOKEN environment
variable, following the same convention as DATABASE_URL (app/database.py)
and PLAID_CLIENT_ID/PLAID_SECRET (app/plaid_client.py).
"""

import hmac
import os

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

load_dotenv()

# auto_error=False: handle a missing header ourselves so it is reported as
# 401, the same status used for a wrong token, instead of HTTPBearer's
# default 403 for a missing Authorization header.
_bearer_scheme = HTTPBearer(auto_error=False)


def get_api_token() -> str:
    token = os.environ.get("API_AUTH_TOKEN")
    if not token:
        raise RuntimeError(
            "API_AUTH_TOKEN is not set. Copy .env.example to .env and set a "
            "shared bearer token before starting the app."
        )
    return token


def require_auth_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> None:
    """FastAPI dependency: 401s unless the request's bearer token matches
    API_AUTH_TOKEN exactly. Attach via `dependencies=[Depends(require_auth_token)]`
    on routes that need it.
    """
    expected = get_api_token()
    if credentials is None or not hmac.compare_digest(credentials.credentials, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
