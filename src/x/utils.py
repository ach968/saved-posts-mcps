"""Shared utility functions for the X scraper."""

import re

from src.common.models import SavedPost


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
