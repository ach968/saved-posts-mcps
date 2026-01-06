# Fuzzy Search for X and Reddit MCP Servers

## Overview

Add fuzzy search capability to both X and Reddit MCP servers, allowing typo-tolerant matching with multiple search terms and configurable AND/OR logic.

## API Changes

### X Server: `search_x_bookmarks`

```python
@mcp.tool()
async def search_x_bookmarks(
    queries: list[str],           # List of search terms
    match_all: bool = True,       # True=AND (all required), False=OR (any match)
    fuzzy_threshold: int = 2,     # Max edit distance (0 disables fuzzy)
) -> list[dict]:
```

### Reddit Server: `search_reddit_saved`

```python
@mcp.tool()
async def search_reddit_saved(
    queries: list[str],
    match_all: bool = True,
    fuzzy_threshold: int = 2,
) -> list[dict]:
```

## Examples

- `queries=["python", "async"], match_all=True` - posts with both words
- `queries=["python", "rust"], match_all=False` - posts with either word
- `queries=["twiter"]` - matches "twitter" via fuzzy tolerance

## Implementation

### Dependencies

Add `rapidfuzz` for fast fuzzy string matching:

```bash
uv add rapidfuzz
```

### Matching Logic

```python
from rapidfuzz import fuzz

def fuzzy_word_match(word: str, text: str, threshold: int) -> bool:
    """Check if word appears in text with fuzzy tolerance."""
    text_words = text.lower().split()
    word_lower = word.lower()

    for text_word in text_words:
        # Exact match
        if word_lower == text_word:
            return True
        # Fuzzy match for words 4+ chars
        if threshold > 0 and len(word_lower) > 3:
            if fuzz.ratio(word_lower, text_word) >= (100 - threshold * 10):
                return True
    return False
```

Posts match when:
- **AND mode (`match_all=True`)**: All query words match somewhere in content
- **OR mode (`match_all=False`)**: At least one query word matches

### Fuzzy Threshold

- `threshold=0`: Exact matching only
- `threshold=1`: Strict - 1 char difference allowed
- `threshold=2`: Moderate (default) - up to 2 char differences for longer words
- `threshold=3+`: Loose - more forgiving

Only applies to words 4+ characters to avoid false positives on short words.

## Files to Change

1. `src/x/scraper.py` - Update `search_bookmarks` method
2. `src/x/server.py` - Update `search_x_bookmarks` tool signature
3. `src/reddit/scraper.py` - Update search method
4. `src/reddit/server.py` - Update `search_reddit_saved` tool signature
5. `pyproject.toml` - Add `rapidfuzz` dependency
