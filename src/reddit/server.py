import json
from typing import Optional

from mcp.server.fastmcp import FastMCP

from src.reddit.client import RedditClient

mcp = FastMCP("Reddit Saved Posts Server")

# Global client instance (initialized on first use)
_client: Optional[RedditClient] = None


def get_client() -> RedditClient:
    """Get or create the Reddit API client."""
    global _client
    if _client is None:
        _client = RedditClient.from_env()
    return _client


@mcp.tool()
def get_reddit_saved(limit: int = 100) -> str:
    """
    Fetch the user's saved posts and comments from Reddit.

    Args:
        limit: Maximum number of items to fetch (default 100, max ~1000)

    Returns:
        JSON array of saved items with author info and metadata
    """
    client = get_client()
    saved_items = []

    for item in client.get_saved(limit=limit):
        saved_items.append(item.model_dump(mode="json"))

    return json.dumps(saved_items, indent=2)


@mcp.tool()
def get_reddit_saved_posts(limit: int = 100) -> str:
    """
    Fetch only saved posts (submissions) from Reddit.

    Args:
        limit: Maximum number of posts to fetch (default 100)

    Returns:
        JSON array of saved posts
    """
    client = get_client()
    posts = []

    for item in client.get_saved_posts(limit=limit):
        posts.append(item.model_dump(mode="json"))

    return json.dumps(posts, indent=2)


@mcp.tool()
def get_reddit_saved_comments(limit: int = 100) -> str:
    """
    Fetch only saved comments from Reddit.

    Args:
        limit: Maximum number of comments to fetch (default 100)

    Returns:
        JSON array of saved comments
    """
    client = get_client()
    comments = []

    for item in client.get_saved_comments(limit=limit):
        comments.append(item.model_dump(mode="json"))

    return json.dumps(comments, indent=2)


@mcp.tool()
def search_reddit_saved(
    query: str,
    limit: int = 50,
    subreddit: Optional[str] = None,
) -> str:
    """
    Search through saved Reddit items by keyword.

    Args:
        query: Search term to look for in content
        limit: Maximum number of results to return (default 50)
        subreddit: Filter by subreddit name (optional)

    Returns:
        JSON array of matching saved items
    """
    client = get_client()
    results = client.search_saved(query=query, limit=limit, subreddit=subreddit)

    return json.dumps([item.model_dump(mode="json") for item in results], indent=2)


@mcp.tool()
def get_reddit_user_info() -> str:
    """
    Get information about the authenticated Reddit user.

    Returns:
        JSON object with user ID, username, karma, and account age
    """
    client = get_client()
    user = client.get_me()

    return json.dumps(user, indent=2)


@mcp.resource("reddit://saved")
def list_saved() -> str:
    """List all saved items as a resource."""
    client = get_client()
    saved_items = []

    for item in client.get_saved():
        saved_items.append(item.model_dump(mode="json"))

    return json.dumps(saved_items, indent=2)


@mcp.resource("reddit://saved/posts")
def list_saved_posts() -> str:
    """List only saved posts as a resource."""
    client = get_client()
    posts = []

    for item in client.get_saved_posts():
        posts.append(item.model_dump(mode="json"))

    return json.dumps(posts, indent=2)


@mcp.resource("reddit://saved/comments")
def list_saved_comments() -> str:
    """List only saved comments as a resource."""
    client = get_client()
    comments = []

    for item in client.get_saved_comments():
        comments.append(item.model_dump(mode="json"))

    return json.dumps(comments, indent=2)


@mcp.resource("reddit://user")
def get_user() -> str:
    """Get the authenticated user's information as a resource."""
    client = get_client()
    user = client.get_me()
    return json.dumps(user, indent=2)


def main():
    """Entry point for the Reddit MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
