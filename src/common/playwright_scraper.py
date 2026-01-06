"""Base Playwright scraper with shared cookie and browser management."""

import json
import logging
import re
import sys
from pathlib import Path
from typing import Optional

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    async_playwright,
)

logging.basicConfig(
    level=logging.INFO,
    format="[PlaywrightScraper] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


class PlaywrightScraper:
    """Base class for Playwright-based scrapers with cookie authentication."""

    def __init__(
        self,
        cookies_file: Optional[Path] = None,
        cookies_list: Optional[list[dict]] = None,
        cookie_domains: Optional[list[str]] = None,
        target_domain: str = "",
        headless: bool = True,
        env_var_name: Optional[str] = None,
    ):
        """
        Initialize the scraper with authentication cookies.

        Args:
            cookies_file: Path to a cookies file (JSON or Netscape format)
            cookies_list: List of cookie dicts (alternative to file)
            cookie_domains: List of domains to accept cookies from
            target_domain: Domain to normalize cookies to (e.g., ".x.com")
            headless: Run browser in headless mode
            env_var_name: Environment variable name for cookies JSON fallback
        """
        self.cookies: list[dict] = []
        self.headless = headless
        self.cookie_domains = cookie_domains or []
        self.target_domain = target_domain
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._playwright = None

        if cookies_file and cookies_file.exists():
            self._load_cookies_from_file(cookies_file)
        elif cookies_list:
            self.cookies = cookies_list
        elif env_var_name:
            import os
            cookies_json = os.environ.get(env_var_name)
            if cookies_json:
                self.cookies = json.loads(cookies_json)

        if not self.cookies:
            raise ValueError(
                "No cookies provided. Export cookies from your browser as JSON "
                "or Netscape format."
            )

        logger.info(f"Loaded {len(self.cookies)} cookies")

    def _load_cookies_from_file(self, cookies_file: Path) -> None:
        """Load cookies from a JSON file or Netscape cookies.txt format."""
        content = cookies_file.read_text()

        # Try JSON first
        try:
            data = json.loads(content)
            if isinstance(data, list):
                self.cookies = data
            elif isinstance(data, dict):
                # Simple key-value format
                self.cookies = [
                    {"name": k, "value": v, "domain": self.target_domain, "path": "/"}
                    for k, v in data.items()
                ]
            return
        except json.JSONDecodeError:
            pass

        # Fall back to Netscape format
        self._parse_netscape_cookies(content)

    def _parse_netscape_cookies(self, content: str) -> None:
        """Parse Netscape cookies.txt format."""
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split("\t")
            if len(parts) >= 7:
                domain = parts[0]
                if domain in self.cookie_domains or any(
                    domain.endswith(d) for d in self.cookie_domains
                ):
                    # Normalize domain
                    cookie_domain = (
                        self.target_domain if domain.startswith(".") else self.target_domain.lstrip(".")
                    )
                    self.cookies.append(
                        {
                            "name": parts[5],
                            "value": parts[6],
                            "domain": cookie_domain,
                            "path": parts[2],
                            "secure": parts[3].upper() == "TRUE",
                            "httpOnly": False,
                        }
                    )

    async def _get_browser(self) -> Browser:
        """Get or create browser instance."""
        if self._browser is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=self.headless)
        return self._browser

    async def _get_context(self) -> BrowserContext:
        """Get or create browser context with cookies."""
        if self._context is None:
            browser = await self._get_browser()
            self._context = await browser.new_context(
                user_agent="Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0",
                viewport={"width": 1920, "height": 1080},
            )
            await self._context.add_cookies(self.cookies)
        return self._context

    async def _create_page(self, block_resources: bool = True) -> Page:
        """Create a new page with optional resource blocking."""
        context = await self._get_context()
        page = await context.new_page()

        if block_resources:
            await page.route(
                re.compile(r"\.(png|jpg|jpeg|gif|webp|woff|woff2)$"),
                lambda route: route.abort(),
            )

        return page

    async def close(self) -> None:
        """Close browser resources."""
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
