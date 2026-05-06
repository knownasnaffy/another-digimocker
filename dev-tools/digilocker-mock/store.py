import secrets
from datetime import datetime, timedelta, timezone

from config import settings

# auth_codes[code] = { persona_id, redirect_uri, code_challenge, expires_at }
auth_codes: dict[str, dict] = {}

# access_tokens[token] = { persona_id, expires_at }
access_tokens: dict[str, dict] = {}

# refresh_tokens[token] = { persona_id, expires_at }
refresh_tokens: dict[str, dict] = {}


def generate_token(length: int = 40) -> str:
    return secrets.token_hex(length // 2)


def issue_token_pair(persona_id: str) -> dict:
    access = generate_token()
    refresh = generate_token()
    access_tokens[access] = {
        "persona_id": persona_id,
        "expires_at": datetime.now(timezone.utc) + timedelta(seconds=settings.ACCESS_TOKEN_EXPIRES_IN),
    }
    refresh_tokens[refresh] = {
        "persona_id": persona_id,
        "expires_at": datetime.now(timezone.utc) + timedelta(seconds=settings.REFRESH_TOKEN_EXPIRES_IN),
    }
    return {
        "access_token": access,
        "refresh_token": refresh,
        "expires_in": settings.ACCESS_TOKEN_EXPIRES_IN,
        "token_type": "Bearer",
        "scope": "",
    }


def resolve_access_token(token: str) -> dict | None:
    entry = access_tokens.get(token)
    if not entry:
        return None
    if datetime.now(timezone.utc) > entry["expires_at"]:
        del access_tokens[token]
        return None
    return entry


def clear_all() -> None:
    """Clear all in-memory state."""
    auth_codes.clear()
    access_tokens.clear()
    refresh_tokens.clear()
