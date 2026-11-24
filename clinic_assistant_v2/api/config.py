"""Settings for the API, read once from environment variables."""

import os
from dataclasses import dataclass

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 - a public URL, not a secret
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GOOGLE_SCOPES = "openid email"
GOOGLE_TIMEOUT_SECONDS = 10.0

# The cookie that carries the OAuth state from /auth/login to /auth/callback.
STATE_COOKIE_NAME = "oauth_state"
STATE_COOKIE_MAX_AGE_SECONDS = 600

# In v2 every signed-in user gets all six scopes (see docs/contract.md).
USER_SCOPES = [
    "appointments:read",
    "appointments:write",
    "pharmacy:read",
    "pharmacy:write",
    "records:read",
    "docs:read",
]

REQUIRED_ENV_VARS = ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "OAUTH_REDIRECT_URI"]


@dataclass(frozen=True)
class Settings:
    """The Google OAuth client the API signs users in with."""

    google_client_id: str
    google_client_secret: str
    oauth_redirect_uri: str


def load_settings() -> Settings:
    """Read the settings from the environment; fail fast naming every missing one."""
    missing = [name for name in REQUIRED_ENV_VARS if not os.environ.get(name)]
    if missing:
        raise RuntimeError(
            f"Missing environment variables: {', '.join(missing)}. "
            "Copy .env.example to .env and fill them in."
        )
    return Settings(
        google_client_id=os.environ["GOOGLE_CLIENT_ID"],
        google_client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        oauth_redirect_uri=os.environ["OAUTH_REDIRECT_URI"],
    )
