#!/bin/bash
# Development environment shutdown script for Hackathon Backend

set -e

CLEAN=false
VOLUMES=false
ALL=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --clean)
            CLEAN=true
            shift
            ;;
        --volumes)
            VOLUMES=true
            shift
            ;;
        --all)
            ALL=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "🛑 Stopping Hackathon Backend Development Environment"

# Navigate to project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Check if Docker is running
if ! docker version >/dev/null 2>&1; then
    echo "❌ Docker is not running"
    exit 1
fi
echo "✅ Docker is running"

# Stop services
echo "⏹️  Stopping Docker Compose services..."
if [ "$ALL" = true ]; then
    echo "🗑️  Removing containers, networks, and volumes..."
    docker compose down --volumes --remove-orphans
    docker system prune -f
elif [ "$VOLUMES" = true ]; then
    echo "🗑️  Removing containers, networks, and named volumes..."
    docker compose down --volumes --remove-orphans
elif [ "$CLEAN" = true ]; then
    echo "🧹 Removing containers and networks..."
    docker compose down --remove-orphans
else
    docker compose stop
fi

echo ""
echo "✅ Services stopped successfully!"

# Show remaining containers
CONTAINERS=$(docker compose ps -q)
if [ -n "$CONTAINERS" ]; then
    echo ""
    echo "📊 Remaining containers:"
    docker compose ps
else
    echo ""
    echo "🎉 All containers have been stopped and removed."
fi

echo ""
echo "💡 Usage tips:"
echo "  • Use --clean to remove containers and networks"
echo "  • Use --volumes to also remove persistent data"
echo "  • Use --all for complete cleanup including system prune"