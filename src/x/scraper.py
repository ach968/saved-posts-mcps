import asyncio
import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Response,
)

from src.common.models import Author, Media, SavedPost, XMetadata

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
        max_scrolls: int = 250,
    ) -> list[SavedPost]:
        """
        Fetch bookmarked tweets by intercepting X's GraphQL API responses.

        Args:
            limit: Maximum number of bookmarks to return
            max_scrolls: Safety limit for maximum scroll attempts (default 250)

        Returns:
            List of SavedPost objects
        """
        logger.info(f"Starting get_bookmarks (max {max_scrolls} scrolls)")
        logger.info(f"Loaded {len(self.cookies)} cookies")

        context = await self._get_context()
        logger.info("Got browser context")

        page = await context.new_page()
        logger.info("Created new page")

        # Collect tweets from GraphQL responses
        collected_posts: list[SavedPost] = []
        seen_ids: set[str] = set()

        def handle_response(response: Response) -> None:
            """Capture GraphQL bookmark responses."""
            if "Bookmarks" in response.url and "graphql" in response.url:
                try:
                    # Run async json() in the event loop
                    asyncio.create_task(self._process_response(response, collected_posts, seen_ids))
                except Exception as e:
                    logger.warning(f"Error queuing response: {e}")

        page.on("response", handle_response)

        try:
            # Block unnecessary resources for speed
            await page.route(
                re.compile(r"\.(png|jpg|jpeg|gif|webp|css|woff|woff2)$"),
                lambda route: route.abort()
            )

            logger.info(f"Navigating to {BOOKMARKS_URL}")
            await page.goto(BOOKMARKS_URL, wait_until="domcontentloaded", timeout=60000)
            logger.info(f"Page loaded, current URL: {page.url}")

            if "login" in page.url.lower():
                logger.error("Redirected to login page - cookies may be invalid")
                return []

            # Wait for initial content
            await asyncio.sleep(3)

            scroll_num = 0
            no_new_count = 0
            last_count = 0

            while scroll_num < max_scrolls:
                if limit and len(collected_posts) >= limit:
                    logger.info(f"Reached limit of {limit} posts")
                    break
                scroll_num += 1

                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(0.5)

                # Check if we got new posts
                if len(collected_posts) > last_count:
                    logger.info(f"Scroll {scroll_num}: {len(collected_posts)} posts collected")
                    last_count = len(collected_posts)
                    no_new_count = 0
                else:
                    no_new_count += 1
                    if no_new_count >= 5:
                        logger.info(f"No new content after {scroll_num} scrolls, stopping")
                        break

            logger.info(f"Collected {len(collected_posts)} posts via GraphQL")

            if limit:
                collected_posts = collected_posts[:limit]

            return collected_posts

        except Exception as e:
            logger.error(f"Error during fetch: {e}")
            raise

        finally:
            await page.close()
            logger.info("Page closed")

    async def _process_response(
        self, response: Response, posts: list[SavedPost], seen_ids: set[str]
    ) -> None:
        """Process a GraphQL response and add new posts."""
        try:
            data = await response.json()
            new_posts = self._parse_graphql_response(data)
            for post in new_posts:
                if post.id not in seen_ids:
                    seen_ids.add(post.id)
                    posts.append(post)
        except Exception as e:
            logger.warning(f"Error processing response: {e}")

    def _parse_graphql_response(self, data: dict) -> list[SavedPost]:
        """Extract tweets from X's GraphQL bookmark response."""
        posts = []

        try:
            # Navigate the GraphQL response structure
            timeline = data.get("data", {}).get("bookmark_timeline_v2", {}).get("timeline", {})
            instructions = timeline.get("instructions", [])

            for instruction in instructions:
                entries = instruction.get("entries", [])
                for entry in entries:
                    try:
                        content = entry.get("content", {})
                        item_content = content.get("itemContent", {})
                        tweet_results = item_content.get("tweet_results", {})
                        result = tweet_results.get("result", {})

                        if not result:
                            continue

                        # Handle tweets wrapped in "tweet" field (for retweets/quoted)
                        if "tweet" in result:
                            result = result["tweet"]

                        legacy = result.get("legacy", {})
                        core = result.get("core", {})
                        user_results = core.get("user_results", {}).get("result", {})
                        # User info is now in user_results.core, not user_results.legacy
                        user_core = user_results.get("core", {})
                        user_avatar = user_results.get("avatar", {})

                        tweet_id = result.get("rest_id")
                        if not tweet_id:
                            continue

                        # Extract author info from user_results.core
                        username = user_core.get("screen_name", "")
                        display_name = user_core.get("name", username)
                        avatar_url = user_avatar.get("image_url")

                        author = Author(
                            id=user_results.get("rest_id", username),
                            username=username,
                            display_name=display_name,
                            avatar_url=avatar_url,
                            platform="x",
                        )

                        # Extract content
                        full_text = legacy.get("full_text", "")

                        # Extract timestamp
                        created_at_str = legacy.get("created_at", "")
                        try:
                            created_at = datetime.strptime(
                                created_at_str, "%a %b %d %H:%M:%S %z %Y"
                            )
                        except ValueError:
                            created_at = datetime.now()

                        # Extract media
                        media_list = []
                        entities = legacy.get("extended_entities", legacy.get("entities", {}))
                        for media_item in entities.get("media", []):
                            media_type = media_item.get("type", "photo")
                            if media_type == "photo":
                                media_list.append(Media(
                                    type="image",
                                    url=media_item.get("media_url_https", ""),
                                ))
                            elif media_type in ("video", "animated_gif"):
                                media_list.append(Media(
                                    type="video",
                                    url=media_item.get("media_url_https", ""),
                                    thumbnail_url=media_item.get("media_url_https"),
                                ))

                        # Extract metrics
                        metrics = XMetadata(
                            retweet_count=legacy.get("retweet_count", 0),
                            like_count=legacy.get("favorite_count", 0),
                            reply_count=legacy.get("reply_count", 0),
                            quote_count=legacy.get("quote_count", 0),
                        )

                        post = SavedPost(
                            id=tweet_id,
                            platform="x",
                            author=author,
                            content=full_text,
                            url=f"https://x.com/{username}/status/{tweet_id}",
                            created_at=created_at,
                            media=media_list,
                            metadata=metrics.model_dump(),
                        )
                        posts.append(post)

                    except Exception as e:
                        logger.warning(f"Error parsing tweet entry: {e}")
                        continue

        except Exception as e:
            logger.warning(f"Error parsing GraphQL response: {e}")

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
