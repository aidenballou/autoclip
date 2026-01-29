#!/usr/bin/env pwsh
# AutoClip - Production build script (Windows)
# Builds frontend and configures backend to serve it

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Write-Host "==========================================="
Write-Host "        AutoClip Production Build          " -ForegroundColor Cyan
Write-Host "==========================================="
Write-Host ""

# Build frontend
Write-Host "Building frontend..." -ForegroundColor Green
$frontendDir = Join-Path $ProjectRoot "frontend"
Set-Location $frontendDir

# Install dependencies if needed
if (-not (Test-Path "node_modules")) {
    npm install
}

npm run build

Write-Host ""
Write-Host "Frontend built successfully!" -ForegroundColor Green
Write-Host "Output: $frontendDir\dist"
Write-Host ""
Write-Host "To run in production mode:"
Write-Host "  1. cd backend"
Write-Host "  2. `$env:SERVE_FRONTEND=`$true"
Write-Host "  3. python -m uvicorn app.main:app --port 8000"
Write-Host ""
Write-Host "Then open http://localhost:8000"
