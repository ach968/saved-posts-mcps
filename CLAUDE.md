# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MCP (Model Context Protocol) server that aggregates saved/bookmarked posts from X (Twitter) and Reddit. Each platform runs as a separate MCP server exposing tools and resources for LLM applications.

## Common Commands

```bash
# Install dependencies
uv sync
uv run playwright install chromium

# Run X server
X_COOKIES_FILE=/path/to/x_cookies.txt uv run python -m src.x.server

# Run Reddit server
REDDIT_COOKIES_FILE=/path/to/reddit_cookies.txt REDDIT_USERNAME=your_username uv run python -m src.reddit.server

# Test with MCP inspector
X_COOKIES_FILE=x_cookies.txt npx @modelcontextprotocol/inspector uv run python -m src.x.server
REDDIT_COOKIES_FILE=reddit_cookies.txt REDDIT_USERNAME=your_username npx @modelcontextprotocol/inspector uv run python -m src.reddit.server
```

## Architecture

### Platform Structure
Each platform (`src/x/`, `src/reddit/`) follows the same pattern:
- `server.py` - FastMCP server with `@mcp.tool()` and `@mcp.resource()` decorators
- `scraper.py` - Platform-specific Playwright scraper extending `PlaywrightScraper` base class
- Lazy-initialized global scraper instance via `get_scraper()`

### Shared Playwright Base (`src/common/playwright_scraper.py`)
Both X and Reddit scrapers extend `PlaywrightScraper` which provides:
- Cookie parsing (JSON array, dict, Netscape cookies.txt format)
- Browser/context lifecycle management
- Request optimization (blocking images/fonts)

### Shared Models (`src/common/models.py`)
All platforms return unified `SavedPost` objects with platform-specific metadata:
- `SavedPost` - Base model with `id`, `platform`, `author`, `content`, `url`, `created_at`, `media`, `metadata`
- `Author` - User info across platforms
- `Media` - Attached images/videos
- `XMetadata`/`RedditMetadata` - Platform-specific fields stored in `SavedPost.metadata`

### X Integration
Uses Playwright headless browser to:
1. Load bookmarks page with exported cookies (Netscape or JSON format)
2. Capture GraphQL request headers from initial page load
3. Make direct API calls using captured headers for pagination

Cookie sources (checked in order): `X_COOKIES_FILE` env var, `X_COOKIES` JSON env var, `~/.x_cookies.txt`

### Reddit Integration
Uses Playwright headless browser (same hybrid approach as X):
1. Load saved page with exported cookies (Netscape or JSON format)
2. Capture request headers from initial page load
3. Make direct JSON API calls using captured headers for pagination

Cookie sources (checked in order): `REDDIT_COOKIES_FILE` env var, `REDDIT_COOKIES` JSON env var, `~/.reddit_cookies.txt`

Also requires: `REDDIT_USERNAME` env var (for building saved URL)

## Environment Files

- `.env.x` - X cookies path
- `.env.reddit` - Reddit cookies path and username

## MCP Tools Exposed

**X Server:** `get_x_bookmarks`, `search_x_bookmarks`
**Reddit Server:** `get_reddit_saved`, `get_reddit_saved_posts`, `get_reddit_saved_comments`, `search_reddit_saved`, `get_reddit_user_info`
