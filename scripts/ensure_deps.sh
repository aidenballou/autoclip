#!/bin/bash
# AutoClip - Dependency checker
# This script verifies all required dependencies are installed

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "╔══════════════════════════════════════════╗"
echo "║       AutoClip Dependency Checker        ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Track if any dependencies are missing
MISSING=0

# Check for Python
echo -n "Checking Python 3.11+... "
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
    if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 11 ]; then
        echo -e "${GREEN}✓ Python $PYTHON_VERSION${NC}"
    else
        echo -e "${YELLOW}⚠ Python $PYTHON_VERSION (3.11+ recommended)${NC}"
    fi
else
    echo -e "${RED}✗ Not found${NC}"
    MISSING=1
fi

# Check for pip
echo -n "Checking pip... "
if command -v pip3 &> /dev/null; then
    echo -e "${GREEN}✓ $(pip3 --version | cut -d' ' -f1-2)${NC}"
else
    echo -e "${RED}✗ Not found${NC}"
    MISSING=1
fi

# Check for Node.js
echo -n "Checking Node.js 18+... "
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version | cut -c2-)
    MAJOR=$(echo $NODE_VERSION | cut -d. -f1)
    if [ "$MAJOR" -ge 18 ]; then
        echo -e "${GREEN}✓ Node.js $NODE_VERSION${NC}"
    else
        echo -e "${YELLOW}⚠ Node.js $NODE_VERSION (18+ recommended)${NC}"
    fi
else
    echo -e "${RED}✗ Not found${NC}"
    MISSING=1
fi

# Check for npm
echo -n "Checking npm... "
if command -v npm &> /dev/null; then
    echo -e "${GREEN}✓ npm $(npm --version)${NC}"
else
    echo -e "${RED}✗ Not found${NC}"
    MISSING=1
fi

# Check for FFmpeg
echo -n "Checking FFmpeg... "
if command -v ffmpeg &> /dev/null; then
    FFMPEG_VERSION=$(ffmpeg -version | head -1 | cut -d' ' -f3)
    echo -e "${GREEN}✓ FFmpeg $FFMPEG_VERSION${NC}"
else
    echo -e "${RED}✗ Not found${NC}"
    echo "  Install with: brew install ffmpeg"
    MISSING=1
fi

# Check for ffprobe
echo -n "Checking ffprobe... "
if command -v ffprobe &> /dev/null; then
    echo -e "${GREEN}✓ Available${NC}"
else
    echo -e "${RED}✗ Not found${NC}"
    echo "  Install with: brew install ffmpeg"
    MISSING=1
fi

# Check for yt-dlp
echo -n "Checking yt-dlp... "
if command -v yt-dlp &> /dev/null; then
    YTDLP_VERSION=$(yt-dlp --version)
    echo -e "${GREEN}✓ yt-dlp $YTDLP_VERSION${NC}"
else
    echo -e "${RED}✗ Not found${NC}"
    echo "  Install with: brew install yt-dlp"
    MISSING=1
fi

echo ""

# Summary
if [ $MISSING -eq 0 ]; then
    echo -e "${GREEN}All dependencies are installed! ✓${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. cd backend && pip install -r requirements.txt"
    echo "  2. cd frontend && npm install"
    echo "  3. ./scripts/dev.sh"
else
    echo -e "${RED}Some dependencies are missing.${NC}"
    echo ""
    echo "Install missing dependencies:"
    echo "  brew install python@3.11 node ffmpeg yt-dlp"
    exit 1
fi

