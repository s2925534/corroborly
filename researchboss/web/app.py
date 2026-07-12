from __future__ import annotations

from pathlib import Path
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Cookie, FastAPI, Header, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from researchboss.api.auth import SESSION_COOKIE_NAME, auth_configured, extract_token, session_is_valid


WEB_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))

router = APIRouter()


def _has_valid_session(authorization: Optional[str], session_cookie: Optional[str]) -> bool:
    if not auth_configured():
        return False
    token = extract_token(authorization, session_cookie)
    return bool(token and session_is_valid(token))


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: str = "/") -> HTMLResponse:
    """Serve the login form. Public — this is the only page reachable without a session."""
    return templates.TemplateResponse(request, "login.html", {"next": next})


@router.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    authorization: Optional[str] = Header(None),
    session_cookie: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
) -> HTMLResponse:
    """Serve the app shell, gated server-side before any workspace view loads.

    Without a valid session this redirects to `/login` rather than sending an
    empty shell that only discovers it's unauthenticated after JS makes its
    first API call — the "no view loads before login" requirement is enforced
    here, not just client-side.
    """
    if not _has_valid_session(authorization, session_cookie):
        next_url = str(request.url)
        return RedirectResponse(url=f"/login?next={quote(next_url)}", status_code=303)
    return templates.TemplateResponse(request, "index.html", {})


def mount_web(app: FastAPI) -> None:
    """Register the web UI shell and its static assets onto an existing FastAPI app.

    Deliberately outside `/api/v1` and outside the `require_session` API
    dependency: these routes serve HTML, not the JSON envelope, and enforce
    their own session gate (see `index` above) so an unauthenticated request
    gets a redirect to a login page, not a JSON 401.
    """
    app.include_router(router)
    app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="web-static")
