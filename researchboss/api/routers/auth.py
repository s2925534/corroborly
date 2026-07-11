from __future__ import annotations

import time
from typing import Any, Optional

from fastapi import APIRouter, Cookie, Header, Response
from pydantic import BaseModel

from researchboss.api.auth import (
    SESSION_COOKIE_NAME,
    auth_configured,
    create_session,
    extract_token,
    invalidate_session,
    verify_password,
)
from researchboss.api.envelope import ApiError, ok


router = APIRouter()


class LoginRequest(BaseModel):
    password: str


@router.post("/login")
def login(payload: LoginRequest, response: Response) -> dict[str, Any]:
    if not auth_configured():
        raise ApiError(
            "auth_not_configured",
            "RESEARCHBOSS_API_PASSWORD is not set. Configure it before logging in.",
            status_code=503,
        )
    if not verify_password(payload.password):
        raise ApiError("invalid_credentials", "Incorrect password.", status_code=401)

    token, expires_at = create_session()
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        max_age=max(1, int(expires_at - time.time())),
    )
    return ok({"token": token, "expires_at": expires_at})


@router.post("/logout")
def logout(
    response: Response,
    authorization: Optional[str] = Header(None),
    session_cookie: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
) -> dict[str, Any]:
    token = extract_token(authorization, session_cookie)
    if token:
        invalidate_session(token)
    response.delete_cookie(SESSION_COOKIE_NAME)
    return ok({"logged_out": True})
