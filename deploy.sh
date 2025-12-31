#!/bin/bash

# Git Deploy Script for RVTools
# ==============================

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$PROJECT_DIR"

echo -e "${BLUE}"
echo "╔════════════════════════════════════╗"
echo "║     RVTools GitHub Deploy          ║"
echo "╚════════════════════════════════════╝"
echo -e "${NC}"

# Check if git repo
if [ ! -d ".git" ]; then
    echo -e "${RED}Error: Not a git repository${NC}"
    exit 1
fi

# Show status
echo -e "${YELLOW}Current changes:${NC}"
git status --short

# Check if there are changes
if git diff-index --quiet HEAD -- 2>/dev/null; then
    echo -e "${GREEN}No changes to commit.${NC}"
    exit 0
fi

echo ""

# Ask for commit message
read -p "Enter commit message (or 'q' to quit): " message

if [ "$message" = "q" ] || [ "$message" = "Q" ]; then
    echo -e "${YELLOW}Cancelled.${NC}"
    exit 0
fi

if [ -z "$message" ]; then
    message="Update $(date '+%Y-%m-%d %H:%M')"
    echo -e "${YELLOW}Using default message: $message${NC}"
fi

# Stage all changes
echo -e "${BLUE}Staging changes...${NC}"
git add -A

# Commit
echo -e "${BLUE}Committing...${NC}"
git commit -m "$message"

# Push
echo -e "${BLUE}Pushing to origin...${NC}"
git push origin main

if [ $? -eq 0 ]; then
    echo -e "${GREEN}"
    echo "╔════════════════════════════════════╗"
    echo "║  ✓ Successfully pushed to GitHub!  ║"
    echo "╚════════════════════════════════════╝"
    echo -e "${NC}"
else
    echo -e "${RED}Push failed. Check your connection or credentials.${NC}"
    exit 1
fi
