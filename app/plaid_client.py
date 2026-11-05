"""Plaid API client configuration.

Credentials come from PLAID_CLIENT_ID, PLAID_SECRET, and PLAID_ENV
environment variables (PLAID_ENV defaults to "sandbox"). A local, untracked
.env file may be used for development configuration, the same convention
DATABASE_URL already uses in app/database.py.

The client is built lazily (on first call to get_plaid_client(), not at
import time) and cached, so importing this module -- or app.main, or
running the test suite -- never requires Plaid credentials to be set.
Only the /plaid/* endpoints that actually call get_plaid_client() do.
"""

import os
from functools import lru_cache

from dotenv import load_dotenv
from plaid.api import plaid_api
from plaid.api_client import ApiClient
from plaid.configuration import Configuration, Environment

load_dotenv()

_ENVIRONMENTS = {
    "sandbox": Environment.Sandbox,
    "production": Environment.Production,
}


@lru_cache(maxsize=1)
def get_plaid_client() -> plaid_api.PlaidApi:
    client_id = os.environ.get("PLAID_CLIENT_ID")
    secret = os.environ.get("PLAID_SECRET")
    env_name = os.environ.get("PLAID_ENV", "sandbox")

    if not client_id or not secret:
        raise RuntimeError(
            "PLAID_CLIENT_ID and PLAID_SECRET are not set. Copy .env.example "
            "to .env and add your Plaid Sandbox keys."
        )
    if env_name not in _ENVIRONMENTS:
        raise RuntimeError(
            f"Unknown PLAID_ENV '{env_name}'; expected 'sandbox' or 'production'."
        )

    configuration = Configuration(
        host=_ENVIRONMENTS[env_name],
        api_key={"clientId": client_id, "secret": secret},
    )
    return plaid_api.PlaidApi(ApiClient(configuration))
