import asyncio
import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Locator

from src.common.models import Author, Media, SavedPost, XMetadata

# Configure logging to stderr (stdout is used for MCP JSON-RPC)
logging.basicConfig(
    level=logging.INFO,
    format="[XScraper] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

BOOKMARKS_URL = "https://x.com/i/bookmarks"


class XScraper:
    """Scraper for X.com bookmarks using Playwright."""

    def __init__(
        self,
        cookies_file: Optional[Path] = None,
        cookies_list: Optional[list[dict]] = None,
        headless: bool = True,
    ):
        """
        Initialize the scraper with authentication cookies.

        Args:
            cookies_file: Path to a JSON file containing cookies array
            cookies_list: List of cookie dicts (alternative to file)
            headless: Run browser in headless mode
        """
        self.cookies: list[dict] = []
        self.headless = headless
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None

        if cookies_file and cookies_file.exists():
            self._load_cookies_from_file(cookies_file)
        elif cookies_list:
            self.cookies = cookies_list
        else:
            # Try to load from environment variable
            cookies_json = os.environ.get("X_COOKIES")
            if cookies_json:
                self.cookies = json.loads(cookies_json)

        if not self.cookies:
            raise ValueError(
                "No cookies provided. Export cookies from your browser as JSON, "
                "or set X_COOKIES environment variable."
            )

    def _load_cookies_from_file(self, cookies_file: Path) -> None:
        """Load cookies from a JSON file or Netscape cookies.txt format."""
        content = cookies_file.read_text()

        # Try JSON format first
        try:
            data = json.loads(content)
            if isinstance(data, list):
                self.cookies = data
            elif isinstance(data, dict):
                # Convert dict to list format for Playwright
                self.cookies = [
                    {"name": k, "value": v, "domain": ".x.com", "path": "/"}
                    for k, v in data.items()
                ]
            return
        except json.JSONDecodeError:
            pass

        # Try Netscape cookies.txt format
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
                if domain in [".x.com", "x.com", ".twitter.com", "twitter.com"]:
                    # Convert to x.com domain
                    cookie_domain = ".x.com" if domain.startswith(".") else "x.com"
                    self.cookies.append({
                        "name": parts[5],
                        "value": parts[6],
                        "domain": cookie_domain,
                        "path": parts[2],
                        "secure": parts[3].upper() == "TRUE",
                        "httpOnly": False,
                    })

    async def _get_browser(self) -> Browser:
        """Get or create browser instance."""
        if self._browser is None:
            playwright = await async_playwright().start()
            self._browser = await playwright.chromium.launch(headless=self.headless)
        return self._browser

    async def _get_context(self) -> BrowserContext:
        """Get or create browser context with cookies."""
        if self._context is None:
            browser = await self._get_browser()
            self._context = await browser.new_context(
                user_agent="Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0",
                viewport={"width": 1920, "height": 1080},
            )
            # Add cookies
            await self._context.add_cookies(self.cookies)
        return self._context

    async def close(self) -> None:
        """Close browser resources."""
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None

    async def get_bookmarks(
        self,
        limit: Optional[int] = None,
        scroll_count: int = 15,
    ) -> list[SavedPost]:
        """
        Fetch and parse bookmarked tweets using Playwright.

        Args:
            limit: Maximum number of bookmarks to return
            scroll_count: Number of times to scroll for more content

        Returns:
            List of SavedPost objects
        """
        logger.info(f"Starting get_bookmarks with {scroll_count} scrolls")
        logger.info(f"Loaded {len(self.cookies)} cookies")

        context = await self._get_context()
        logger.info("Got browser context")

        page = await context.new_page()
        logger.info("Created new page")

        try:
            # Navigate to bookmarks
            logger.info(f"Navigating to {BOOKMARKS_URL}")
            await page.goto(BOOKMARKS_URL, wait_until="domcontentloaded", timeout=60000)
            logger.info(f"Page loaded, current URL: {page.url}")

            # Take a screenshot for debugging
            await page.screenshot(path="/tmp/x_bookmarks_debug.png")
            logger.info("Screenshot saved to /tmp/x_bookmarks_debug.png")

            # Check if we got redirected to login
            if "login" in page.url.lower():
                logger.error("Redirected to login page - cookies may be invalid")
                return []

            # Wait for tweets to load
            logger.info("Waiting for article elements...")
            try:
                await page.wait_for_selector("article", timeout=15000)
                logger.info("Found article elements")
            except Exception as e:
                logger.warning(f"No articles found: {e}")
                return []

            # Scroll to load more tweets
            for i in range(scroll_count):
                logger.info(f"Scroll {i+1}/{scroll_count}")
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1.5)

            # Parse articles using Playwright locators
            posts = await self._parse_articles(page)
            logger.info(f"Parsed {len(posts)} posts")

            if limit:
                posts = posts[:limit]

            return posts

        except Exception as e:
            logger.error(f"Error during fetch: {e}")
            try:
                await page.screenshot(path="/tmp/x_bookmarks_error.png")
                logger.info("Error screenshot saved to /tmp/x_bookmarks_error.png")
            except:
                pass
            raise

        finally:
            await page.close()
            logger.info("Page closed")

    async def _parse_articles(self, page: Page) -> list[SavedPost]:
        """Parse all article elements from the page using Playwright."""
        articles = page.locator("article")
        count = await articles.count()
        logger.info(f"Found {count} articles to parse")

        posts = []
        for i in range(count):
            try:
                article = articles.nth(i)
                post = await self._parse_article(article)
                if post:
                    posts.append(post)
            except Exception as e:
                logger.warning(f"Error parsing article {i}: {e}")
                continue

        return posts

    async def _parse_article(self, article: Locator) -> Optional[SavedPost]:
        """Parse a single article element into a SavedPost."""
        # Extract tweet text
        tweet_text = article.locator('[data-testid="tweetText"]')
        content = ""
        if await tweet_text.count() > 0:
            content = await tweet_text.first.inner_text()

        # Extract author info from User-Name div
        user_name_element = article.locator('[data-testid="User-Name"]')
        if await user_name_element.count() == 0:
            return None

        # Find username from links
        links = user_name_element.locator("a")
        username = None
        display_name = None

        link_count = await links.count()
        for j in range(link_count):
            link = links.nth(j)
            href = await link.get_attribute("href") or ""
            if href and re.match(r"^/[^/]+$", href) and not href.startswith("/i/"):
                username = href.strip("/")
                # Try to get display name from spans
                spans = link.locator("span")
                span_count = await spans.count()
                for k in range(span_count):
                    text = await spans.nth(k).inner_text()
                    if text and not text.startswith("@"):
                        display_name = text.strip()
                        break
                break

        if not username:
            return None

        if not display_name:
            display_name = username

        # Extract tweet ID from permalink
        permalink = article.locator('a[href*="/status/"]')
        if await permalink.count() == 0:
            return None

        href = await permalink.first.get_attribute("href") or ""
        tweet_id_match = re.search(r"/status/(\d+)", href)
        if not tweet_id_match:
            return None

        tweet_id = tweet_id_match.group(1)

        # Extract timestamp
        time_element = article.locator("time")
        created_at = datetime.now()
        if await time_element.count() > 0:
            datetime_str = await time_element.first.get_attribute("datetime")
            if datetime_str:
                created_at = datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))

        # Extract media
        media_list = []
        images = article.locator('img[src*="pbs.twimg.com/media"]')
        img_count = await images.count()
        for j in range(img_count):
            src = await images.nth(j).get_attribute("src")
            if src:
                media_list.append(Media(type="image", url=src))

        # Check for video
        video_container = article.locator('[data-testid="videoComponent"]')
        if await video_container.count() > 0:
            video = video_container.locator("video")
            if await video.count() > 0:
                poster = await video.first.get_attribute("poster")
                if poster:
                    media_list.append(Media(type="video", url=poster, thumbnail_url=poster))

        # Extract avatar
        avatar_img = article.locator('img[src*="pbs.twimg.com/profile_images"]')
        avatar_url = None
        if await avatar_img.count() > 0:
            avatar_url = await avatar_img.first.get_attribute("src")

        author = Author(
            id=username,
            username=username,
            display_name=display_name,
            avatar_url=avatar_url,
            platform="x",
        )

        # Extract metrics
        metrics = await self._extract_metrics(article)

        return SavedPost(
            id=tweet_id,
            platform="x",
            author=author,
            content=content,
            url=f"https://x.com/{username}/status/{tweet_id}",
            created_at=created_at,
            media=media_list,
            metadata=metrics,
        )

    async def _extract_metrics(self, article: Locator) -> dict:
        """Extract engagement metrics from the article."""
        metrics = XMetadata(
            retweet_count=0,
            like_count=0,
            reply_count=0,
            quote_count=0,
        )

        metric_mappings = [
            ("reply", "reply_count"),
            ("retweet", "retweet_count"),
            ("like", "like_count"),
        ]

        for testid, attr in metric_mappings:
            button = article.locator(f'button[data-testid="{testid}"]')
            if await button.count() > 0:
                aria_label = await button.first.get_attribute("aria-label") or ""
                count_match = re.search(r"(\d+(?:,\d+)*(?:\.\d+)?[KMB]?)", aria_label)
                if count_match:
                    setattr(metrics, attr, self._parse_count(count_match.group(1)))

        return metrics.model_dump()

    def _parse_count(self, text: str) -> int:
        """Parse a count string like '1.2K' or '500' into an integer."""
        text = text.strip()
        if not text:
            return 0

        multipliers = {"K": 1000, "M": 1000000, "B": 1000000000}

        for suffix, mult in multipliers.items():
            if text.endswith(suffix):
                try:
                    return int(float(text[:-1]) * mult)
                except ValueError:
                    return 0

        try:
            return int(text.replace(",", ""))
        except ValueError:
            return 0

    def search_bookmarks(
        self,
        posts: list[SavedPost],
        query: str,
        limit: Optional[int] = None,
    ) -> list[SavedPost]:
        """
        Search through bookmarks by keyword.

        Args:
            posts: List of posts to search through
            query: Search term
            limit: Maximum results

        Returns:
            Filtered list of matching posts
        """
        query_lower = query.lower()
        results = [p for p in posts if query_lower in p.content.lower()]

        if limit:
            results = results[:limit]

        return results

    @classmethod
    def from_env(cls, headless: bool = True) -> "XScraper":
        """Create an XScraper from environment variables."""
        cookies_file = os.environ.get("X_COOKIES_FILE")
        if cookies_file:
            return cls(cookies_file=Path(cookies_file), headless=headless)

        cookies_json = os.environ.get("X_COOKIES")
        if cookies_json:
            return cls(cookies_list=json.loads(cookies_json), headless=headless)

        # Try default location
        default_path = Path.home() / ".x_cookies.txt"
        if default_path.exists():
            return cls(cookies_file=default_path, headless=headless)

        raise ValueError(
            "No cookies found. Set X_COOKIES_FILE to path of cookies file, "
            "or X_COOKIES to a JSON array of cookies, "
            "or place cookies at ~/.x_cookies.txt"
        )
