import re
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.browser import BrowserAction, BrowserSession


class BrowserUnavailable(RuntimeError):
    pass


class BrowserStartupError(BrowserUnavailable):
    pass


def validate_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or re.search(r"[\r\n]", url):
        raise ValueError("Only validated http(s) URLs are allowed")
    return url


class BrowserManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._playwright = None
        self._browser = None
        self._pages: dict[str, object] = {}

    async def create_session(self, session: AsyncSession) -> BrowserSession:
        browser_session = BrowserSession()
        session.add(browser_session)
        await session.commit()
        return browser_session

    async def ensure_started(self) -> None:
        if self._browser is not None:
            return
        try:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=True)
        except ImportError as error:
            raise BrowserStartupError(
                "Playwright is not installed. Run 'pip install -r requirements.txt'."
            ) from error
        except Exception as error:
            raise BrowserStartupError(
                "Chromium could not start. Run 'python -m playwright install chromium' "
                "and verify the browser installation."
            ) from error

    async def shutdown(self) -> None:
        for page in list(self._pages.values()):
            await page.close()
        self._pages.clear()
        if self._browser is not None:
            await self._browser.close()
        if self._playwright is not None:
            await self._playwright.stop()
        self._browser = None
        self._playwright = None

    async def open_url(self, session: AsyncSession, browser_session: BrowserSession, url: str) -> dict:
        validate_url(url)
        await self.ensure_started()
        existing = self._pages.pop(browser_session.id, None)
        if existing is not None:
            await existing.close()
        page = await self._browser.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=self.settings.browser_navigation_timeout_ms)
        except Exception as error:
            await page.close()
            raise BrowserUnavailable(f"Unable to load {url}: {error}") from error
        self._pages[browser_session.id] = page
        browser_session.current_url = page.url
        browser_session.page_title = await page.title()
        browser_session.status = "active"
        session.add(BrowserAction(session_id=browser_session.id, action="open_url", details=url))
        await session.commit()
        return {"session_id": browser_session.id, "url": page.url, "title": browser_session.page_title}

    async def content(self, browser_session: BrowserSession) -> dict:
        page = self._pages.get(browser_session.id)
        if page is None:
            raise BrowserUnavailable("Browser session is not active")
        try:
            text = await page.locator("body").inner_text(timeout=self.settings.browser_content_timeout_ms)
            links = await page.locator("a").evaluate_all(
                "(anchors) => anchors.map((anchor) => anchor.href).filter(Boolean)"
            )
        except Exception as error:
            raise BrowserUnavailable(f"Unable to extract page content: {error}") from error
        return {"url": page.url, "title": await page.title(), "text": text, "links": links}

    async def screenshot(self, browser_session: BrowserSession, workspace: Path) -> Path:
        page = self._pages.get(browser_session.id)
        if page is None:
            raise BrowserUnavailable("Browser session is not active")
        output = workspace / "screenshots" / f"{browser_session.id}.png"
        output.parent.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(output), full_page=False)
        return output

    async def close(self, browser_session: BrowserSession) -> None:
        page = self._pages.pop(browser_session.id, None)
        if page is not None:
            await page.close()
        browser_session.status = "closed"
