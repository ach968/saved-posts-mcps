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
