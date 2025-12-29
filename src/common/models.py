from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

Platform = Literal["x", "reddit", "instagram", "tiktok", "youtube"]
MediaType = Literal["image", "video", "gif"]


class Author(BaseModel):
    """Represents the author of a saved post."""

    id: str
    username: str
    display_name: str
    avatar_url: Optional[str] = None
    platform: Platform


class Media(BaseModel):
    """Represents media attached to a post."""

    type: MediaType
    url: str
    thumbnail_url: Optional[str] = None


class SavedPost(BaseModel):
    """Unified model for a saved post across all platforms."""

    id: str
    platform: Platform
    author: Author
    content: str
    url: str
    created_at: datetime
    saved_at: Optional[datetime] = None
    media: list[Media] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class RedditMetadata(BaseModel):
    """Reddit-specific metadata for saved posts."""

    subreddit: str
    subreddit_id: str
    score: int
    num_comments: int
    is_self: bool
    link_flair_text: Optional[str] = None
    over_18: bool = False


class XMetadata(BaseModel):
    """X/Twitter-specific metadata for saved bookmarks."""

    retweet_count: int = 0
    like_count: int = 0
    reply_count: int = 0
    quote_count: int = 0
    is_retweet: bool = False
    conversation_id: Optional[str] = None
