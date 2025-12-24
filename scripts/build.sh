#!/bin/bash
# AutoClip - Production build script
# Builds frontend and configures backend to serve it

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔══════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         AutoClip Production Build        ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════╝${NC}"
echo ""

# Build frontend
echo -e "${GREEN}Building frontend...${NC}"
cd "$PROJECT_ROOT/frontend"

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    npm install
fi

npm run build

echo ""
echo -e "${GREEN}Frontend built successfully!${NC}"
echo "Output: $PROJECT_ROOT/frontend/dist"
echo ""
echo "To run in production mode:"
echo "  1. cd backend"
echo "  2. export SERVE_FRONTEND=true"
echo "  3. python -m uvicorn app.main:app --port 8000"
echo ""
echo "Then open http://localhost:8000"

