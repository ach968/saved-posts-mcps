import os
from datetime import datetime, timezone
from typing import Iterator, Literal, Optional

import praw
from praw.models import Comment, Submission

from src.common.models import Author, Media, RedditMetadata, SavedPost


class RedditClient:
    """Client for interacting with the Reddit API via PRAW."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        username: str,
        password: str,
        user_agent: str,
    ):
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            username=username,
            password=password,
            user_agent=user_agent,
        )
        self._username = username

    def get_me(self) -> dict:
        """Get the authenticated user's information."""
        user = self.reddit.user.me()
        return {
            "id": user.id,
            "username": user.name,
            "display_name": getattr(user, "subreddit", {}).get("title", user.name),
            "avatar_url": getattr(user, "icon_img", None),
            "karma": user.link_karma + user.comment_karma,
            "created_utc": user.created_utc,
        }

    def get_saved(
        self,
        limit: Optional[int] = None,
        filter_type: Optional[Literal["posts", "comments"]] = None,
    ) -> Iterator[SavedPost]:
        """
        Iterate through saved items.

        Args:
            limit: Maximum number of items to fetch (None = all, max ~1000)
            filter_type: Filter to only "posts" or "comments" (None = both)

        Yields:
            SavedPost objects for each saved item
        """
        saved_items = self.reddit.user.me().saved(limit=limit)

        for item in saved_items:
            if isinstance(item, Submission):
                if filter_type == "comments":
                    continue
                yield self._parse_submission(item)
            elif isinstance(item, Comment):
                if filter_type == "posts":
                    continue
                yield self._parse_comment(item)

    def get_saved_posts(self, limit: Optional[int] = None) -> Iterator[SavedPost]:
        """Get only saved posts (submissions)."""
        return self.get_saved(limit=limit, filter_type="posts")

    def get_saved_comments(self, limit: Optional[int] = None) -> Iterator[SavedPost]:
        """Get only saved comments."""
        return self.get_saved(limit=limit, filter_type="comments")

    def search_saved(
        self,
        query: str,
        limit: Optional[int] = None,
        subreddit: Optional[str] = None,
    ) -> list[SavedPost]:
        """
        Search through saved items.

        Args:
            query: Search term to look for in content
            limit: Maximum results to return
            subreddit: Filter by subreddit name (optional)

        Returns:
            List of matching SavedPost objects
        """
        results = []
        query_lower = query.lower()
        subreddit_lower = subreddit.lower() if subreddit else None

        for item in self.get_saved():
            # Filter by subreddit if specified
            if subreddit_lower:
                item_subreddit = item.metadata.get("subreddit", "").lower()
                if item_subreddit != subreddit_lower:
                    continue

            # Search in content
            if query_lower in item.content.lower():
                results.append(item)
                if limit and len(results) >= limit:
                    break

        return results

    def _parse_submission(self, submission: Submission) -> SavedPost:
        """Parse a Reddit submission into a SavedPost model."""
        author_name = submission.author.name if submission.author else "[deleted]"
        author_id = submission.author.id if submission.author else "deleted"

        author = Author(
            id=author_id,
            username=author_name,
            display_name=author_name,
            avatar_url=None,
            platform="reddit",
        )

        # Parse media
        media_list = []
        if hasattr(submission, "preview") and submission.preview:
            images = submission.preview.get("images", [])
            for img in images:
                source = img.get("source", {})
                if source.get("url"):
                    media_list.append(
                        Media(
                            type="image",
                            url=source["url"].replace("&amp;", "&"),
                            thumbnail_url=img.get("resolutions", [{}])[-1].get("url", "").replace("&amp;", "&") if img.get("resolutions") else None,
                        )
                    )

        # Handle direct image/video URLs
        if submission.url and any(submission.url.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".gif"]):
            if not media_list:
                media_type = "gif" if submission.url.endswith(".gif") else "image"
                media_list.append(Media(type=media_type, url=submission.url))

        # Content: use selftext for text posts, title + url for links
        if submission.is_self:
            content = f"{submission.title}\n\n{submission.selftext}" if submission.selftext else submission.title
        else:
            content = f"{submission.title}\n\n{submission.url}"

        metadata = RedditMetadata(
            subreddit=submission.subreddit.display_name,
            subreddit_id=submission.subreddit_id,
            score=submission.score,
            num_comments=submission.num_comments,
            is_self=submission.is_self,
            link_flair_text=submission.link_flair_text,
            over_18=submission.over_18,
        )

        return SavedPost(
            id=submission.id,
            platform="reddit",
            author=author,
            content=content,
            url=f"https://reddit.com{submission.permalink}",
            created_at=datetime.fromtimestamp(submission.created_utc, tz=timezone.utc),
            media=media_list,
            metadata=metadata.model_dump(),
        )

    def _parse_comment(self, comment: Comment) -> SavedPost:
        """Parse a Reddit comment into a SavedPost model."""
        author_name = comment.author.name if comment.author else "[deleted]"
        author_id = comment.author.id if comment.author else "deleted"

        author = Author(
            id=author_id,
            username=author_name,
            display_name=author_name,
            avatar_url=None,
            platform="reddit",
        )

        # Get parent submission info for context
        submission = comment.submission

        metadata = RedditMetadata(
            subreddit=comment.subreddit.display_name,
            subreddit_id=comment.subreddit_id,
            score=comment.score,
            num_comments=0,
            is_self=True,
            over_18=submission.over_18 if submission else False,
        )

        # Include submission title for context
        content = f"[Comment on: {submission.title}]\n\n{comment.body}"

        return SavedPost(
            id=comment.id,
            platform="reddit",
            author=author,
            content=content,
            url=f"https://reddit.com{comment.permalink}",
            created_at=datetime.fromtimestamp(comment.created_utc, tz=timezone.utc),
            media=[],
            metadata=metadata.model_dump(),
        )

    @classmethod
    def from_env(cls) -> "RedditClient":
        """Create a RedditClient from environment variables."""
        client_id = os.environ.get("REDDIT_CLIENT_ID")
        client_secret = os.environ.get("REDDIT_CLIENT_SECRET")
        username = os.environ.get("REDDIT_USERNAME")
        password = os.environ.get("REDDIT_PASSWORD")
        user_agent = os.environ.get(
            "REDDIT_USER_AGENT",
            f"saved-posts-aggregator:v0.1.0 (by /u/{username})",
        )

        if not all([client_id, client_secret, username, password]):
            raise ValueError(
                "Missing required environment variables: "
                "REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD"
            )

        return cls(
            client_id=client_id,
            client_secret=client_secret,
            username=username,
            password=password,
            user_agent=user_agent,
        )
