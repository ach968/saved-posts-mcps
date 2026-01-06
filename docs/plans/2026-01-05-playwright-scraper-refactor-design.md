# Playwright Scraper Refactor Design

## Overview

Extract shared Playwright logic from XScraper into a base class that both X and Reddit scrapers can extend. Replace the PRAW-based Reddit client with a cookie-authenticated Playwright scraper.

## Base Class: PlaywrightScraper

**Location**: `src/common/playwright_scraper.py`

Handles:
- Cookie management: Load from file (JSON array, dict, Netscape format) or env var
- Browser lifecycle: Lazy browser/context creation, cleanup via `close()`
- Configurable domains: Each platform specifies its cookie domains
- Request optimization: Optional resource blocking (images, fonts)

```python
class PlaywrightScraper:
    def __init__(
        self,
        cookies_file: Path | None,
        cookies_list: list[dict] | None,
        cookie_domains: list[str],  # e.g., [".x.com", "x.com"]
        target_domain: str,         # e.g., ".x.com" for normalization
        headless: bool = True,
    ): ...

    async def _get_browser(self) -> Browser: ...
    async def _get_context(self) -> BrowserContext: ...
    async def close(self) -> None: ...

    def _load_cookies_from_file(self, path: Path) -> None: ...
    def _parse_netscape_cookies(self, content: str) -> None: ...
```

## XScraper Refactor

Becomes a thin subclass inheriting cookie/browser management:

```python
class XScraper(PlaywrightScraper):
    def __init__(self, cookies_file=None, cookies_list=None, headless=True):
        super().__init__(
            cookies_file=cookies_file,
            cookies_list=cookies_list,
            cookie_domains=[".x.com", "x.com", ".twitter.com", "twitter.com"],
            target_domain=".x.com",
            headless=headless,
        )
```

X-specific logic stays: GraphQL features, header capture, cursor extraction, parsing.

## RedditScraper Implementation

**Location**: `src/reddit/scraper.py`

```python
class RedditScraper(PlaywrightScraper):
    def __init__(self, username: str, cookies_file=None, cookies_list=None, headless=True):
        super().__init__(
            cookies_file=cookies_file,
            cookies_list=cookies_list,
            cookie_domains=[".reddit.com", "reddit.com"],
            target_domain=".reddit.com",
            headless=headless,
        )
        self.username = username
```

Uses same hybrid approach: navigate to capture headers, then paginate API directly.

## File Changes

```
src/
├── common/
│   ├── models.py              # unchanged
│   ├── auth.py                # unchanged
│   └── playwright_scraper.py  # NEW
├── x/
│   ├── server.py              # unchanged
│   ├── scraper.py             # refactored
│   └── utils.py               # unchanged
└── reddit/
    ├── server.py              # updated
    ├── scraper.py             # NEW
    └── client.py              # DELETE
```

## Environment Changes

Reddit env vars simplify from OAuth credentials to cookie auth:

```bash
# Old (.env.reddit)
export REDDIT_CLIENT_ID="..."
export REDDIT_CLIENT_SECRET="..."
export REDDIT_USERNAME="..."
export REDDIT_PASSWORD="..."

# New (.env.reddit)
export REDDIT_COOKIES_FILE=/path/to/reddit_cookies.txt
export REDDIT_USERNAME=your_username
```

## Implementation Order

1. Create `src/common/playwright_scraper.py` with base class
2. Refactor `src/x/scraper.py` to extend it (verify X still works)
3. Create `src/reddit/scraper.py` with RedditScraper
4. Update `src/reddit/server.py` to use new scraper
5. Delete `src/reddit/client.py`
6. Update CLAUDE.md with new env var instructions
