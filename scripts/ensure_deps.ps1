#!/usr/bin/env pwsh
# AutoClip - Dependency checker (Windows)
# Verifies all required dependencies are installed

$ErrorActionPreference = "Stop"

Write-Host "==========================================="
Write-Host "       AutoClip Dependency Checker         "
Write-Host "==========================================="
Write-Host ""

$missing = $false

function Write-Ok($message) {
    Write-Host "OK  $message" -ForegroundColor Green
}

function Write-Warn($message) {
    Write-Host "WARN $message" -ForegroundColor Yellow
}

function Write-Err($message) {
    Write-Host "ERR $message" -ForegroundColor Red
}

# Check for Python
Write-Host -NoNewline "Checking Python 3.11+... "
$pythonCmd = $null
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCmd = @("python")
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCmd = @("py", "-3")
}

if ($pythonCmd) {
    $pyVersion = & $pythonCmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    $parts = $pyVersion.Split(".")
    $major = [int]$parts[0]
    $minor = [int]$parts[1]
    if ($major -ge 3 -and $minor -ge 11) {
        Write-Ok "Python $pyVersion"
    } else {
        Write-Warn "Python $pyVersion (3.11+ recommended)"
    }
} else {
    Write-Err "Not found"
    $missing = $true
}

# Check for pip
Write-Host -NoNewline "Checking pip... "
if ($pythonCmd) {
    try {
        $pipVersion = & $pythonCmd -m pip --version 2>$null
        if ($pipVersion) {
            Write-Ok ($pipVersion.Split(" ")[0..1] -join " ")
        } else {
            Write-Err "Not found"
            $missing = $true
        }
    } catch {
        Write-Err "Not found"
        $missing = $true
    }
} else {
    Write-Err "Not found"
    $missing = $true
}

# Check for Node.js
Write-Host -NoNewline "Checking Node.js 18+... "
if (Get-Command node -ErrorAction SilentlyContinue) {
    $nodeVersion = (node --version).TrimStart("v")
    $major = [int]$nodeVersion.Split(".")[0]
    if ($major -ge 18) {
        Write-Ok "Node.js $nodeVersion"
    } else {
        Write-Warn "Node.js $nodeVersion (18+ recommended)"
    }
} else {
    Write-Err "Not found"
    $missing = $true
}

# Check for npm
Write-Host -NoNewline "Checking npm... "
if (Get-Command npm -ErrorAction SilentlyContinue) {
    Write-Ok ("npm " + (npm --version))
} else {
    Write-Err "Not found"
    $missing = $true
}

# Check for FFmpeg
Write-Host -NoNewline "Checking FFmpeg... "
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    $ffmpegVersion = (ffmpeg -version | Select-Object -First 1).Split(" ")[2]
    Write-Ok "FFmpeg $ffmpegVersion"
} else {
    Write-Err "Not found"
    Write-Host "  Install with: winget install Gyan.FFmpeg | choco install ffmpeg | scoop install ffmpeg"
    $missing = $true
}

# Check for ffprobe
Write-Host -NoNewline "Checking ffprobe... "
if (Get-Command ffprobe -ErrorAction SilentlyContinue) {
    Write-Ok "Available"
} else {
    Write-Err "Not found"
    Write-Host "  Install with: winget install Gyan.FFmpeg | choco install ffmpeg | scoop install ffmpeg"
    $missing = $true
}

# Check for yt-dlp
Write-Host -NoNewline "Checking yt-dlp... "
if (Get-Command yt-dlp -ErrorAction SilentlyContinue) {
    $ytdlpVersion = yt-dlp --version
    Write-Ok "yt-dlp $ytdlpVersion"
} else {
    Write-Err "Not found"
    Write-Host "  Install with: winget install yt-dlp.yt-dlp | choco install yt-dlp | scoop install yt-dlp"
    $missing = $true
}

Write-Host ""

if (-not $missing) {
    Write-Host "All dependencies are installed!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:"
    Write-Host "  1. cd backend; python -m venv venv; .\\venv\\Scripts\\Activate.ps1; pip install -r requirements.txt"
    Write-Host "  2. cd ..\\frontend; npm install"
    Write-Host "  3. .\\scripts\\dev.ps1"
} else {
    Write-Host "Some dependencies are missing." -ForegroundColor Red
    Write-Host ""
    Write-Host "Install missing dependencies (choose one):"
    Write-Host "  winget install Python.Python.3.11 OpenJS.NodeJS.LTS Gyan.FFmpeg yt-dlp.yt-dlp"
    Write-Host "  choco install python nodejs-lts ffmpeg yt-dlp -y"
    Write-Host "  scoop install python nodejs ffmpeg yt-dlp"
    exit 1
}
