import json
import os
from typing import Optional

from mcp.server.fastmcp import FastMCP

from src.reddit.scraper import RedditScraper

_TRANSPORT = os.getenv("MCP_TRANSPORT", "stdio")


def _create_mcp() -> FastMCP:
    """Create FastMCP instance with HTTP config if MCP_TRANSPORT=http."""
    if _TRANSPORT == "http":
        return FastMCP(
            "Reddit Saved Posts Server",
            host="0.0.0.0",
            port=int(os.getenv("MCP_PORT", "8000")),
        )
    return FastMCP("Reddit Saved Posts Server")


mcp = _create_mcp()

# Global scraper instance (initialized on first use)
_scraper: Optional[RedditScraper] = None
# Cache for saved items to avoid refetching for search
_saved_cache: list = []


def get_scraper() -> RedditScraper:
    """Get or create the Reddit scraper."""
    global _scraper
    if _scraper is None:
        _scraper = RedditScraper.from_env()
    return _scraper


async def _ensure_cache(limit: Optional[int] = None) -> list:
    """Ensure saved items are cached and return them."""
    global _saved_cache
    if not _saved_cache:
        scraper = get_scraper()
        _saved_cache = await scraper.get_saved(limit=limit)
    return _saved_cache


@mcp.tool()
async def get_reddit_saved(limit: int = 100) -> str:
    """
    Fetch the user's saved posts and comments from Reddit.

    Args:
        limit: Maximum number of items to fetch (default 100)

    Returns:
        JSON array of saved items with author info and metadata
    """
    scraper = get_scraper()
    saved_items = await scraper.get_saved(limit=limit)

    global _saved_cache
    _saved_cache = saved_items

    return json.dumps(
        [item.model_dump(mode="json") for item in saved_items],
        indent=2,
    )


@mcp.tool()
async def get_reddit_saved_posts(limit: int = 100) -> str:
    """
    Fetch only saved posts (submissions) from Reddit.

    Args:
        limit: Maximum number of posts to fetch (default 100)

    Returns:
        JSON array of saved posts
    """
    scraper = get_scraper()
    posts = await scraper.get_saved_posts(limit=limit)

    return json.dumps(
        [item.model_dump(mode="json") for item in posts],
        indent=2,
    )


@mcp.tool()
async def get_reddit_saved_comments(limit: int = 100) -> str:
    """
    Fetch only saved comments from Reddit.

    Args:
        limit: Maximum number of comments to fetch (default 100)

    Returns:
        JSON array of saved comments
    """
    scraper = get_scraper()
    comments = await scraper.get_saved_comments(limit=limit)

    return json.dumps(
        [item.model_dump(mode="json") for item in comments],
        indent=2,
    )


@mcp.tool()
async def search_reddit_saved(
    queries: list[str],
    match_all: bool = True,
    fuzzy_threshold: int = 2,
    limit: int = 50,
    subreddit: Optional[str] = None,
) -> str:
    """
    Search through saved Reddit items with fuzzy matching.

    Args:
        queries: List of search terms to look for in content
        match_all: If True, all queries must match (AND). If False, any match (OR).
        fuzzy_threshold: Max edit distance for fuzzy matching (0 disables fuzzy)
        limit: Maximum number of results to return (default 50)
        subreddit: Filter by subreddit name (optional)

    Returns:
        JSON array of matching saved items
    """
    # Use cache if available, otherwise fetch all saved items
    saved_items = await _ensure_cache()

    scraper = get_scraper()
    results = scraper.search_saved(
        posts=saved_items,
        queries=queries,
        match_all=match_all,
        fuzzy_threshold=fuzzy_threshold,
        limit=limit,
        subreddit=subreddit,
    )

    return json.dumps(
        [item.model_dump(mode="json") for item in results],
        indent=2,
    )


@mcp.tool()
def get_reddit_user_info() -> str:
    """
    Get information about the authenticated Reddit user.

    Returns:
        JSON object with username from environment
    """
    username = os.environ.get("REDDIT_USERNAME", "unknown")
    return json.dumps({"username": username}, indent=2)


@mcp.resource("reddit://saved")
async def list_saved() -> str:
    """List all saved items as a resource."""
    scraper = get_scraper()
    saved_items = await scraper.get_saved()

    global _saved_cache
    _saved_cache = saved_items

    return json.dumps(
        [item.model_dump(mode="json") for item in saved_items],
        indent=2,
    )


@mcp.resource("reddit://saved/posts")
async def list_saved_posts() -> str:
    """List only saved posts as a resource."""
    scraper = get_scraper()
    posts = await scraper.get_saved_posts()

    return json.dumps(
        [item.model_dump(mode="json") for item in posts],
        indent=2,
    )


@mcp.resource("reddit://saved/comments")
async def list_saved_comments() -> str:
    """List only saved comments as a resource."""
    scraper = get_scraper()
    comments = await scraper.get_saved_comments()

    return json.dumps(
        [item.model_dump(mode="json") for item in comments],
        indent=2,
    )


@mcp.resource("reddit://user")
def get_user() -> str:
    """Get the authenticated user's information as a resource."""
    username = os.environ.get("REDDIT_USERNAME", "unknown")
    return json.dumps({"username": username}, indent=2)


def main():
    """Entry point for the Reddit MCP server."""
    if _TRANSPORT == "http":
        mcp.run(transport="streamable-http")
    else:
        mcp.run()


if __name__ == "__main__":
    main()
