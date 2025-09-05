#!/usr/bin/env pwsh
# Development environment startup script for Hackathon Backend

param(
    [string]$Profile = "dev",
    [switch]$Build,
    [switch]$Clean,
    [switch]$Logs
)

# Set error action
$ErrorActionPreference = "Stop"

Write-Host "🚀 Starting Hackathon Backend Development Environment" -ForegroundColor Green
Write-Host "Profile: $Profile" -ForegroundColor Yellow

# Navigate to project root
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

# Check if Docker is running
try {
    docker version | Out-Null
    Write-Host "✅ Docker is running" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker is not running. Please start Docker Desktop first." -ForegroundColor Red
    exit 1
}

# Check if .env file exists
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Write-Host "📋 Copying .env.example to .env" -ForegroundColor Yellow
        Copy-Item ".env.example" ".env"
        Write-Host "⚠️  Please review and update .env file with your configuration" -ForegroundColor Yellow
    } else {
        Write-Host "❌ No .env or .env.example file found" -ForegroundColor Red
        exit 1
    }
}

# Clean up existing containers if requested
if ($Clean) {
    Write-Host "🧹 Cleaning up existing containers and volumes..." -ForegroundColor Yellow
    docker compose down --volumes --remove-orphans
    docker system prune -f
}

# Build images if requested
if ($Build) {
    Write-Host "🔨 Building Docker images..." -ForegroundColor Yellow
    docker compose build --no-cache
}

# Start services
Write-Host "🐳 Starting Docker Compose services..." -ForegroundColor Cyan
try {
    if ($Logs) {
        docker compose up --remove-orphans
    } else {
        docker compose up -d --remove-orphans
        
        Write-Host ""
        Write-Host "🎉 Services started successfully!" -ForegroundColor Green
        Write-Host ""
        Write-Host "📊 Service Status:" -ForegroundColor Cyan
        docker compose ps
        
        Write-Host ""
        Write-Host "🌐 Service URLs:" -ForegroundColor Cyan
        Write-Host "  • PostgreSQL:     localhost:5433" -ForegroundColor White
        Write-Host "  • Keycloak Admin: http://localhost:8070" -ForegroundColor White
        Write-Host "  • Milvus API:     localhost:19530" -ForegroundColor White
        Write-Host "  • Milvus WebUI:   http://localhost:9092" -ForegroundColor White
        Write-Host "  • MinIO Console:  http://localhost:9091" -ForegroundColor White
        
        Write-Host ""
        Write-Host "🔑 Default Credentials:" -ForegroundColor Cyan
        Write-Host "  • Keycloak Admin: admin / admin123" -ForegroundColor White
        Write-Host "  • MinIO:          minioadmin / minioadmin" -ForegroundColor White
        Write-Host "  • Test User:      testuser / testuser123" -ForegroundColor White
        
        Write-Host ""
        Write-Host "📝 To view logs: docker compose logs -f [service-name]" -ForegroundColor Yellow
        Write-Host "🛑 To stop: ./scripts/dev-down.ps1" -ForegroundColor Yellow
    }
} catch {
    Write-Host "❌ Failed to start services: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}