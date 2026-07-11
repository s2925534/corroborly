from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import Cookie, Header, Query

from researchboss.api.auth import SESSION_COOKIE_NAME, auth_configured, extract_token, session_is_valid
from researchboss.api.envelope import ApiError


def resolve_workspace(
    workspace: str = Query(..., description="Absolute local workspace path."),
) -> Path:
    """Resolve the `workspace` query parameter without any interactive discovery.

    CLI commands may prompt to discover or select a workspace; the API has no
    interactive surface, so callers must always pass an explicit workspace path.
    """
    path = Path(workspace).expanduser()
    if not path.is_absolute():
        path = path.resolve()
    if not path.is_dir():
        raise ApiError("workspace_not_found", f"Workspace does not exist: {workspace}", status_code=404)
    return path


def require_session(
    authorization: Optional[str] = Header(None),
    session_cookie: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
) -> None:
    """Require a valid session on every protected route.

    Fails closed (503) when no RESEARCHBOSS_API_PASSWORD is configured, rather
    than silently allowing unauthenticated access.
    """
    if not auth_configured():
        raise ApiError(
            "auth_not_configured",
            "RESEARCHBOSS_API_PASSWORD is not set. Configure it before using this API.",
            status_code=503,
        )
    token = extract_token(authorization, session_cookie)
    if not token or not session_is_valid(token):
        raise ApiError(
            "unauthorized",
            "A valid session is required. Log in via POST /api/v1/auth/login.",
            status_code=401,
        )
