"""Reddit saved posts scraper using Playwright."""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

from src.common.fuzzy_search import fuzzy_search
from src.common.models import Author, Media, RedditMetadata, SavedPost
from src.common.playwright_scraper import PlaywrightScraper

logging.basicConfig(
    level=logging.INFO,
    format="[RedditScraper] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

SAVED_JSON_URL = "https://www.reddit.com/user/{username}/saved.json"


class RedditScraper(PlaywrightScraper):
    """Scraper for Reddit saved posts using Playwright."""

    REDDIT_COOKIE_DOMAINS = [".reddit.com", "reddit.com"]

    def __init__(
        self,
        username: str,
        cookies_file: Optional[Path] = None,
        cookies_list: Optional[list[dict]] = None,
        headless: bool = True,
    ):
        """
        Initialize the scraper with authentication cookies.

        Args:
            username: Reddit username for building saved URL
            cookies_file: Path to a cookies file (JSON or Netscape format)
            cookies_list: List of cookie dicts (alternative to file)
            headless: Run browser in headless mode
        """
        super().__init__(
            cookies_file=cookies_file,
            cookies_list=cookies_list,
            cookie_domains=self.REDDIT_COOKIE_DOMAINS,
            target_domain=".reddit.com",
            headless=headless,
            env_var_name="REDDIT_COOKIES",
        )
        self.username = username

    async def _fetch_saved_json(
        self,
        headers: dict,
        after: Optional[str] = None,
        limit: int = 100,
    ) -> dict:
        """Fetch a page of saved items using captured headers."""
        context = await self._get_context()

        url = SAVED_JSON_URL.format(username=self.username)
        params = {"limit": str(limit), "raw_json": "1"}
        if after:
            params["after"] = after

        query = "&".join(f"{k}={v}" for k, v in params.items())
        full_url = f"{url}?{query}"

        response = await context.request.get(full_url, headers=headers)

        if not response.ok:
            raise Exception(f"HTTP {response.status}: {response.status_text}")

        return await response.json()

    async def get_saved(
        self,
        limit: Optional[int] = None,
        filter_type: Optional[Literal["posts", "comments"]] = None,
        max_pages: int = 50,
    ) -> list[SavedPost]:
        """
        Fetch saved items using a hybrid approach:
        1. Use Playwright to load the page and capture request headers
        2. Use captured headers to make direct API calls

        Args:
            limit: Maximum number of items to return
            filter_type: Filter to only "posts" or "comments" (None = both)
            max_pages: Safety limit for maximum API pages to fetch

        Returns:
            List of SavedPost objects
        """
        logger.info("Starting get_saved (hybrid approach)")

        page = await self._create_page(block_resources=True)

        captured_headers: dict = {}

        async def capture_headers(request):
            nonlocal captured_headers
            if "saved.json" in request.url and not captured_headers:
                captured_headers = dict(request.headers)
                logger.info("Captured API request headers")

        page.on("request", capture_headers)

        try:
            saved_url = SAVED_JSON_URL.format(username=self.username)
            logger.info(f"Navigating to {saved_url} to capture headers")

            await page.goto(saved_url, wait_until="domcontentloaded", timeout=60000)

            if "login" in page.url.lower() or "register" in page.url.lower():
                logger.error("Redirected to login page - cookies may be invalid")
                return []

            # Reddit's new UI doesn't always trigger .json requests immediately
            # Try to capture headers by making a test request
            for _ in range(30):
                if captured_headers:
                    break
                await page.wait_for_timeout(100)

            # If no headers captured, build minimal headers from page context
            if not captured_headers:
                logger.info("Building headers from page context")
                captured_headers = {
                    "user-agent": "Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0",
                    "accept": "application/json",
                    "accept-language": "en-US,en;q=0.5",
                }

            logger.info("Making direct API calls")

            collected_posts: list[SavedPost] = []
            seen_ids: set[str] = set()
            after: Optional[str] = None
            page_num = 0

            while page_num < max_pages:
                page_num += 1

                try:
                    logger.info(f"Fetching page {page_num}...")
                    data = await self._fetch_saved_json(captured_headers, after)

                    children = data.get("data", {}).get("children", [])
                    if not children:
                        logger.info("No more items found")
                        break

                    added_count = 0
                    for child in children:
                        kind = child.get("kind")
                        item_data = child.get("data", {})

                        # Filter by type if requested
                        if filter_type == "posts" and kind != "t3":
                            continue
                        if filter_type == "comments" and kind != "t1":
                            continue

                        item_id = item_data.get("id", "")
                        if item_id in seen_ids:
                            continue

                        seen_ids.add(item_id)

                        if kind == "t3":  # Post/submission
                            post = self._parse_submission(item_data)
                        elif kind == "t1":  # Comment
                            post = self._parse_comment(item_data)
                        else:
                            continue

                        collected_posts.append(post)
                        added_count += 1

                    logger.info(
                        f"Page {page_num}: added {added_count} items (total: {len(collected_posts)})"
                    )

                    if limit and len(collected_posts) >= limit:
                        logger.info(f"Reached limit of {limit} items")
                        break

                    # Get next page cursor
                    after = data.get("data", {}).get("after")
                    if not after:
                        logger.info("No more pages available")
                        break

                except Exception as e:
                    logger.error(f"Error fetching page {page_num}: {e}")
                    break

            logger.info(f"Collected {len(collected_posts)} items total")

            if limit:
                collected_posts = collected_posts[:limit]

            return collected_posts

        finally:
            await page.close()

    async def get_saved_posts(self, limit: Optional[int] = None) -> list[SavedPost]:
        """Get only saved posts (submissions)."""
        return await self.get_saved(limit=limit, filter_type="posts")

    async def get_saved_comments(self, limit: Optional[int] = None) -> list[SavedPost]:
        """Get only saved comments."""
        return await self.get_saved(limit=limit, filter_type="comments")

    def search_saved(
        self,
        posts: list[SavedPost],
        queries: list[str],
        match_all: bool = True,
        fuzzy_threshold: int = 2,
        limit: Optional[int] = None,
        subreddit: Optional[str] = None,
    ) -> list[SavedPost]:
        """
        Search through saved items with fuzzy matching.

        Args:
            posts: List of posts to search through
            queries: List of search terms
            match_all: If True, all queries must match (AND). If False, any match (OR).
            fuzzy_threshold: Max edit distance for fuzzy matching (0 disables fuzzy)
            limit: Maximum results to return
            subreddit: Filter by subreddit name (optional)

        Returns:
            List of matching SavedPost objects
        """
        subreddit_lower = subreddit.lower() if subreddit else None

        results = []
        for item in posts:
            # Filter by subreddit if specified
            if subreddit_lower:
                item_subreddit = item.metadata.get("subreddit", "").lower()
                if item_subreddit != subreddit_lower:
                    continue

            # Fuzzy search in content
            if fuzzy_search(item.content, queries, match_all, fuzzy_threshold):
                results.append(item)
                if limit and len(results) >= limit:
                    break

        return results

    def _parse_submission(self, data: dict) -> SavedPost:
        """Parse a Reddit submission into a SavedPost model."""
        author_name = data.get("author", "[deleted]")
        author_id = data.get("author_fullname", "deleted")

        author = Author(
            id=author_id,
            username=author_name,
            display_name=author_name,
            avatar_url=None,
            platform="reddit",
        )

        # Parse media
        media_list = []
        preview = data.get("preview", {})
        if preview:
            images = preview.get("images", [])
            for img in images:
                source = img.get("source", {})
                if source.get("url"):
                    resolutions = img.get("resolutions", [])
                    thumbnail = resolutions[-1].get("url", "") if resolutions else None
                    media_list.append(
                        Media(
                            type="image",
                            url=source["url"].replace("&amp;", "&"),
                            thumbnail_url=thumbnail.replace("&amp;", "&") if thumbnail else None,
                        )
                    )

        # Handle direct image/video URLs
        url = data.get("url", "")
        if url and any(url.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".gif"]):
            if not media_list:
                media_type = "gif" if url.endswith(".gif") else "image"
                media_list.append(Media(type=media_type, url=url))

        # Content: use selftext for text posts, title + url for links
        title = data.get("title", "")
        selftext = data.get("selftext", "")
        is_self = data.get("is_self", False)

        if is_self:
            content = f"{title}\n\n{selftext}" if selftext else title
        else:
            content = f"{title}\n\n{url}"

        subreddit = data.get("subreddit", "")
        permalink = data.get("permalink", "")

        metadata = RedditMetadata(
            subreddit=subreddit,
            subreddit_id=data.get("subreddit_id", ""),
            score=data.get("score", 0),
            num_comments=data.get("num_comments", 0),
            is_self=is_self,
            link_flair_text=data.get("link_flair_text"),
            over_18=data.get("over_18", False),
        )

        return SavedPost(
            id=data.get("id", ""),
            platform="reddit",
            author=author,
            content=content,
            url=f"https://reddit.com{permalink}",
            created_at=datetime.fromtimestamp(data.get("created_utc", 0), tz=timezone.utc),
            media=media_list,
            metadata=metadata.model_dump(),
        )

    def _parse_comment(self, data: dict) -> SavedPost:
        """Parse a Reddit comment into a SavedPost model."""
        author_name = data.get("author", "[deleted]")
        author_id = data.get("author_fullname", "deleted")

        author = Author(
            id=author_id,
            username=author_name,
            display_name=author_name,
            avatar_url=None,
            platform="reddit",
        )

        # Get parent submission title for context
        link_title = data.get("link_title", "Unknown post")
        body = data.get("body", "")
        content = f"[Comment on: {link_title}]\n\n{body}"

        subreddit = data.get("subreddit", "")
        permalink = data.get("permalink", "")

        metadata = RedditMetadata(
            subreddit=subreddit,
            subreddit_id=data.get("subreddit_id", ""),
            score=data.get("score", 0),
            num_comments=0,
            is_self=True,
            over_18=data.get("over_18", False),
        )

        return SavedPost(
            id=data.get("id", ""),
            platform="reddit",
            author=author,
            content=content,
            url=f"https://reddit.com{permalink}",
            created_at=datetime.fromtimestamp(data.get("created_utc", 0), tz=timezone.utc),
            media=[],
            metadata=metadata.model_dump(),
        )

    @classmethod
    def from_env(cls, headless: bool = True) -> "RedditScraper":
        """Create a RedditScraper from environment variables."""
        username = os.environ.get("REDDIT_USERNAME")
        if not username:
            raise ValueError("REDDIT_USERNAME environment variable is required")

        cookies_file = os.environ.get("REDDIT_COOKIES_FILE")
        if cookies_file:
            return cls(
                username=username,
                cookies_file=Path(cookies_file),
                headless=headless,
            )

        cookies_json = os.environ.get("REDDIT_COOKIES")
        if cookies_json:
            return cls(
                username=username,
                cookies_list=json.loads(cookies_json),
                headless=headless,
            )

        default_path = Path.home() / ".reddit_cookies.txt"
        if default_path.exists():
            return cls(
                username=username,
                cookies_file=default_path,
                headless=headless,
            )

        raise ValueError(
            "No cookies found. Set REDDIT_COOKIES_FILE to path of cookies file, "
            "or REDDIT_COOKIES to a JSON array of cookies, "
            "or place cookies at ~/.reddit_cookies.txt"
        )
