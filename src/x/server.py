import json
from typing import Optional

from mcp.server.fastmcp import FastMCP

from src.common.models import SavedPost
from src.x.scraper import XScraper

mcp = FastMCP("X Bookmarks Server")

# Global scraper instance and cached bookmarks
_scraper: Optional[XScraper] = None
_cached_bookmarks: Optional[list] = None


def _simplify_post(post: SavedPost) -> dict:
    """Convert a SavedPost to a simplified dict for LLM consumption."""
    result = {
        "id": post.id,
        "author": post.author.username,
        "display_name": post.author.display_name,
        "content": post.content,
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


def get_scraper() -> XScraper:
    """Get or create the X scraper."""
    global _scraper
    if _scraper is None:
        _scraper = XScraper.from_env()
    return _scraper


@mcp.tool()
async def get_x_bookmarks(limit: int = 250, refresh: bool = False) -> str:
    """
    Fetch the user's bookmarked tweets from X (Twitter) via web scraping.

    Args:
        limit: Maximum number of bookmarks to return (default 250)
        refresh: Force refresh from X.com instead of using cache

    Returns:
        JSON array of bookmarked tweets with author info and metadata
    """
    global _cached_bookmarks

    scraper = get_scraper()

    if refresh or _cached_bookmarks is None:
        _cached_bookmarks = await scraper.get_bookmarks()

    bookmarks = _cached_bookmarks[:limit] if limit else _cached_bookmarks

    return json.dumps([_simplify_post(post) for post in bookmarks], indent=2)


@mcp.tool()
async def search_x_bookmarks(query: str, limit: int = 250) -> str:
    """
    Search through bookmarked tweets by keyword.

    Always fetches fresh bookmarks from X.com to ensure complete search results.

    Args:
        query: Search term to look for in tweet text
        limit: Maximum number of results to return (default 250)

    Returns:
        JSON array of matching bookmarked tweets
    """
    global _cached_bookmarks

    scraper = get_scraper()

    # Always fetch fresh for search to ensure complete results
    _cached_bookmarks = await scraper.get_bookmarks()

    results = scraper.search_bookmarks(_cached_bookmarks, query=query, limit=limit)

    return json.dumps([_simplify_post(post) for post in results], indent=2)


@mcp.tool()
async def refresh_x_bookmarks() -> str:
    """
    Force refresh bookmarks from X.com.

    Use this after bookmarking new tweets to update the cache.

    Returns:
        JSON object with count of bookmarks fetched
    """
    global _cached_bookmarks

    scraper = get_scraper()
    _cached_bookmarks = await scraper.get_bookmarks()

    return json.dumps({
        "status": "success",
        "count": len(_cached_bookmarks),
        "message": f"Refreshed {len(_cached_bookmarks)} bookmarks from X.com",
    }, indent=2)


@mcp.resource("x://bookmarks")
async def list_bookmarks() -> str:
    """List all bookmarked tweets as a resource."""
    global _cached_bookmarks

    scraper = get_scraper()

    if _cached_bookmarks is None:
        _cached_bookmarks = await scraper.get_bookmarks()

    return json.dumps([_simplify_post(post) for post in _cached_bookmarks], indent=2)


def main():
    """Entry point for the X MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
