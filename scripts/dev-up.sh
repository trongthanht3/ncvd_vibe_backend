#!/bin/bash
# Development environment startup script for Hackathon Backend

set -e

PROFILE="dev"
BUILD=false
CLEAN=false
LOGS=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --profile)
            PROFILE="$2"
            shift 2
            ;;
        --build)
            BUILD=true
            shift
            ;;
        --clean)
            CLEAN=true
            shift
            ;;
        --logs)
            LOGS=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "🚀 Starting Hackathon Backend Development Environment"
echo "Profile: $PROFILE"

# Navigate to project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Check if Docker is running
if ! docker version >/dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi
echo "✅ Docker is running"

# Check if .env file exists
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "📋 Copying .env.example to .env"
        cp ".env.example" ".env"
        echo "⚠️  Please review and update .env file with your configuration"
    else
        echo "❌ No .env or .env.example file found"
        exit 1
    fi
fi

# Clean up existing containers if requested
if [ "$CLEAN" = true ]; then
    echo "🧹 Cleaning up existing containers and volumes..."
    docker compose down --volumes --remove-orphans
    docker system prune -f
fi

# Build images if requested
if [ "$BUILD" = true ]; then
    echo "🔨 Building Docker images..."
    docker compose build --no-cache
fi

# Start services
echo "🐳 Starting Docker Compose services..."
if [ "$LOGS" = true ]; then
    docker compose up --remove-orphans
else
    docker compose up -d --remove-orphans
    
    echo ""
    echo "🎉 Services started successfully!"
    echo ""
    echo "📊 Service Status:"
    docker compose ps
    
    echo ""
    echo "🌐 Service URLs:"
    echo "  • PostgreSQL:     localhost:5433"
    echo "  • Keycloak Admin: http://localhost:8070"
    echo "  • Milvus API:     localhost:19530"
    echo "  • Milvus WebUI:   http://localhost:9092"
    echo "  • MinIO Console:  http://localhost:9091"
    
    echo ""
    echo "🔑 Default Credentials:"
    echo "  • Keycloak Admin: admin / admin123"
    echo "  • MinIO:          minioadmin / minioadmin"
    echo "  • Test User:      testuser / testuser123"
    
    echo ""
    echo "📝 To view logs: docker compose logs -f [service-name]"
    echo "🛑 To stop: ./scripts/dev-down.sh"
fi