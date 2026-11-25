"""Settings for the API, read once from environment variables, plus the agent's fixed limits."""

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
# /chat only needs to know the caller is signed in; every signed-in user has this scope.
# Each MCP server still checks the scope of its own tools.
CHAT_REQUIRED_SCOPE = "docs:read"

# Limits that bound the agent's work and what is sent to the model.
MAX_AGENT_STEPS = 6
MAX_MESSAGE_CHARS = 2000
MAX_TOOL_RESULT_CHARS = 4000
LLM_TIMEOUT_SECONDS = 30.0
MCP_TIMEOUT_SECONDS = 10.0

SYSTEM_PROMPT = """You are the front-desk assistant of a small clinic.
The patient is already signed in, and every tool knows who they are.
Never ask for their name, ID, patient number or any other identifier.
Use the tools to book, list or cancel their appointments, check or add pharmacy stock,
read their own medical records, and answer questions about the clinic from its documents.
You can only see the signed-in patient's own data; politely refuse requests about anyone else.
Never diagnose, and never recommend a treatment or medicine; suggest booking a doctor instead.
If a tool returns an error, apologise briefly and suggest trying again later.
Keep answers short and friendly."""

STEP_LIMIT_REPLY = (
    "Sorry, I couldn't finish that request. Please try again with a shorter or simpler question."
)

# Env var for each MCP server's URL, keyed by the server's name.
MCP_URL_ENV_VARS = {
    "appointments": "APPOINTMENTS_MCP_URL",
    "pharmacy": "PHARMACY_MCP_URL",
    "records": "RECORDS_MCP_URL",
    "knowledge": "KNOWLEDGE_MCP_URL",
}

REQUIRED_ENV_VARS = [
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "OAUTH_REDIRECT_URI",
    "OPENAI_API_KEY",
    "CHAT_MODEL",
    *MCP_URL_ENV_VARS.values(),
]


@dataclass(frozen=True)
class Settings:
    """The Google OAuth client, the chat model and the MCP servers the API talks to."""

    google_client_id: str
    google_client_secret: str
    oauth_redirect_uri: str
    openai_api_key: str
    chat_model: str
    mcp_server_urls: dict[str, str]


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
        openai_api_key=os.environ["OPENAI_API_KEY"],
        chat_model=os.environ["CHAT_MODEL"],
        mcp_server_urls={name: os.environ[var] for name, var in MCP_URL_ENV_VARS.items()},
    )
