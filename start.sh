#!/bin/bash

# RVTools Start Script
# =====================

PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$PROJECT_DIR"

PORT=${PORT:-5050}
LOG_FILE="$PROJECT_DIR/server.log"
PID_FILE="$PROJECT_DIR/.server.pid"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

start_server() {
    echo -e "${YELLOW}Starting RVTools Server on port $PORT...${NC}"
    
    # Kill existing process if running
    if [ -f "$PID_FILE" ]; then
        kill -9 $(cat "$PID_FILE") 2>/dev/null
        rm "$PID_FILE"
    fi
    
    # Also kill anything on the port
    lsof -ti:$PORT | xargs kill -9 2>/dev/null
    
    # Start server in background
    nohup python3 backend/app.py > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    
    sleep 2
    
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo -e "${GREEN}✓ Server started (PID: $(cat $PID_FILE))${NC}"
        echo -e "${BLUE}  URL: http://localhost:$PORT${NC}"
    else
        echo -e "${RED}✗ Failed to start server. Check logs.${NC}"
    fi
}

stop_server() {
    if [ -f "$PID_FILE" ]; then
        echo -e "${YELLOW}Stopping server...${NC}"
        kill -9 $(cat "$PID_FILE") 2>/dev/null
        rm "$PID_FILE"
        echo -e "${GREEN}✓ Server stopped${NC}"
    else
        echo -e "${YELLOW}No server running${NC}"
    fi
    lsof -ti:$PORT | xargs kill -9 2>/dev/null
}

show_logs() {
    echo -e "${BLUE}=== Last 30 lines of server.log ===${NC}"
    tail -30 "$LOG_FILE" 2>/dev/null || echo "No logs yet"
    echo -e "${BLUE}====================================${NC}"
}

open_browser() {
    echo -e "${GREEN}Opening browser...${NC}"
    open "http://localhost:$PORT" 2>/dev/null || xdg-open "http://localhost:$PORT" 2>/dev/null
}

show_menu() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════╗${NC}"
    echo -e "${BLUE}║     ${GREEN}RVTools Manager${BLUE}            ║${NC}"
    echo -e "${BLUE}╠════════════════════════════════╣${NC}"
    echo -e "${BLUE}║${NC} 1. [r] Restart Server          ${BLUE}║${NC}"
    echo -e "${BLUE}║${NC} 2. [s] Stop Server             ${BLUE}║${NC}"
    echo -e "${BLUE}║${NC} 3. [l] View Logs               ${BLUE}║${NC}"
    echo -e "${BLUE}║${NC} 4. [o] Open Browser            ${BLUE}║${NC}"
    echo -e "${BLUE}║${NC} 5. [q] Quit                    ${BLUE}║${NC}"
    echo -e "${BLUE}╚════════════════════════════════╝${NC}"
}

# Main
echo -e "${GREEN}"
echo "  ____  __     __  _____            _     "
echo " |  _ \\ \\ \\   / / |_   _|___   ___ | |___ "
echo " | |_) | \\ \\ / /    | | / _ \\ / _ \\| / __|"
echo " |  _ <   \\ V /     | || (_) | (_) | \\__ \\"
echo " |_| \\_\\   \\_/      |_| \\___/ \\___/|_|___/"
echo -e "${NC}"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python3 not found${NC}"
    exit 1
fi

# Start server initially
start_server

# Interactive menu loop
while true; do
    show_menu
    read -p "Select option: " choice
    
    case $choice in
        1|r|R)
            start_server
            ;;
        2|s|S)
            stop_server
            ;;
        3|l|L)
            show_logs
            ;;
        4|o|O)
            open_browser
            ;;
        5|q|Q)
            stop_server
            echo -e "${GREEN}Goodbye!${NC}"
            exit 0
            ;;
        *)
            echo -e "${RED}Invalid option${NC}"
            ;;
    esac
done
