# Docker Build & MCP Config Scripts Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create shell scripts for building Docker images and configuring Claude Code MCP servers.

**Architecture:** Add HTTP transport support to existing MCP servers via env var switch, then create two shell scripts for Docker builds and MCP configuration.

**Tech Stack:** Bash, FastMCP streamable-http transport, Docker

---

### Task 1: Update X Server Transport

**Files:**
- Modify: `src/x/server.py:74-80`

**Step 1: Update the main() function and entry point**

Replace lines 74-80 with:

```python
def main():
    """Entry point for the X MCP server."""
    import os
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "http":
        mcp.run(transport="streamable-http", host="0.0.0.0", port=int(os.getenv("MCP_PORT", "8000")))
    else:
        mcp.run()


if __name__ == "__main__":
    main()
```

**Step 2: Test locally**

```bash
cd /home/acheney/Public/saved-posts-aggregator
MCP_TRANSPORT=http MCP_PORT=8001 uv run python -m src.x.server &
curl -s http://localhost:8001/mcp | head -5
# Should see SSE or JSON response, not connection refused
kill %1
```

**Step 3: Commit**

```bash
git add src/x/server.py
git commit -m "feat(x): add HTTP transport support via MCP_TRANSPORT env var"
```

---

### Task 2: Update Reddit Server Transport

**Files:**
- Modify: `src/reddit/server.py:195-201`

**Step 1: Update the main() function and entry point**

Replace lines 195-201 with:

```python
def main():
    """Entry point for the Reddit MCP server."""
    import os
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "http":
        mcp.run(transport="streamable-http", host="0.0.0.0", port=int(os.getenv("MCP_PORT", "8000")))
    else:
        mcp.run()


if __name__ == "__main__":
    main()
```

**Step 2: Test locally**

```bash
cd /home/acheney/Public/saved-posts-aggregator
MCP_TRANSPORT=http MCP_PORT=8002 uv run python -m src.reddit.server &
curl -s http://localhost:8002/mcp | head -5
kill %1
```

**Step 3: Commit**

```bash
git add src/reddit/server.py
git commit -m "feat(reddit): add HTTP transport support via MCP_TRANSPORT env var"
```

---

### Task 3: Update X Dockerfile

**Files:**
- Modify: `src/x/Dockerfile:31-38`

**Step 1: Update environment and expose port**

Replace lines 31-38 (from `ENV PYTHONUNBUFFERED` to `CMD`) with:

```dockerfile
# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV MCP_TRANSPORT=http
ENV MCP_PORT=8001

# Expose port for HTTP transport
EXPOSE 8001

# Run the MCP server using Python 3.13
CMD ["python3.13", "-m", "src.x.server"]
```

**Step 2: Commit**

```bash
git add src/x/Dockerfile
git commit -m "feat(x): configure Dockerfile for HTTP transport on port 8001"
```

---

### Task 4: Update Reddit Dockerfile

**Files:**
- Modify: `src/reddit/Dockerfile:23-31`

**Step 1: Update environment and expose port**

Replace lines 23-31 (from `ENV PYTHONUNBUFFERED` to `CMD`) with:

```dockerfile
# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV MCP_TRANSPORT=http
ENV MCP_PORT=8002

# Expose port for HTTP transport
EXPOSE 8002

# Run the MCP server
CMD ["python", "-m", "src.reddit.server"]
```

**Step 2: Commit**

```bash
git add src/reddit/Dockerfile
git commit -m "feat(reddit): configure Dockerfile for HTTP transport on port 8002"
```

---

### Task 5: Create docker-build.sh Script

**Files:**
- Create: `scripts/docker-build.sh`

**Step 1: Create scripts directory**

```bash
mkdir -p /home/acheney/Public/saved-posts-aggregator/scripts
```

**Step 2: Write the script**

```bash
#!/bin/bash
set -e

# Docker build script for saved-posts MCP servers
# Usage: ./scripts/docker-build.sh [x|reddit|all]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$REPO_ROOT"

build_x() {
    echo "Building X server image..."
    docker build -t saved-posts-x:latest -f src/x/Dockerfile .
    echo "✓ Built saved-posts-x:latest"
    echo ""
    echo "Run with:"
    echo "  docker run -d --name saved-posts-x -p 8001:8001 \\"
    echo "    -v /path/to/x_cookies.txt:/app/cookies.txt:ro \\"
    echo "    -e X_COOKIES_FILE=/app/cookies.txt \\"
    echo "    saved-posts-x:latest"
}

build_reddit() {
    echo "Building Reddit server image..."
    docker build -t saved-posts-reddit:latest -f src/reddit/Dockerfile .
    echo "✓ Built saved-posts-reddit:latest"
    echo ""
    echo "Run with:"
    echo "  docker run -d --name saved-posts-reddit -p 8002:8002 \\"
    echo "    -v /path/to/reddit_cookies.txt:/app/cookies.txt:ro \\"
    echo "    -e REDDIT_COOKIES_FILE=/app/cookies.txt \\"
    echo "    -e REDDIT_USERNAME=your_username \\"
    echo "    saved-posts-reddit:latest"
}

case "${1:-all}" in
    x)
        build_x
        ;;
    reddit)
        build_reddit
        ;;
    all)
        build_x
        echo ""
        build_reddit
        ;;
    *)
        echo "Usage: $0 [x|reddit|all]"
        exit 1
        ;;
esac
```

**Step 3: Make executable**

```bash
chmod +x scripts/docker-build.sh
```

**Step 4: Commit**

```bash
git add scripts/docker-build.sh
git commit -m "feat: add docker-build.sh script for building MCP server images"
```

---

### Task 6: Create mcp-config.sh Script

**Files:**
- Create: `scripts/mcp-config.sh`

**Step 1: Write the script**

```bash
#!/bin/bash
set -e

# MCP config script for Claude Code
# Usage: ./scripts/mcp-config.sh [x|reddit|all]

add_x() {
    echo "Adding X server MCP config..."
    claude mcp add saved-posts-x --transport http http://localhost:8001/mcp --scope user 2>/dev/null || \
    claude mcp add saved-posts-x --transport http http://localhost:8001/mcp --scope user
    echo "✓ Added saved-posts-x -> http://localhost:8001/mcp"
}

add_reddit() {
    echo "Adding Reddit server MCP config..."
    claude mcp add saved-posts-reddit --transport http http://localhost:8002/mcp --scope user 2>/dev/null || \
    claude mcp add saved-posts-reddit --transport http http://localhost:8002/mcp --scope user
    echo "✓ Added saved-posts-reddit -> http://localhost:8002/mcp"
}

case "${1:-all}" in
    x)
        add_x
        ;;
    reddit)
        add_reddit
        ;;
    all)
        add_x
        add_reddit
        ;;
    *)
        echo "Usage: $0 [x|reddit|all]"
        exit 1
        ;;
esac

echo ""
echo "Verify with: claude mcp list"
```

**Step 2: Make executable**

```bash
chmod +x scripts/mcp-config.sh
```

**Step 3: Commit**

```bash
git add scripts/mcp-config.sh
git commit -m "feat: add mcp-config.sh script for Claude Code MCP configuration"
```

---

### Task 7: Update TODO.md

**Files:**
- Modify: `docs/TODO.md`

**Step 1: Mark item as complete**

Change:
```markdown
- [ ] ez script to add mcp configs to claude code, and ez dockerfile building scripts (both features bundled together)
```

To:
```markdown
- [x] ez script to add mcp configs to claude code, and ez dockerfile building scripts (both features bundled together)
```

**Step 2: Commit**

```bash
git add docs/TODO.md
git commit -m "docs: mark docker/mcp scripts TODO as complete"
```
