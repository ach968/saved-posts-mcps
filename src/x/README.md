# X Bookmarks MCP Server

An MCP (Model Context Protocol) server that scrapes your X (Twitter) bookmarks using Playwright and browser cookies.

## Setup

### 1. Export Browser Cookies

Export your X.com cookies from your browser using a cookies.txt extension:
- Firefox: [cookies.txt](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/)
- Chrome: [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)

1. Log into x.com in your browser
2. Use the extension to export cookies
3. Save the file (e.g., `x_cookies.txt`)

### 2. Configure Environment

Create a `.env.x` file or set environment variables:

```bash
# Path to your cookies file (Netscape format)
X_COOKIES_FILE=/path/to/x_cookies.txt

# OR provide cookies as JSON
# X_COOKIES='[{"name":"auth_token","value":"xxx","domain":".x.com","path":"/"}]'
```

The scraper also checks `~/.x_cookies.txt` by default.

### 3. Install Dependencies

```bash
uv sync
uv run playwright install chromium
```

### 4. Run the Server

```bash
# With environment file
source .env.x && export X_COOKIES_FILE && uv run python -m src.x.server

# Or run directly
X_COOKIES_FILE=x_cookies.txt uv run python -m src.x.server
```

## Available Tools

### `get_x_bookmarks`
Fetch bookmarked tweets from X.

**Parameters:**
- `limit` (int, default: 100): Maximum number of bookmarks to return
- `refresh` (bool, default: false): Force refresh from X.com instead of using cache

**Returns:** JSON array of bookmarked tweets with author info, content, media, and metadata.

### `search_x_bookmarks`
Search through bookmarked tweets by keyword.

**Parameters:**
- `query` (string, required): Search term to look for in tweet text
- `limit` (int, default: 50): Maximum number of results

**Returns:** JSON array of matching bookmarks.

### `refresh_x_bookmarks`
Force refresh the bookmarks cache from X.com.

**Returns:** Status object with count of bookmarks fetched.

## Available Resources

- `x://bookmarks` - List all bookmarked tweets

## Response Format

Each bookmark is returned as a `SavedPost` object:

```json
{
  "id": "1234567890",
  "platform": "x",
  "author": {
    "id": "username",
    "username": "username",
    "display_name": "Display Name",
    "avatar_url": "https://pbs.twimg.com/profile_images/...",
    "platform": "x"
  },
  "content": "Tweet text content...",
  "url": "https://x.com/username/status/1234567890",
  "created_at": "2024-01-15T12:00:00+00:00",
  "media": [
    {
      "type": "image",
      "url": "https://pbs.twimg.com/media/..."
    }
  ],
  "metadata": {
    "retweet_count": 42,
    "like_count": 123,
    "reply_count": 5,
    "quote_count": 2
  }
}
```

## Usage Examples

### For AI Assistants

```
# Fetch recent bookmarks
Call get_x_bookmarks with limit=20

# Search for specific topics
Call search_x_bookmarks with query="python" limit=10

# Refresh after bookmarking new tweets
Call refresh_x_bookmarks
```

### With MCP Inspector

```bash
source .env.x && export X_COOKIES_FILE && \
  npx @modelcontextprotocol/inspector uv run python -m src.x.server
```

## Troubleshooting

### Cookies Expired
If you get redirected to login, your cookies have expired. Export fresh cookies from your browser.

### No Articles Found
X.com uses JavaScript heavily. The scraper uses Playwright to render the page. Check:
1. Cookies are valid (not expired)
2. Debug screenshot at `/tmp/x_bookmarks_debug.png`
3. Debug HTML at `/tmp/x_bookmarks_debug.html`

### Timeout Errors
Increase timeout or check network connectivity. X.com can be slow to load.
