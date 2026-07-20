import sys
from pathlib import Path

import pytest

from corroborly.engine.institutional_access import (
    InstitutionalAccessError,
    ensure_institutional_login,
    fetch_full_text,
    institutional_profile_dir,
    require_institutional_access_flag,
)


# --------------------------------------------------------------------------
# Fake Playwright sync API surface (mirrors only what institutional_access.py calls)
# --------------------------------------------------------------------------


class FakeDownload:
    def __init__(self, filename: str = "paper.pdf"):
        self.suggested_filename = filename
        self.saved_to = None

    def save_as(self, path):
        self.saved_to = path
        Path(path).write_bytes(b"%PDF-1.4 fake content")


class FakeLocator:
    def __init__(self, *, count: int = 0, download: FakeDownload | None = None):
        self._count = count
        self._download = download
        self.page = None

    @property
    def first(self):
        return self

    def count(self) -> int:
        return self._count

    def click(self, timeout=None):
        if self._download is not None:
            self.page._last_download = self._download


class _ExpectDownloadCM:
    def __init__(self, page):
        self._page = page

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    @property
    def value(self):
        return self._page._last_download


class FakePage:
    def __init__(
        self,
        *,
        url: str = "https://example.com/article",
        html: str = "<html><body>Just an abstract page.</body></html>",
        selector_matches: dict | None = None,
        goto_error: Exception | None = None,
    ):
        self.url = url
        self._html = html
        self._selector_matches = selector_matches or {}
        self._goto_error = goto_error
        self._last_download = None

    def goto(self, url, timeout=None):
        if self._goto_error is not None:
            raise self._goto_error

    def locator(self, selector):
        locator = self._selector_matches.get(selector, FakeLocator(count=0))
        locator.page = self
        return locator

    def expect_download(self, timeout=None):
        return _ExpectDownloadCM(self)

    def content(self):
        return self._html


class FakeContext:
    def __init__(self, page: FakePage):
        self._page = page
        self.closed = False

    def new_page(self):
        return self._page

    def close(self):
        self.closed = True


class FakeChromium:
    def __init__(self, context: FakeContext):
        self._context = context
        self.launch_calls: list[dict] = []

    def launch_persistent_context(self, profile_dir, headless=False):
        self.launch_calls.append({"profile_dir": profile_dir, "headless": headless})
        return self._context


class _FakeSyncPlaywrightCM:
    def __init__(self, handle):
        self._handle = handle

    def __enter__(self):
        return self._handle

    def __exit__(self, *_args):
        return False


class _FakeHandle:
    def __init__(self, chromium: FakeChromium):
        self.chromium = chromium


def _fake_playwright_factory(page: FakePage):
    """Build a `playwright_factory` callable (returns something shaped like
    `sync_playwright`) around a single FakePage. Exposes `.context` and
    `.chromium` on the returned factory for assertions."""
    context = FakeContext(page)
    chromium = FakeChromium(context)
    handle = _FakeHandle(chromium)

    def sync_playwright():
        return _FakeSyncPlaywrightCM(handle)

    def factory():
        return sync_playwright

    factory.context = context
    factory.chromium = chromium
    return factory


# --------------------------------------------------------------------------
# require_institutional_access_flag
# --------------------------------------------------------------------------


def test_require_institutional_access_flag_raises_without_opt_in():
    with pytest.raises(InstitutionalAccessError, match="--institutional-access"):
        require_institutional_access_flag(False)


def test_require_institutional_access_flag_passes_with_opt_in():
    require_institutional_access_flag(True)


# --------------------------------------------------------------------------
# Missing dependency
# --------------------------------------------------------------------------


def test_missing_playwright_dependency_raises_clear_error(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "playwright", None)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", None)
    with pytest.raises(InstitutionalAccessError, match="playwright"):
        ensure_institutional_login(tmp_path, wait_for_enter=lambda _msg: "")


# --------------------------------------------------------------------------
# ensure_institutional_login
# --------------------------------------------------------------------------


def test_ensure_institutional_login_opens_signin_url_and_waits_for_human(tmp_path):
    page = FakePage()
    factory = _fake_playwright_factory(page)
    prompts = []

    def fake_wait(message):
        prompts.append(message)
        return ""

    ensure_institutional_login(
        tmp_path,
        signin_url="https://www.library.qut.edu.au/search/getstarted/web/openathens/",
        wait_for_enter=fake_wait,
        playwright_factory=factory,
    )

    assert len(prompts) == 1
    assert "MFA" in prompts[0]
    assert institutional_profile_dir(tmp_path).exists()
    assert factory.context.closed is True
    assert factory.chromium.launch_calls[0]["headless"] is False


# --------------------------------------------------------------------------
# fetch_full_text
# --------------------------------------------------------------------------


def test_fetch_full_text_requires_login_first_when_no_saved_session(tmp_path):
    result = fetch_full_text("https://example.com/paper", tmp_path)
    assert result.status == "login_required"
    assert "institutional login" in result.message


def test_fetch_full_text_downloads_pdf_when_link_found(tmp_path):
    institutional_profile_dir(tmp_path).mkdir(parents=True)
    download = FakeDownload(filename="my-paper.pdf")
    page = FakePage(
        url="https://example.com/resolved-article",
        selector_matches={"a[href$='.pdf']": FakeLocator(count=1, download=download)},
    )
    factory = _fake_playwright_factory(page)

    result = fetch_full_text("https://example.com/article", tmp_path, playwright_factory=factory)

    assert result.status == "downloaded"
    assert result.resolved_url == "https://example.com/resolved-article"
    assert result.local_path is not None
    assert result.local_path.endswith("my-paper.pdf")
    assert Path(result.local_path).exists()
    assert factory.chromium.launch_calls[0]["headless"] is True


def test_fetch_full_text_reports_not_accessible_when_paywalled(tmp_path):
    institutional_profile_dir(tmp_path).mkdir(parents=True)
    page = FakePage(html="<html><body>Purchase this article for $39.95</body></html>")
    factory = _fake_playwright_factory(page)

    result = fetch_full_text("https://example.com/article", tmp_path, playwright_factory=factory)

    assert result.status == "not_accessible"
    assert "paywall" in result.message
    assert "openathens" in result.message.lower()
    assert result.local_path is None


def test_fetch_full_text_reports_not_accessible_when_no_pdf_link_found(tmp_path):
    institutional_profile_dir(tmp_path).mkdir(parents=True)
    page = FakePage(html="<html><body>Just an abstract page, nothing special.</body></html>")
    factory = _fake_playwright_factory(page)

    result = fetch_full_text("https://example.com/article", tmp_path, playwright_factory=factory)

    assert result.status == "not_accessible"
    assert "no downloadable PDF" in result.message


def test_fetch_full_text_reports_not_accessible_on_navigation_failure(tmp_path):
    institutional_profile_dir(tmp_path).mkdir(parents=True)
    page = FakePage(goto_error=RuntimeError("navigation timeout"))
    factory = _fake_playwright_factory(page)

    result = fetch_full_text("https://example.com/article", tmp_path, playwright_factory=factory)

    assert result.status == "not_accessible"
    assert "navigation timeout" in result.message
    assert factory.context.closed is True
