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
