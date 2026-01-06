# Docker Build & MCP Config Scripts Design

## Overview

Two shell scripts for personal workflow: quick Docker image builds and Claude Code MCP configuration.

## Scripts

### `scripts/docker-build.sh`

Builds Docker images for X and/or Reddit MCP servers.

```bash
# Usage
./scripts/docker-build.sh [x|reddit|all]

# Examples
./scripts/docker-build.sh x       # Build X server only
./scripts/docker-build.sh reddit  # Build Reddit server only
./scripts/docker-build.sh all     # Build both (default)
./scripts/docker-build.sh         # Same as 'all'
```

**Image names**: `saved-posts-x:latest`, `saved-posts-reddit:latest`

**Behavior**:
- Runs from repo root (script handles directory)
- Shows build progress, exits on failure
- Prints docker run command hint after successful build

### `scripts/mcp-config.sh`

Adds MCP server configs to Claude Code pointing to local Docker containers.

```bash
# Usage
./scripts/mcp-config.sh [x|reddit|all]

# Examples
./scripts/mcp-config.sh x       # Add X server config only
./scripts/mcp-config.sh reddit  # Add Reddit server config only
./scripts/mcp-config.sh all     # Add both (default)
```

**MCP endpoints**:
| Server | URL |
|--------|-----|
| `saved-posts-x` | `http://localhost:8001/mcp` |
| `saved-posts-reddit` | `http://localhost:8002/mcp` |

**Behavior**:
- Uses `claude mcp add --transport http` CLI
- Adds to user scope (`~/.claude.json`)
- Overwrites existing entries with same name

## Server Changes

Both `src/x/server.py` and `src/reddit/server.py` need transport switching:

```python
if __name__ == "__main__":
    import os
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "http":
        mcp.run(transport="streamable-http", host="0.0.0.0", port=int(os.getenv("MCP_PORT", "8000")))
    else:
        mcp.run()
```

**Environment variables**:
- `MCP_TRANSPORT` - `stdio` (default) or `http`
- `MCP_PORT` - Port for HTTP mode (default 8000)

## Dockerfile Updates

### `src/x/Dockerfile`

Add before CMD:
```dockerfile
ENV MCP_TRANSPORT=http
ENV MCP_PORT=8001
EXPOSE 8001
```

### `src/reddit/Dockerfile`

Add before CMD:
```dockerfile
ENV MCP_TRANSPORT=http
ENV MCP_PORT=8002
EXPOSE 8002
```

## Docker Run Commands

```bash
# X server
docker run -d --name saved-posts-x \
  -p 8001:8001 \
  -v /path/to/x_cookies.txt:/app/cookies.txt:ro \
  -e X_COOKIES_FILE=/app/cookies.txt \
  saved-posts-x:latest

# Reddit server
docker run -d --name saved-posts-reddit \
  -p 8002:8002 \
  -v /path/to/reddit_cookies.txt:/app/cookies.txt:ro \
  -e REDDIT_COOKIES_FILE=/app/cookies.txt \
  -e REDDIT_USERNAME=your_username \
  saved-posts-reddit:latest
```
