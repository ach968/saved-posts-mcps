# Saved Posts Aggregator MCP - Project Plan

## Overview

A Model Context Protocol (MCP) server that aggregates saved/bookmarked posts from multiple social platforms. Each platform integration runs as a dockerized MCP server, exposing tools and resources for LLM applications to query saved content.

**Initial Focus:** X (Twitter) and Reddit integrations

---

## Phase 1: Project Foundation

### 1.1 Dependencies Setup
- Add MCP SDK: `mcp[cli]` (requires Python 3.10+, current project uses 3.13)
- Add HTTP client: `httpx` for async API requests
- Add Reddit wrapper: `praw` for Reddit API
- Add OAuth library: `authlib` for X OAuth 2.0 PKCE flow
- Add data validation: `pydantic` for structured responses

### 1.2 Project Structure
```
saved-posts-aggregator/
├── src/
│   ├── common/
│   │   ├── __init__.py
│   │   ├── models.py          # Shared data models (Post, Author, etc.)
│   │   └── auth.py            # OAuth utilities
│   ├── x/
│   │   ├── __init__.py
│   │   ├── server.py          # X MCP server
│   │   ├── client.py          # X API client
│   │   └── Dockerfile
│   └── reddit/
│       ├── __init__.py
│       ├── server.py          # Reddit MCP server
│       ├── client.py          # Reddit API client
│       └── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

---

## Phase 2: X (Twitter) Integration

### 2.1 API Details

**Endpoint:** `GET /2/users/:id/bookmarks`
**Base URL:** `https://api.twitter.com/2`

**Authentication:**
- OAuth 2.0 Authorization Code with PKCE
- Required scopes: `tweet.read`, `users.read`, `bookmark.read`
- Requires approved X Developer Account

**Rate Limits:**
- 180 requests per 15-minute window (per user)
- Returns max 800 most recent bookmarks

**Response Fields to Request:**
- Tweet: `id`, `text`, `created_at`, `author_id`, `attachments`
- Expansions: `author_id`, `attachments.media_keys`
- User fields: `username`, `name`, `profile_image_url`
- Media fields: `url`, `preview_image_url`, `type`

### 2.2 Implementation Steps

1. **OAuth 2.0 PKCE Flow Handler**
   - Implement authorization URL generation
   - Handle callback and token exchange
   - Token storage and refresh logic

2. **X API Client (`src/x/client.py`)**
   - `get_bookmarks(user_id, pagination_token=None)` - Fetch bookmarks page
   - `get_all_bookmarks(user_id)` - Iterator for all bookmarks (up to 800)
   - Handle rate limiting with exponential backoff

3. **MCP Server (`src/x/server.py`)**
   - **Tools:**
     - `get_x_bookmarks` - Fetch user's bookmarked tweets
     - `search_x_bookmarks` - Search within bookmarks by keyword
   - **Resources:**
     - `x://bookmarks` - List all bookmarks as structured data
     - `x://bookmarks/{tweet_id}` - Get specific bookmark details

---

## Phase 3: Reddit Integration

### 3.1 API Details

**Library:** PRAW (Python Reddit API Wrapper)
**Endpoint:** User saved items via `reddit.user.me().saved()`

**Authentication:**
- OAuth2 with password grant (for script apps)
- Requires Reddit app credentials from https://www.reddit.com/prefs/apps
- User-Agent format: `<platform>:<app_id>:<version> (by /u/<username>)`

**Rate Limits:**
- 100 queries per minute (free tier)
- 60 requests per minute via PRAW
- Max ~1000 items per listing

**Required Credentials:**
- `client_id` - From Reddit app
- `client_secret` - From Reddit app
- `username` - Reddit username
- `password` - Reddit password
- `user_agent` - Custom user agent string

### 3.2 Implementation Steps

1. **Reddit Client (`src/reddit/client.py`)**
   - Initialize PRAW with credentials
   - `get_saved_posts(limit=None)` - Fetch saved submissions
   - `get_saved_comments(limit=None)` - Fetch saved comments
   - `get_all_saved(limit=None)` - Fetch all saved items (posts + comments)

2. **MCP Server (`src/reddit/server.py`)**
   - **Tools:**
     - `get_reddit_saved` - Fetch all saved items
     - `get_reddit_saved_posts` - Fetch only saved posts
     - `get_reddit_saved_comments` - Fetch only saved comments
     - `search_reddit_saved` - Search saved items by keyword/subreddit
   - **Resources:**
     - `reddit://saved` - List all saved items
     - `reddit://saved/posts` - List saved posts only
     - `reddit://saved/comments` - List saved comments only

---

## Phase 4: Shared Data Models

### 4.1 Common Models (`src/common/models.py`)

```python
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Literal

class Author(BaseModel):
    id: str
    username: str
    display_name: str
    avatar_url: Optional[str] = None
    platform: Literal["x", "reddit", "instagram", "tiktok", "youtube"]

class Media(BaseModel):
    type: Literal["image", "video", "gif"]
    url: str
    thumbnail_url: Optional[str] = None

class SavedPost(BaseModel):
    id: str
    platform: Literal["x", "reddit", "instagram", "tiktok", "youtube"]
    author: Author
    content: str
    url: str
    created_at: datetime
    saved_at: Optional[datetime] = None
    media: list[Media] = []
    metadata: dict = {}  # Platform-specific data (subreddit, retweets, etc.)
```

---

## Phase 5: Docker Setup

### 5.1 Per-Platform Dockerfiles

Each platform server runs in its own container:

```dockerfile
# Example: src/x/Dockerfile
FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install .
COPY src/ src/
ENV MCP_TRANSPORT=streamable-http
EXPOSE 8000
CMD ["python", "-m", "src.x.server"]
```

### 5.2 Docker Compose

```yaml
version: "3.9"
services:
  x-server:
    build:
      context: .
      dockerfile: src/x/Dockerfile
    ports:
      - "8001:8000"
    env_file:
      - .env.x

  reddit-server:
    build:
      context: .
      dockerfile: src/reddit/Dockerfile
    ports:
      - "8002:8000"
    env_file:
      - .env.reddit
```

---

## Phase 6: Configuration & Environment

### 6.1 Environment Variables

**X (`.env.x`):**
```
X_CLIENT_ID=your_client_id
X_CLIENT_SECRET=your_client_secret
X_REDIRECT_URI=http://localhost:8001/callback
X_ACCESS_TOKEN=  # After OAuth flow
X_REFRESH_TOKEN= # After OAuth flow
```

**Reddit (`.env.reddit`):**
```
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USERNAME=your_username
REDDIT_PASSWORD=your_password
REDDIT_USER_AGENT=saved-posts-aggregator:v0.1.0 (by /u/your_username)
```

---

## Implementation Order

1. **Set up dependencies** in `pyproject.toml`
2. **Create common models** for unified data representation
3. **Implement Reddit integration first** (simpler OAuth, well-documented PRAW)
4. **Implement X integration** (more complex PKCE flow)
5. **Dockerize each server**
6. **Test with MCP inspector** (`npx @modelcontextprotocol/inspector`)
7. **Create docker-compose** for unified deployment

---

## API Reference Sources

- [X Bookmarks API Introduction](https://developer.x.com/en/docs/x-api/tweets/bookmarks/introduction)
- [X Get Bookmarks Endpoint](https://docs.x.com/x-api/users/get-bookmarks)
- [PRAW Documentation](https://praw.readthedocs.io/en/stable/)
- [Reddit OAuth2 Wiki](https://github.com/reddit-archive/reddit/wiki/OAuth2)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Reddit API Guide](https://apidog.com/blog/reddit-api-guide/)

---

## Future Phases (Out of Scope for Now)

- Instagram saved posts integration
- TikTok favorites integration
- YouTube liked/saved videos integration
- Unified search across all platforms
- Web UI for managing saved posts
- Automated sync/backup to local storage
