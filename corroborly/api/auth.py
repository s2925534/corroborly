from __future__ import annotations

import hmac
import os
import secrets
import time
from pathlib import Path
from typing import Optional


DEFAULT_SESSION_TTL_SECONDS = 12 * 60 * 60
REMEMBER_ME_TTL_SECONDS = 30 * 24 * 60 * 60
SESSION_COOKIE_NAME = "corroborly_session"

_sessions: dict[str, float] = {}


def _load_dotenv_values(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _configured_password() -> Optional[str]:
    env_values = _load_dotenv_values(Path.cwd() / ".env")
    password = os.environ.get("CORROBORLY_API_PASSWORD") or env_values.get("CORROBORLY_API_PASSWORD")
    return password or None


def _configured_username() -> Optional[str]:
    env_values = _load_dotenv_values(Path.cwd() / ".env")
    username = os.environ.get("CORROBORLY_API_USERNAME") or env_values.get("CORROBORLY_API_USERNAME")
    return username or None


def _session_ttl_seconds() -> int:
    raw = os.environ.get("CORROBORLY_API_SESSION_HOURS")
    if not raw:
        return DEFAULT_SESSION_TTL_SECONDS
    try:
        hours = float(raw)
    except ValueError:
        return DEFAULT_SESSION_TTL_SECONDS
    return max(60, int(hours * 3600))


def auth_configured() -> bool:
    """True when both CORROBORLY_API_USERNAME and CORROBORLY_API_PASSWORD are set.

    Protected routes fail closed otherwise. A username is required alongside
    the password (not just a bare password box) to match the login UX of a
    real account, even though this is still a single shared credential pair,
    not a per-user account system — see AGENTS.md / TODO.md for the separate,
    larger multi-tenant item that would add real per-user accounts.
    """
    return _configured_username() is not None and _configured_password() is not None


def verify_credentials(username: str, password: str) -> bool:
    configured_username = _configured_username()
    configured_password = _configured_password()
    if configured_username is None or configured_password is None:
        return False
    username_ok = hmac.compare_digest(configured_username, username)
    password_ok = hmac.compare_digest(configured_password, password)
    return username_ok and password_ok


def create_session(ttl_seconds: Optional[int] = None) -> tuple[str, float]:
    token = secrets.token_urlsafe(32)
    expires_at = time.time() + (ttl_seconds if ttl_seconds is not None else _session_ttl_seconds())
    _sessions[token] = expires_at
    return token, expires_at


def invalidate_session(token: str) -> None:
    _sessions.pop(token, None)


def session_is_valid(token: str) -> bool:
    expires_at = _sessions.get(token)
    if expires_at is None:
        return False
    if expires_at < time.time():
        _sessions.pop(token, None)
        return False
    return True


def clear_all_sessions() -> None:
    """Test-only helper: reset in-memory session state between tests."""
    _sessions.clear()


def extract_token(authorization: Optional[str], session_cookie: Optional[str]) -> Optional[str]:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip() or None
    return session_cookie or None
