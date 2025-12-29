import json
from typing import Optional

from mcp.server.fastmcp import FastMCP

from src.x.scraper import XScraper

mcp = FastMCP("X Bookmarks Server")

# Global scraper instance and cached bookmarks
_scraper: Optional[XScraper] = None
_cached_bookmarks: Optional[list] = None


def get_scraper() -> XScraper:
    """Get or create the X scraper."""
    global _scraper
    if _scraper is None:
        _scraper = XScraper.from_env()
    return _scraper


@mcp.tool()
async def get_x_bookmarks(limit: int = 100, refresh: bool = False) -> str:
    """
    Fetch the user's bookmarked tweets from X (Twitter) via web scraping.

    Args:
        limit: Maximum number of bookmarks to return (default 100)
        refresh: Force refresh from X.com instead of using cache

    Returns:
        JSON array of bookmarked tweets with author info and metadata
    """
    global _cached_bookmarks

    scraper = get_scraper()

    if refresh or _cached_bookmarks is None:
        _cached_bookmarks = await scraper.get_bookmarks()

    bookmarks = _cached_bookmarks[:limit] if limit else _cached_bookmarks

    return json.dumps([post.model_dump(mode="json") for post in bookmarks], indent=2)


@mcp.tool()
async def search_x_bookmarks(query: str, limit: int = 50) -> str:
    """
    Search through bookmarked tweets by keyword.

    Args:
        query: Search term to look for in tweet text
        limit: Maximum number of results to return (default 50)

    Returns:
        JSON array of matching bookmarked tweets
    """
    global _cached_bookmarks

    scraper = get_scraper()

    # Ensure we have bookmarks cached
    if _cached_bookmarks is None:
        _cached_bookmarks = await scraper.get_bookmarks()

    results = scraper.search_bookmarks(_cached_bookmarks, query=query, limit=limit)

    return json.dumps([post.model_dump(mode="json") for post in results], indent=2)


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

    return json.dumps([post.model_dump(mode="json") for post in _cached_bookmarks], indent=2)


def main():
    """Entry point for the X MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
