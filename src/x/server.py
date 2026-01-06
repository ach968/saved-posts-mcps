from typing import Optional

from mcp.server.fastmcp import FastMCP

from src.x.scraper import XScraper
from src.x.utils import simplify_post

mcp = FastMCP("X Bookmarks Server")

_scraper: Optional[XScraper] = None


def get_scraper() -> XScraper:
    """Get or create the X scraper."""
    global _scraper
    if _scraper is None:
        _scraper = XScraper.from_env()
    return _scraper


@mcp.tool()
async def get_x_bookmarks(limit: int = 10) -> list[dict]:
    """
    Fetch the user's bookmarked tweets from X (Twitter) via web scraping.

    Args:
        limit: Maximum number of bookmarks to return

    Returns:
        List of bookmarked tweets with author info and metadata
    """
    scraper = get_scraper()

    bookmarks = await scraper.get_bookmarks()

    bookmarks = bookmarks[:limit] if limit else bookmarks

    return [simplify_post(post) for post in bookmarks]


@mcp.tool()
async def search_x_bookmarks(
    queries: list[str],
    match_all: bool = True,
    fuzzy_threshold: int = 2,
) -> list[dict]:
    """
    Search through bookmarked tweets with fuzzy matching.

    Always fetches fresh bookmarks from X.com to ensure complete search results.

    Args:
        queries: List of search terms to look for in tweet text
        match_all: If True, all queries must match (AND). If False, any match (OR).
        fuzzy_threshold: Max edit distance for fuzzy matching (0 disables fuzzy)

    Returns:
        List of matching bookmarked tweets
    """
    scraper = get_scraper()

    bookmarks = await scraper.get_bookmarks()

    results = scraper.search_bookmarks(
        bookmarks,
        queries=queries,
        match_all=match_all,
        fuzzy_threshold=fuzzy_threshold,
    )

    return [simplify_post(post) for post in results]


def main():
    """Entry point for the X MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
