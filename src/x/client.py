import asyncio
from datetime import datetime
from typing import AsyncIterator, Optional

import httpx

from src.common.models import Author, Media, SavedPost, XMetadata
from src.x.auth import XAuthHandler

X_API_BASE = "https://api.twitter.com/2"


class XClient:
    """Client for interacting with the X (Twitter) API v2."""

    def __init__(self, auth_handler: XAuthHandler):
        self.auth = auth_handler
        self._user_id: Optional[str] = None

    async def _get_headers(self) -> dict[str, str]:
        """Get authorization headers with a valid token."""
        token = await self.auth.get_valid_token()
        return {"Authorization": f"Bearer {token}"}

    async def get_me(self) -> dict:
        """Get the authenticated user's information."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{X_API_BASE}/users/me",
                headers=await self._get_headers(),
                params={"user.fields": "id,username,name,profile_image_url"},
            )
            response.raise_for_status()
            return response.json()["data"]

    async def get_user_id(self) -> str:
        """Get the authenticated user's ID (cached)."""
        if not self._user_id:
            user = await self.get_me()
            self._user_id = user["id"]
        return self._user_id

    async def get_bookmarks_page(
        self,
        pagination_token: Optional[str] = None,
        max_results: int = 100,
    ) -> dict:
        """
        Fetch a single page of bookmarks.

        Args:
            pagination_token: Token for pagination
            max_results: Number of results per page (max 100)

        Returns:
            Raw API response with data, includes, and meta
        """
        user_id = await self.get_user_id()

        params = {
            "max_results": min(max_results, 100),
            "tweet.fields": "id,text,created_at,author_id,attachments,public_metrics,conversation_id",
            "expansions": "author_id,attachments.media_keys",
            "user.fields": "id,username,name,profile_image_url",
            "media.fields": "type,url,preview_image_url",
        }

        if pagination_token:
            params["pagination_token"] = pagination_token

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{X_API_BASE}/users/{user_id}/bookmarks",
                headers=await self._get_headers(),
                params=params,
            )
            response.raise_for_status()
            return response.json()

    async def get_all_bookmarks(
        self,
        limit: Optional[int] = None,
    ) -> AsyncIterator[SavedPost]:
        """
        Iterate through all bookmarks, handling pagination.

        Args:
            limit: Maximum number of bookmarks to fetch (None = all, max 800)

        Yields:
            SavedPost objects for each bookmark
        """
        pagination_token = None
        count = 0
        max_count = limit or 800  # X API caps at 800 bookmarks

        while count < max_count:
            page_size = min(100, max_count - count)
            response = await self.get_bookmarks_page(
                pagination_token=pagination_token,
                max_results=page_size,
            )

            # Build lookup maps for includes
            users_map = {}
            media_map = {}

            if "includes" in response:
                for user in response["includes"].get("users", []):
                    users_map[user["id"]] = user
                for media in response["includes"].get("media", []):
                    media_map[media["media_key"]] = media

            # Process tweets
            for tweet in response.get("data", []):
                saved_post = self._parse_tweet(tweet, users_map, media_map)
                yield saved_post
                count += 1

                if count >= max_count:
                    break

            # Check for more pages
            meta = response.get("meta", {})
            pagination_token = meta.get("next_token")
            if not pagination_token:
                break

            # Respect rate limits
            await asyncio.sleep(0.1)

    def _parse_tweet(
        self,
        tweet: dict,
        users_map: dict,
        media_map: dict,
    ) -> SavedPost:
        """Parse a tweet into a SavedPost model."""
        author_data = users_map.get(tweet["author_id"], {})

        author = Author(
            id=tweet["author_id"],
            username=author_data.get("username", "unknown"),
            display_name=author_data.get("name", "Unknown"),
            avatar_url=author_data.get("profile_image_url"),
            platform="x",
        )

        # Parse media attachments
        media_list = []
        if "attachments" in tweet and "media_keys" in tweet["attachments"]:
            for media_key in tweet["attachments"]["media_keys"]:
                media_data = media_map.get(media_key, {})
                if media_data:
                    media_type = media_data.get("type", "image")
                    if media_type == "photo":
                        media_type = "image"
                    elif media_type == "animated_gif":
                        media_type = "gif"

                    media_list.append(
                        Media(
                            type=media_type,
                            url=media_data.get("url", ""),
                            thumbnail_url=media_data.get("preview_image_url"),
                        )
                    )

        # Parse metrics
        metrics = tweet.get("public_metrics", {})
        x_metadata = XMetadata(
            retweet_count=metrics.get("retweet_count", 0),
            like_count=metrics.get("like_count", 0),
            reply_count=metrics.get("reply_count", 0),
            quote_count=metrics.get("quote_count", 0),
            conversation_id=tweet.get("conversation_id"),
        )

        return SavedPost(
            id=tweet["id"],
            platform="x",
            author=author,
            content=tweet["text"],
            url=f"https://twitter.com/{author.username}/status/{tweet['id']}",
            created_at=datetime.fromisoformat(tweet["created_at"].replace("Z", "+00:00")),
            media=media_list,
            metadata=x_metadata.model_dump(),
        )

    async def search_bookmarks(
        self,
        query: str,
        limit: Optional[int] = None,
    ) -> list[SavedPost]:
        """
        Search through bookmarks by keyword.

        Note: X API doesn't support server-side filtering of bookmarks,
        so we fetch all and filter client-side.

        Args:
            query: Search term to look for in tweet text
            limit: Maximum results to return

        Returns:
            List of matching SavedPost objects
        """
        results = []
        query_lower = query.lower()

        async for post in self.get_all_bookmarks():
            if query_lower in post.content.lower():
                results.append(post)
                if limit and len(results) >= limit:
                    break

        return results
