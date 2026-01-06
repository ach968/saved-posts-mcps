"""X (Twitter) bookmarks scraper using Playwright."""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

from playwright.async_api import BrowserContext

from src.common.fuzzy_search import fuzzy_search
from src.common.models import SavedPost
from src.common.playwright_scraper import PlaywrightScraper
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


class XScraper(PlaywrightScraper):
    """Scraper for X.com bookmarks using Playwright."""

    X_COOKIE_DOMAINS = [".x.com", "x.com", ".twitter.com", "twitter.com"]

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
        super().__init__(
            cookies_file=cookies_file,
            cookies_list=cookies_list,
            cookie_domains=self.X_COOKIE_DOMAINS,
            target_domain=".x.com",
            headless=headless,
            env_var_name="X_COOKIES",
        )

    async def _fetch_graphql_bookmarks_with_headers(
        self,
        context: BrowserContext,
        headers: dict,
        cursor: Optional[str] = None,
        count: int = 800,
    ) -> dict:
        """Fetch a single page of bookmarks using captured headers."""
        variables = {"count": count, "includePromotedContent": True}
        if cursor:
            variables["cursor"] = cursor

        params = {
            "variables": json.dumps(variables),
            "features": json.dumps(GRAPHQL_FEATURES),
        }
        url = f"{GRAPHQL_ENDPOINT}?{urlencode(params)}"

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

        context = await self._get_context()
        page = await self._create_page(block_resources=True)

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
            logger.info(f"Navigating to {BOOKMARKS_URL} to capture headers")
            await page.goto(BOOKMARKS_URL, wait_until="domcontentloaded", timeout=60000)

            if "login" in page.url.lower():
                logger.error("Redirected to login page - cookies may be invalid")
                return []

            # Wait for the initial GraphQL request to be captured
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
        queries: list[str],
        match_all: bool = True,
        fuzzy_threshold: int = 2,
        limit: Optional[int] = None,
    ) -> list[SavedPost]:
        """
        Search through bookmarks with fuzzy matching.

        Args:
            posts: List of posts to search through
            queries: List of search terms
            match_all: If True, all queries must match (AND). If False, any match (OR).
            fuzzy_threshold: Max edit distance for fuzzy matching (0 disables fuzzy)
            limit: Maximum results

        Returns:
            Filtered list of matching posts
        """
        results = [
            p
            for p in posts
            if fuzzy_search(p.content, queries, match_all, fuzzy_threshold)
        ]

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
