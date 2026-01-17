#!/bin/bash
set -e

add_x() {
    echo "Adding X server MCP config (Docker + stdio)..."

    # Remove existing if present
    claude mcp remove saved-posts-x --scope user 2>/dev/null || true

    claude mcp add-json saved-posts-x --scope user '{
        "type": "stdio",
        "command": "docker",
        "args": [
            "run", "-i", "--rm",
            "-e", "MCP_TRANSPORT=stdio",
            "-v", "${X_COOKIES_FILE}:/app/cookies.txt:ro",
            "-e", "X_COOKIES_FILE=/app/cookies.txt",
            "saved-posts-x:latest"
        ]
    }'

    echo "✓ Added saved-posts-x (Docker stdio)"
    echo "  Requires: X_COOKIES_FILE env var set"
}

add_reddit() {
    echo "Adding Reddit server MCP config (Docker + stdio)..."

    # Remove existing if present
    claude mcp remove saved-posts-reddit --scope user 2>/dev/null || true

    claude mcp add-json saved-posts-reddit --scope user '{
        "type": "stdio",
        "command": "docker",
        "args": [
            "run", "-i", "--rm",
            "-e", "MCP_TRANSPORT=stdio",
            "-v", "${REDDIT_COOKIES_FILE}:/app/cookies.txt:ro",
            "-e", "REDDIT_COOKIES_FILE=/app/cookies.txt",
            "-e", "REDDIT_USERNAME=${REDDIT_USERNAME}",
            "saved-posts-reddit:latest"
        ]
    }'

    echo "✓ Added saved-posts-reddit (Docker stdio)"
    echo "  Requires: REDDIT_COOKIES_FILE and REDDIT_USERNAME env vars set"
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
        echo ""
        add_reddit
        ;;
    *)
        echo "Usage: $0 [x|reddit|all]"
        exit 1
        ;;
esac

echo ""
echo "Verify with: claude mcp list"
echo ""
echo "Make sure these env vars are set in your shell profile:"
echo "  export X_COOKIES_FILE=/path/to/x_cookies.txt"
echo "  export REDDIT_COOKIES_FILE=/path/to/reddit_cookies.txt"
echo "  export REDDIT_USERNAME=your_username"
