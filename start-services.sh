#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

PROJECT_DIR="/Users/kushbhuwalka/Documents/bid-buddy"

echo "======================================"
echo "Starting Bid Buddy Services"
echo "======================================"

# Function to check if a port is in use
check_port() {
    lsof -i:$1 > /dev/null 2>&1
    return $?
}

# Function to wait for service to be ready
wait_for_service() {
    local url=$1
    local name=$2
    local max_attempts=30
    local attempt=0

    echo -n "Waiting for $name to start..."
    while [ $attempt -lt $max_attempts ]; do
        if curl -s "$url" > /dev/null 2>&1; then
            echo -e " ${GREEN}✓${NC}"
            return 0
        fi
        echo -n "."
        sleep 1
        attempt=$((attempt + 1))
    done
    echo -e " ${RED}✗${NC}"
    return 1
}

# 1. Check and start Frontend (port 3000)
echo ""
echo "Checking Frontend (port 3000)..."
if check_port 3000; then
    echo -e "${GREEN}✓ Frontend is already running${NC}"
else
    echo -e "${YELLOW}⚠ Frontend not running, starting...${NC}"
    cd "$PROJECT_DIR"
    npm run dev > /tmp/bid-buddy-frontend.log 2>&1 &
    echo "Frontend PID: $!"
    wait_for_service "http://localhost:3000" "Frontend"
fi

# 2. Check and start Backend (port 8000)
echo ""
echo "Checking Backend (port 8000)..."
if check_port 8000; then
    echo -e "${GREEN}✓ Backend is already running${NC}"
else
    echo -e "${YELLOW}⚠ Backend not running, starting...${NC}"
    cd "$PROJECT_DIR/backend"
    python3 main.py > /tmp/bid-buddy-backend.log 2>&1 &
    echo "Backend PID: $!"
    wait_for_service "http://localhost:8000/health" "Backend"
fi

# 3. Check and start ngrok
echo ""
echo "Checking ngrok..."
if pgrep -f "ngrok http 8000" > /dev/null; then
    echo -e "${GREEN}✓ ngrok is already running${NC}"
    # Get the public URL
    sleep 1
    NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "import sys, json; data = json.load(sys.stdin); print(data['tunnels'][0]['public_url'] if data.get('tunnels') else '')" 2>/dev/null)
    if [ ! -z "$NGROK_URL" ]; then
        echo -e "   Public URL: ${GREEN}$NGROK_URL${NC}"
    fi
else
    echo -e "${YELLOW}⚠ ngrok not running, starting...${NC}"
    ngrok http 8000 > /dev/null 2>&1 &
    echo "ngrok PID: $!"
    sleep 3
    NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "import sys, json; data = json.load(sys.stdin); print(data['tunnels'][0]['public_url'] if data.get('tunnels') else '')" 2>/dev/null)
    if [ ! -z "$NGROK_URL" ]; then
        echo -e "${GREEN}✓ ngrok started${NC}"
        echo -e "   Public URL: ${GREEN}$NGROK_URL${NC}"
    else
        echo -e "${RED}✗ Failed to get ngrok URL${NC}"
    fi
fi

# Summary
echo ""
echo "======================================"
echo "Service Status Summary"
echo "======================================"
echo -e "Frontend:  http://localhost:3000"
echo -e "Backend:   http://localhost:8000"
if [ ! -z "$NGROK_URL" ]; then
    echo -e "ngrok:     $NGROK_URL"
    echo ""
    echo -e "Webhook URL: ${GREEN}$NGROK_URL/webhooks/agentmail${NC}"
fi
echo ""
echo "Log files:"
echo "  Frontend: /tmp/bid-buddy-frontend.log"
echo "  Backend:  /tmp/bid-buddy-backend.log"
echo "  ngrok UI: http://localhost:4040"
echo "======================================"
