#!/bin/bash
# AutoClip - Development server launcher
# Runs both backend and frontend concurrently

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔══════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         AutoClip Development Server      ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════╝${NC}"
echo ""

# Check if dependencies are installed
if ! command -v ffmpeg &> /dev/null; then
    echo -e "${YELLOW}Warning: ffmpeg not found. Video processing will not work.${NC}"
    echo "Install with: brew install ffmpeg"
fi

if ! command -v yt-dlp &> /dev/null; then
    echo -e "${YELLOW}Warning: yt-dlp not found. YouTube downloads will not work.${NC}"
    echo "Install with: brew install yt-dlp"
fi

# Create data directory
mkdir -p "$PROJECT_ROOT/backend/data/projects"

# Function to cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down servers...${NC}"
    kill $(jobs -p) 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start backend
echo -e "${GREEN}Starting backend server on http://localhost:8000${NC}"
cd "$PROJECT_ROOT/backend"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment and install dependencies
source venv/bin/activate
pip install -q -r requirements.txt

# Run backend in background
python -m uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!

# Wait a bit for backend to start
sleep 2

# Start frontend
echo -e "${GREEN}Starting frontend server on http://localhost:5173${NC}"
cd "$PROJECT_ROOT/frontend"

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

# Run frontend in background
npm run dev &
FRONTEND_PID=$!

echo ""
echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo -e "${GREEN}  AutoClip is running!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo ""
echo "  Frontend: http://localhost:5173"
echo "  Backend:  http://localhost:8000"
echo "  API Docs: http://localhost:8000/docs"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all servers${NC}"
echo ""

# Wait for both processes
wait

