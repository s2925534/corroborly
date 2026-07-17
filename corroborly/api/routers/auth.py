from __future__ import annotations

import time
from typing import Any, Optional

from fastapi import APIRouter, Cookie, Header, Response
from pydantic import BaseModel

from corroborly.api.auth import (
    REMEMBER_ME_TTL_SECONDS,
    SESSION_COOKIE_NAME,
    auth_configured,
    create_session,
    extract_token,
    invalidate_session,
    verify_credentials,
)
from corroborly.api.envelope import ApiError, ok


router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str
    remember: bool = False


@router.post("/login")
def login(payload: LoginRequest, response: Response) -> dict[str, Any]:
    if not auth_configured():
        raise ApiError(
            "auth_not_configured",
            "CORROBORLY_API_USERNAME and CORROBORLY_API_PASSWORD are not set. Configure both before logging in.",
            status_code=503,
        )
    if not verify_credentials(payload.username, payload.password):
        raise ApiError("invalid_credentials", "Incorrect username or password.", status_code=401)

    token, expires_at = create_session(REMEMBER_ME_TTL_SECONDS if payload.remember else None)
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
