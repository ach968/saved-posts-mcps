import asyncio
import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Browser, BrowserContext

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
    """Scraper for X.com bookmarks using Playwright with browser cookies."""

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

    async def fetch_bookmarks_page(self, scroll_count: int = 3) -> str:
        """
        Fetch the bookmarks page HTML using Playwright.

        Args:
            scroll_count: Number of times to scroll down to load more tweets

        Returns:
            HTML content of the page
        """
        logger.info(f"Starting fetch_bookmarks_page with {scroll_count} scrolls")
        logger.info(f"Loaded {len(self.cookies)} cookies")

        context = await self._get_context()
        logger.info("Got browser context")

        page = await context.new_page()
        logger.info("Created new page")

        try:
            # Navigate to bookmarks - use domcontentloaded instead of networkidle
            logger.info(f"Navigating to {BOOKMARKS_URL}")
            await page.goto(BOOKMARKS_URL, wait_until="domcontentloaded", timeout=60000)
            logger.info(f"Page loaded, current URL: {page.url}")

            # Take a screenshot for debugging
            await page.screenshot(path="/tmp/x_bookmarks_debug.png")
            logger.info("Screenshot saved to /tmp/x_bookmarks_debug.png")

            # Check if we got redirected to login
            if "login" in page.url.lower():
                logger.error("Redirected to login page - cookies may be invalid")
                html = await page.content()
                return html

            # Wait for tweets to load
            logger.info("Waiting for article elements...")
            try:
                await page.wait_for_selector("article", timeout=15000)
                logger.info("Found article elements")
            except Exception as e:
                logger.warning(f"No articles found: {e}")
                # Save page content for debugging
                html = await page.content()
                with open("/tmp/x_bookmarks_debug.html", "w") as f:
                    f.write(html)
                logger.info("HTML saved to /tmp/x_bookmarks_debug.html")
                return html

            # Scroll to load more tweets
            for i in range(scroll_count):
                logger.info(f"Scroll {i+1}/{scroll_count}")
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1.5)

            # Get the page content
            html = await page.content()
            logger.info(f"Got page content, length: {len(html)}")
            return html

        except Exception as e:
            logger.error(f"Error during fetch: {e}")
            # Try to save screenshot on error
            try:
                await page.screenshot(path="/tmp/x_bookmarks_error.png")
                logger.info("Error screenshot saved to /tmp/x_bookmarks_error.png")
            except:
                pass
            raise

        finally:
            await page.close()
            logger.info("Page closed")

    def parse_articles(self, html: str) -> list[SavedPost]:
        """
        Parse article elements from the bookmarks page.

        Args:
            html: Raw HTML content from the bookmarks page

        Returns:
            List of SavedPost objects
        """
        soup = BeautifulSoup(html, "lxml")
        articles = soup.find_all("article")
        posts = []

        for article in articles:
            try:
                post = self._parse_article(article)
                if post:
                    posts.append(post)
            except Exception as e:
                # Log but continue parsing other articles
                logger.warning(f"Error parsing article: {e}")
                continue

        return posts

    def _parse_article(self, article) -> Optional[SavedPost]:
        """Parse a single article element into a SavedPost."""
        # Extract tweet text
        tweet_text_div = article.find("div", {"data-testid": "tweetText"})
        content = tweet_text_div.get_text(separator=" ", strip=True) if tweet_text_div else ""

        # Extract author info from User-Name div
        user_name_element = article.find("div", {"data-testid": "User-Name"})
        if not user_name_element:
            return None

        # Find all links in the User-Name section
        links = user_name_element.find_all("a")
        username = None
        display_name = None

        for link in links:
            href = link.get("href", "")
            if href and re.match(r"^/[^/]+$", href) and not href.startswith("/i/"):
                username = href.strip("/")
                # Display name is usually in a span within the first link
                spans = link.find_all("span")
                for span in spans:
                    text = span.get_text(strip=True)
                    if text and not text.startswith("@"):
                        display_name = text
                        break
                break

        if not username:
            return None

        if not display_name:
            display_name = username

        # Extract tweet ID from the permalink
        permalink = article.find("a", href=re.compile(r"/status/\d+"))
        if not permalink:
            return None

        href = permalink.get("href", "")
        tweet_id_match = re.search(r"/status/(\d+)", href)
        if not tweet_id_match:
            return None

        tweet_id = tweet_id_match.group(1)

        # Extract timestamp
        time_element = article.find("time")
        if time_element and time_element.get("datetime"):
            created_at = datetime.fromisoformat(time_element["datetime"].replace("Z", "+00:00"))
        else:
            created_at = datetime.now()

        # Extract media
        media_list = []
        images = article.find_all("img", {"src": re.compile(r"pbs\.twimg\.com/media")})
        for img in images:
            media_list.append(
                Media(
                    type="image",
                    url=img.get("src", ""),
                )
            )

        # Check for video
        video_container = article.find("div", {"data-testid": "videoComponent"})
        if video_container:
            video = video_container.find("video")
            if video:
                poster = video.get("poster", "")
                media_list.append(
                    Media(
                        type="video",
                        url=poster,  # Video URL requires additional API call
                        thumbnail_url=poster,
                    )
                )

        # Extract avatar
        avatar_img = article.find("img", {"src": re.compile(r"pbs\.twimg\.com/profile_images")})
        avatar_url = avatar_img.get("src") if avatar_img else None

        author = Author(
            id=username,
            username=username,
            display_name=display_name,
            avatar_url=avatar_url,
            platform="x",
        )

        # Extract metrics
        metrics = self._extract_metrics(article)

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

    def _extract_metrics(self, article) -> dict:
        """Extract engagement metrics from the article."""
        metrics = XMetadata(
            retweet_count=0,
            like_count=0,
            reply_count=0,
            quote_count=0,
        )

        # Look for metric groups by data-testid
        metric_mappings = [
            ("reply", "reply_count"),
            ("retweet", "retweet_count"),
            ("like", "like_count"),
        ]

        for testid, attr in metric_mappings:
            group = article.find("button", {"data-testid": testid})
            if group:
                # Find the text showing the count
                aria_label = group.get("aria-label", "")
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

    async def get_bookmarks(
        self,
        limit: Optional[int] = None,
        scroll_count: int = 5,
    ) -> list[SavedPost]:
        """
        Fetch and parse bookmarked tweets.

        Args:
            limit: Maximum number of bookmarks to return
            scroll_count: Number of times to scroll for more content

        Returns:
            List of SavedPost objects
        """
        html = await self.fetch_bookmarks_page(scroll_count=scroll_count)
        posts = self.parse_articles(html)

        if limit:
            posts = posts[:limit]

        return posts

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
