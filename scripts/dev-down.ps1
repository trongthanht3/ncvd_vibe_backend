#!/usr/bin/env pwsh
# Development environment shutdown script for Hackathon Backend

param(
    [switch]$Clean,
    [switch]$Volumes,
    [switch]$All
)

# Set error action
$ErrorActionPreference = "Stop"

Write-Host "🛑 Stopping Hackathon Backend Development Environment" -ForegroundColor Red

# Navigate to project root
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

# Check if Docker is running
try {
    docker version | Out-Null
    Write-Host "✅ Docker is running" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker is not running" -ForegroundColor Red
    exit 1
}

# Stop services
Write-Host "⏹️  Stopping Docker Compose services..." -ForegroundColor Yellow
try {
    if ($All) {
        Write-Host "🗑️  Removing containers, networks, and volumes..." -ForegroundColor Red
        docker compose down --volumes --remove-orphans
        docker system prune -f
    } elseif ($Volumes) {
        Write-Host "🗑️  Removing containers, networks, and named volumes..." -ForegroundColor Red
        docker compose down --volumes --remove-orphans
    } elseif ($Clean) {
        Write-Host "🧹 Removing containers and networks..." -ForegroundColor Yellow
        docker compose down --remove-orphans
    } else {
        docker compose stop
    }
    
    Write-Host ""
    Write-Host "✅ Services stopped successfully!" -ForegroundColor Green
    
    # Show remaining containers
    $Containers = docker compose ps -q
    if ($Containers) {
        Write-Host ""
        Write-Host "📊 Remaining containers:" -ForegroundColor Cyan
        docker compose ps
    } else {
        Write-Host ""
        Write-Host "🎉 All containers have been stopped and removed." -ForegroundColor Green
    }
    
} catch {
    Write-Host "❌ Failed to stop services: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "💡 Usage tips:" -ForegroundColor Cyan
Write-Host "  • Use -Clean to remove containers and networks" -ForegroundColor White
Write-Host "  • Use -Volumes to also remove persistent data" -ForegroundColor White
Write-Host "  • Use -All for complete cleanup including system prune" -ForegroundColor White