"""Institutional (university SSO) full-text access via a real browser session.

Corroborly cannot script a university single sign-on login end-to-end: QUT
(and virtually every Australian university) requires multi-factor
authentication -- an approval tap on a phone app -- on top of a password,
and that step fundamentally requires a human. Automating around it would be
building an MFA-bypass tool, which this project will not do.

Instead this module follows a "login once, reuse the session" pattern:

  1. `ensure_institutional_login()` launches a real, visible browser window
     (Playwright/Chromium) pointed at the institution's library sign-in
     page, using a *persistent* browser profile directory. You complete the
     normal login (password + MFA) yourself, in that window. Playwright
     writes cookies/local storage to the profile directory on disk as part
     of normal browser operation -- there is no separate credential or
     session file this module manages, parses, or could leak a password
     through.
  2. `fetch_full_text()` reuses that same persistent profile (headless by
     default) to visit a target article URL and look for a downloadable PDF
     using a small set of common publisher page patterns. If nothing is
     found -- paywalled, no recognizable PDF link, unusual page layout --
     it returns a `not_accessible` result with a concrete next step instead
     of failing silently or guessing at a URL.

This is deliberately best-effort: publisher page layouts vary too much for
a universal PDF-download detector, and this module does not attempt to
reverse-engineer proxy/redirector URL schemes it hasn't been shown. QUT
Library's confirmed, real off-campus access mechanism is OpenAthens (not
EZproxy) -- see QUT_OPENATHENS_SIGNIN_URL and
QUT_OPENATHENS_LINK_GENERATOR_URL below, both real QUT Library pages.

Requires the optional `playwright` dependency:
    pip install 'corroborly[institutional]'
    playwright install chromium   # one-time browser download
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

QUT_OPENATHENS_SIGNIN_URL = "https://www.library.qut.edu.au/search/getstarted/web/openathens/"
QUT_OPENATHENS_LINK_GENERATOR_URL = "https://www.library.qut.edu.au/search/status/linking/openathens/"

_PDF_LINK_SELECTORS = [
    "a[href$='.pdf']",
    "a:has-text('Download PDF')",
    "a:has-text('View PDF')",
    "a:has-text('PDF')",
    "a.c-pdf-download__link",  # SpringerLink
    "a[data-testid='pdf-download-link']",
    "link[type='application/pdf']",
]

_PAYWALL_PHRASES = [
    "purchase this article",
    "buy this article",
    "get access",
    "sign in to access",
    "institutional login",
    "purchase pdf",
    "rent this article",
]


class InstitutionalAccessError(RuntimeError):
    """Raised when institutional access cannot proceed (missing dependency,
    missing --institutional-access opt-in, or no saved login session)."""


@dataclass(frozen=True)
class FullTextResult:
    status: str  # "downloaded" | "not_accessible" | "login_required"
    target_url: str
    resolved_url: str | None
    local_path: str | None
    message: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def require_institutional_access_flag(enabled: bool) -> None:
    if not enabled:
        raise InstitutionalAccessError(
            "Pass --institutional-access to explicitly allow this action: it opens/reuses a "
            "real browser session and may download copyrighted content on your behalf."
        )


def institutional_profile_dir(workspace: Path) -> Path:
    """Directory holding the persistent Playwright browser profile (cookies,
    local storage) for the saved institutional login session. Contains live
    session state -- must never be committed to git."""
    return workspace / "data" / "openathens-profile"


def _default_playwright_factory() -> Any:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]
    except ImportError as exc:
        raise InstitutionalAccessError(
            "The optional 'playwright' package is not installed. Install with: "
            "pip install 'corroborly[institutional]' && playwright install chromium"
        ) from exc
    return sync_playwright


def ensure_institutional_login(
    workspace: Path,
    *,
    signin_url: str = QUT_OPENATHENS_SIGNIN_URL,
    wait_for_enter: Callable[[str], str] = input,
    playwright_factory: Callable[[], Any] | None = None,
) -> None:
    """Open a real, visible browser window for the user to sign in through
    their institution's SSO (including MFA) once. The persistent browser
    profile at `institutional_profile_dir(workspace)` then holds the
    resulting session for `fetch_full_text()` to reuse."""
    sync_playwright = (playwright_factory or _default_playwright_factory)()
    profile_dir = institutional_profile_dir(workspace)
    profile_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(str(profile_dir), headless=False)
        try:
            page = context.new_page()
            page.goto(signin_url)
            wait_for_enter(
                "A browser window has opened. Complete your institutional login there "
                "(including any MFA prompt), optionally open a resource to confirm access "
                "works, then press Enter here once you're done...\n"
            )
        finally:
            context.close()

    logger.info("Institutional login session saved to %s", profile_dir)


def fetch_full_text(
    target_url: str,
    workspace: Path,
    *,
    output_dir: Path | None = None,
    headless: bool = True,
    timeout_ms: int = 20000,
    playwright_factory: Callable[[], Any] | None = None,
) -> FullTextResult:
    """Reuse the saved institutional session to try to auto-download a PDF
    for `target_url`. Best-effort: if no session exists, or no downloadable
    PDF link can be found on the resolved page, returns a `not_accessible`
    (or `login_required`) result naming a concrete manual fallback instead
    of failing silently."""
    profile_dir = institutional_profile_dir(workspace)
    if not profile_dir.exists():
        return FullTextResult(
            status="login_required",
            target_url=target_url,
            resolved_url=None,
            local_path=None,
            message=(
                "No saved institutional session found. Run `corroborly institutional login` "
                "first to sign in once via your browser, then retry this fetch."
            ),
        )

    sync_playwright = (playwright_factory or _default_playwright_factory)()
    out_dir = output_dir or (workspace / "outputs" / "full-text")
    out_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(str(profile_dir), headless=headless)
        try:
            page = context.new_page()
            try:
                page.goto(target_url, timeout=timeout_ms)
            except Exception as exc:
                return FullTextResult(
                    status="not_accessible",
                    target_url=target_url,
                    resolved_url=None,
                    local_path=None,
                    message=(
                        f"Could not load {target_url} ({exc}). Try QUT Library's OpenAthens "
                        f"link generator manually: {QUT_OPENATHENS_LINK_GENERATOR_URL}"
                    ),
                )

            resolved_url = page.url

            for selector in _PDF_LINK_SELECTORS:
                locator = page.locator(selector).first
                try:
                    if locator.count() == 0:
                        continue
                except Exception:
                    continue
                try:
                    with page.expect_download(timeout=timeout_ms) as download_info:
                        locator.click(timeout=timeout_ms)
                    download = download_info.value
                    filename = download.suggested_filename or "download.pdf"
                    local_path = out_dir / filename
                    download.save_as(str(local_path))
                    return FullTextResult(
                        status="downloaded",
                        target_url=target_url,
                        resolved_url=resolved_url,
                        local_path=str(local_path),
                        message=f"Downloaded via selector '{selector}'.",
                    )
                except Exception:
                    continue

            page_text = (page.content() or "").lower()
        finally:
            context.close()

    paywalled = any(phrase in page_text for phrase in _PAYWALL_PHRASES)
    reason = "a paywall/login prompt was detected" if paywalled else "no downloadable PDF link was found on the page"
    return FullTextResult(
        status="not_accessible",
        target_url=target_url,
        resolved_url=resolved_url,
        local_path=None,
        message=(
            f"Could not auto-download from {resolved_url or target_url}: {reason}. "
            f"Try QUT Library's OpenAthens link generator: {QUT_OPENATHENS_LINK_GENERATOR_URL} "
            "(paste the article URL/DOI there), or search the title in QUT Library Search directly."
        ),
    )
