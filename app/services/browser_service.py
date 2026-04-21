from __future__ import annotations

import re
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, Optional

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class BrowserService:
    """Manages Playwright browser sessions for web scraping."""

    def __init__(self) -> None:
        self._playwright = None
        self._browser = None

    async def start(self) -> None:
        """Launch Playwright and open a browser instance."""
        try:
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"],
            )
            logger.info("Browser started successfully.")
        except Exception as exc:
            logger.error("Failed to start browser: %s", exc)
            raise

    async def stop(self) -> None:
        """Close the browser and Playwright instance."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.info("Browser stopped.")

    @asynccontextmanager
    async def new_page(
        self,
        mobile: bool = False,
        timeout: Optional[int] = None,
    ) -> AsyncGenerator[Any, None]:
        """Context manager yielding a new browser page."""
        if self._browser is None:
            raise RuntimeError("Browser is not started. Call start() first.")

        context_options: Dict[str, Any] = {}
        if mobile:
            from playwright.async_api import async_playwright as _ap  # noqa: F401

            context_options["viewport"] = {"width": 390, "height": 844}
            context_options["user_agent"] = (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 "
                "Mobile/15E148 Safari/604.1"
            )
        else:
            context_options["viewport"] = {"width": 1280, "height": 800}

        context = await self._browser.new_context(**context_options)
        page = await context.new_page()
        page.set_default_timeout(timeout or settings.BROWSER_TIMEOUT)
        try:
            yield page
        finally:
            await context.close()

    async def fetch_page_data(
        self,
        url: str,
        mobile: bool = False,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Navigate to *url* and collect raw page data for analysis.

        Returns a dictionary with HTML content, performance metrics,
        and metadata.
        """
        data: Dict[str, Any] = {
            "url": url,
            "html": "",
            "title": "",
            "performance": {},
            "resource_count": 0,
            "page_size_bytes": 0,
            "status_code": 0,
            "error": None,
        }

        try:
            async with self.new_page(mobile=mobile, timeout=timeout) as page:
                resources: list[str] = []

                page.on(
                    "response",
                    lambda r: resources.append(r.url),
                )

                response = await page.goto(url, wait_until="networkidle")
                if response:
                    data["status_code"] = response.status

                data["title"] = await page.title()
                data["html"] = await page.content()
                data["resource_count"] = len(resources)

                # Collect browser performance timing
                perf = await page.evaluate(
                    """() => {
                        const nav = performance.getEntriesByType('navigation')[0] || {};
                        const paint = {};
                        performance.getEntriesByType('paint').forEach(e => {
                            paint[e.name] = e.startTime;
                        });
                        return {
                            domContentLoaded: nav.domContentLoadedEventEnd || 0,
                            loadEventEnd: nav.loadEventEnd || 0,
                            firstPaint: paint['first-paint'] || 0,
                            firstContentfulPaint: paint['first-contentful-paint'] || 0,
                            transferSize: nav.transferSize || 0,
                        };
                    }"""
                )
                data["performance"] = perf
                data["page_size_bytes"] = perf.get("transferSize", 0)

                logger.info("Fetched page data for %s (status=%s)", url, data["status_code"])
        except Exception as exc:
            logger.error("Error fetching %s: %s", url, exc)
            data["error"] = str(exc)

        return data

    # ------------------------------------------------------------------
    # Helpers used by tests without a live browser
    # ------------------------------------------------------------------

    @staticmethod
    def extract_links(html: str) -> list[str]:
        """Return all href values found in *html*."""
        return re.findall(r'href=["\']([^"\']+)["\']', html)
