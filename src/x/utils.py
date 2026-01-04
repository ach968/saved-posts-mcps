"""Shared utility functions for the X scraper."""

import logging
import re
from datetime import datetime

from src.common.models import Author, Media, SavedPost, XMetadata

logger = logging.getLogger(__name__)


def clean_text(text: str, max_length: int = 280) -> str:
    """Clean text for output: normalize unicode and optionally truncate."""
    # Replace common unicode characters with ASCII equivalents
    replacements = {
        "\u2019": "'",  # right single quote
        "\u2018": "'",  # left single quote
        "\u201c": '"',  # left double quote
        "\u201d": '"',  # right double quote
        "\u2014": "-",  # em dash
        "\u2013": "-",  # en dash
        "\u2026": "...",  # ellipsis
        "\u00b0": "°",  # degree (keep as-is, it's readable)
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    # Truncate if needed
    if max_length and len(text) > max_length:
        text = text[: max_length - 3] + "..."

    return text


def simplify_post(post: SavedPost, max_content_length: int = 280) -> dict:
    """Convert a SavedPost to a simplified dict for LLM consumption."""
    result = {
        "id": post.id,
        "author": post.author.username,
        "display_name": post.author.display_name,
        "content": clean_text(post.content, max_content_length),
        "url": post.url,
        "created_at": post.created_at.isoformat().replace("+00:00", "Z"),
    }

    # Only include media URLs if present
    if post.media:
        result["media"] = [m.url for m in post.media]

    # Only include non-zero engagement metrics
    metrics = {}
    if post.metadata.get("retweet_count"):
        metrics["retweets"] = post.metadata["retweet_count"]
    if post.metadata.get("like_count"):
        metrics["likes"] = post.metadata["like_count"]
    if post.metadata.get("reply_count"):
        metrics["replies"] = post.metadata["reply_count"]
    if metrics:
        result["metrics"] = metrics

    return result


def parse_count(text: str) -> int:
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


def normalize_text(text: str) -> str:
    """Normalize text by collapsing whitespace and trimming."""
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r" \n", " ", text)
    return text.strip()


def parse_graphql_response(data: dict) -> list[SavedPost]:
    """Extract tweets from X's GraphQL bookmark response."""
    posts = []

    try:
        timeline = (
            data.get("data", {}).get("bookmark_timeline_v2", {}).get("timeline", {})
        )
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
                    user_core = user_results.get("core", {})
                    user_avatar = user_results.get("avatar", {})

                    tweet_id = result.get("rest_id")
                    if not tweet_id:
                        continue

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

                    full_text = legacy.get("full_text", "")

                    created_at_str = legacy.get("created_at", "")
                    try:
                        created_at = datetime.strptime(
                            created_at_str, "%a %b %d %H:%M:%S %z %Y"
                        )
                    except ValueError:
                        created_at = datetime.now()

                    media_list = []
                    entities = legacy.get(
                        "extended_entities", legacy.get("entities", {})
                    )
                    for media_item in entities.get("media", []):
                        media_type = media_item.get("type", "photo")
                        if media_type == "photo":
                            media_list.append(
                                Media(
                                    type="image",
                                    url=media_item.get("media_url_https", ""),
                                )
                            )
                        elif media_type in ("video", "animated_gif"):
                            media_list.append(
                                Media(
                                    type="video",
                                    url=media_item.get("media_url_https", ""),
                                    thumbnail_url=media_item.get("media_url_https"),
                                )
                            )

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
