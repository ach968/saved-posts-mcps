import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Optional

from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
)

from src.common.models import SavedPost
from src.x.utils import parse_graphql_response

logging.basicConfig(
    level=logging.INFO,
    format="[XScraper] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

BOOKMARKS_URL = "https://x.com/i/bookmarks"
GRAPHQL_ENDPOINT = "https://x.com/i/api/graphql/E6jlrZG4703s0mcA9DfNKQ/Bookmarks"

# Feature flags
GRAPHQL_FEATURES = {
    "rweb_video_screen_enabled": False,
    "profile_label_improvements_pcf_label_in_post_enabled": True,
    "responsive_web_profile_redirect_enabled": False,
    "rweb_tipjar_consumption_enabled": True,
    "verified_phone_label_enabled": False,
    "creator_subscriptions_tweet_preview_api_enabled": True,
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "premium_content_api_read_enabled": False,
    "communities_web_enable_tweet_community_results_fetch": True,
    "c9s_tweet_anatomy_moderator_badge_enabled": True,
    "responsive_web_grok_analyze_button_fetch_trends_enabled": False,
    "responsive_web_grok_analyze_post_followups_enabled": True,
    "responsive_web_jetfuel_frame": True,
    "responsive_web_grok_share_attachment_enabled": True,
    "articles_preview_enabled": True,
    "responsive_web_edit_tweet_api_enabled": True,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
    "view_counts_everywhere_api_enabled": True,
    "longform_notetweets_consumption_enabled": True,
    "responsive_web_twitter_article_tweet_consumption_enabled": True,
    "tweet_awards_web_tipping_enabled": False,
    "responsive_web_grok_show_grok_translated_post": True,
    "responsive_web_grok_analysis_button_from_backend": True,
    "creator_subscriptions_quote_tweet_preview_enabled": False,
    "freedom_of_speech_not_reach_fetch_enabled": True,
    "standardized_nudges_misinfo": True,
    "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
    "longform_notetweets_rich_text_read_enabled": True,
    "longform_notetweets_inline_media_enabled": True,
    "responsive_web_grok_image_annotation_enabled": True,
    "responsive_web_grok_imagine_annotation_enabled": True,
    "responsive_web_grok_community_note_auto_translation_is_enabled": False,
    "responsive_web_enhance_cards_enabled": False,
}


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

        try:
            data = json.loads(content)
            if isinstance(data, list):
                self.cookies = data
            elif isinstance(data, dict):
                self.cookies = [
                    {"name": k, "value": v, "domain": ".x.com", "path": "/"}
                    for k, v in data.items()
                ]
            return
        except json.JSONDecodeError:
            pass

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
            await self._context.add_cookies(self.cookies)
        return self._context

    async def _fetch_graphql_bookmarks_with_headers(
        self,
        context: BrowserContext,
        headers: dict,
        cursor: Optional[str] = None,
        count: int = 800, # 800 from X API default limit
    ) -> dict:
        """Fetch a single page of bookmarks using captured headers."""
        from urllib.parse import urlencode

        variables = {"count": count, "includePromotedContent": True}
        if cursor:
            variables["cursor"] = cursor

        params = {
            "variables": json.dumps(variables),
            "features": json.dumps(GRAPHQL_FEATURES),
        }
        url = f"{GRAPHQL_ENDPOINT}?{urlencode(params)}"

        # Use Playwright's request context with the captured headers
        response = await context.request.get(url, headers=headers)

        if not response.ok:
            raise Exception(f"HTTP {response.status}: {response.status_text}")

        return await response.json()

    def _extract_cursor(self, data: dict) -> Optional[str]:
        """Extract the pagination cursor from a GraphQL response."""
        try:
            timeline = (
                data.get("data", {}).get("bookmark_timeline_v2", {}).get("timeline", {})
            )
            instructions = timeline.get("instructions", [])

            for instruction in instructions:
                entries = instruction.get("entries", [])
                for entry in entries:
                    entry_id = entry.get("entryId", "")
                    if entry_id.startswith("cursor-bottom-"):
                        return entry.get("content", {}).get("value")
        except Exception as e:
            logger.warning(f"Error extracting cursor: {e}")
        return None

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
        max_pages: int = 50,
    ) -> list[SavedPost]:
        """
        Fetch bookmarked tweets using a hybrid approach:
        1. Use Playwright to load the page and capture GraphQL request headers
        2. Use captured headers to make direct API calls

        Args:
            limit: Maximum number of bookmarks to return
            max_pages: Safety limit for maximum API pages to fetch (default 50)

        Returns:
            List of SavedPost objects
        """
        logger.info("Starting get_bookmarks (hybrid approach)")
        logger.info(f"Loaded {len(self.cookies)} cookies")

        context = await self._get_context()
        page = await context.new_page()

        captured_headers: dict = {}

        async def capture_graphql_headers(request):
            nonlocal captured_headers
            if (
                "Bookmarks" in request.url
                and "graphql" in request.url
                and not captured_headers
            ):
                captured_headers = dict(request.headers)
                logger.info("Captured GraphQL request headers")

        page.on("request", capture_graphql_headers)

        try:
            # Block unnecessary resources for speed
            await page.route(
                re.compile(r"\.(png|jpg|jpeg|gif|webp|woff|woff2)$"),
                lambda route: route.abort(),
            )

            logger.info(f"Navigating to {BOOKMARKS_URL} to capture headers")
            await page.goto(BOOKMARKS_URL, wait_until="domcontentloaded", timeout=60000)

            if "login" in page.url.lower():
                logger.error("Redirected to login page - cookies may be invalid")
                return []

            # Wait for the initial GraphQL request to be captured, up to 5 seconds
            for _ in range(50):
                if captured_headers:
                    break
                await page.wait_for_timeout(100)

            if not captured_headers:
                logger.error("Failed to capture GraphQL headers")
                return []

            logger.info("Headers captured, making direct API calls")

            collected_posts: list[SavedPost] = []
            seen_ids: set[str] = set()
            cursor: Optional[str] = None
            page_num = 0

            while page_num < max_pages:
                page_num += 1

                try:
                    logger.info(f"Fetching page {page_num}...")
                    data = await self._fetch_graphql_bookmarks_with_headers(
                        context, captured_headers, cursor
                    )

                    # Parse posts from response
                    new_posts = parse_graphql_response(data)
                    added_count = 0

                    for post in new_posts:
                        if post.id not in seen_ids:
                            seen_ids.add(post.id)
                            collected_posts.append(post)
                            added_count += 1
                    if added_count == 0:
                        logger.info("No new posts found on this page, stopping.")
                        break

                    logger.info(
                        f"Page {page_num}: added {added_count} new posts (total: {len(collected_posts)})"
                    )

                    if limit and len(collected_posts) >= limit:
                        logger.info(f"Reached limit of {limit} posts")
                        break

                    next_cursor = self._extract_cursor(data)
                    if not next_cursor:
                        logger.info("No more pages available")
                        break

                    cursor = next_cursor

                except Exception as e:
                    logger.error(f"Error fetching page {page_num}: {e}")
                    break

            logger.info(f"Collected {len(collected_posts)} posts total")

            if limit:
                collected_posts = collected_posts[:limit]

            return collected_posts

        finally:
            await page.close()

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

        default_path = Path.home() / ".x_cookies.txt"
        if default_path.exists():
            return cls(cookies_file=default_path, headless=headless)

        raise ValueError(
            "No cookies found. Set X_COOKIES_FILE to path of cookies file, "
            "or X_COOKIES to a JSON array of cookies, "
            "or place cookies at ~/.x_cookies.txt"
        )
