#!/usr/bin/env pwsh
# AutoClip - Development server launcher (Windows)
# Runs both backend and frontend concurrently

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Write-Host "==========================================="
Write-Host "        AutoClip Development Server        " -ForegroundColor Cyan
Write-Host "==========================================="
Write-Host ""

# Check if dependencies are installed
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Host "Warning: ffmpeg not found. Video processing will not work." -ForegroundColor Yellow
    Write-Host "Install with: winget install Gyan.FFmpeg | choco install ffmpeg | scoop install ffmpeg"
}

if (-not (Get-Command yt-dlp -ErrorAction SilentlyContinue)) {
    Write-Host "Warning: yt-dlp not found. YouTube downloads will not work." -ForegroundColor Yellow
    Write-Host "Install with: winget install yt-dlp.yt-dlp | choco install yt-dlp | scoop install yt-dlp"
}

# Create data directory
$projectsDir = Join-Path $ProjectRoot "backend\data\projects"
New-Item -ItemType Directory -Force -Path $projectsDir | Out-Null

# Start backend
Write-Host "Starting backend server on http://localhost:8000" -ForegroundColor Green
$backendDir = Join-Path $ProjectRoot "backend"
Set-Location $backendDir

# Create virtual environment if it doesn't exist
if (-not (Test-Path "venv")) {
    Write-Host "Creating Python virtual environment..."
    python -m venv venv
}

# Activate virtual environment and install dependencies
$activateScript = Join-Path $backendDir "venv\Scripts\Activate.ps1"
. $activateScript
pip install -q -r requirements.txt

# Run backend in background
$script:backend = Start-Process -FilePath python -ArgumentList "-m", "uvicorn", "app.main:app", "--reload", "--port", "8000" -WorkingDirectory $backendDir -PassThru

# Wait a bit for backend to start
Start-Sleep -Seconds 2

# Start frontend
Write-Host "Starting frontend server on http://localhost:5173" -ForegroundColor Green
$frontendDir = Join-Path $ProjectRoot "frontend"
Set-Location $frontendDir

# Install dependencies if needed
if (-not (Test-Path "node_modules")) {
    Write-Host "Installing frontend dependencies..."
    npm install
}

# Run frontend in background
$script:frontend = Start-Process -FilePath npm -ArgumentList "run", "dev" -WorkingDirectory $frontendDir -PassThru

Write-Host ""
Write-Host "===========================================" -ForegroundColor Green
Write-Host "  AutoClip is running!" -ForegroundColor Green
Write-Host "===========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Frontend: http://localhost:5173"
Write-Host "  Backend:  http://localhost:8000"
Write-Host "  API Docs: http://localhost:8000/docs"
Write-Host ""
Write-Host "Press Ctrl+C to stop all servers" -ForegroundColor Yellow
Write-Host ""

$script:cleanup = {
    Write-Host ""
    Write-Host "Shutting down servers..." -ForegroundColor Yellow
    if ($script:backend -and -not $script:backend.HasExited) {
        Stop-Process -Id $script:backend.Id -Force
    }
    if ($script:frontend -and -not $script:frontend.HasExited) {
        Stop-Process -Id $script:frontend.Id -Force
    }
}

Register-EngineEvent PowerShell.Exiting -Action $script:cleanup | Out-Null
[Console]::CancelKeyPress += {
    param($sender, $e)
    $e.Cancel = $true
    & $script:cleanup
    exit
}

# Wait for both processes
Wait-Process -Id $script:backend.Id, $script:frontend.Id
