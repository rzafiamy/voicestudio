#!/bin/bash

# Qwen3-TTS Setup Script
# This script creates a virtual environment and installs all dependencies.

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Qwen3-TTS Setup ===${NC}"

# 1. Check for Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: python3 is not installed.${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo -e "${GREEN}Using Python $PYTHON_VERSION${NC}"

# 2. Setup Virtual Environment
if command -v uv &> /dev/null; then
    echo -e "${BLUE}Found 'uv', using it for faster setup...${NC}"
    uv venv venv
    source venv/bin/activate
    echo -e "${BLUE}Installing dependencies...${NC}"
    uv pip install -r requirements.txt
else
    echo -e "${BLUE}Creating virtual environment 'venv'...${NC}"
    python3 -m venv venv
    source venv/bin/activate
    echo -e "${BLUE}Installing dependencies (this may take a while)...${NC}"
    pip install --upgrade pip
    pip install -r requirements.txt
fi

# 3. Handle Flash Attention
echo -e "${BLUE}Checking for Flash Attention...${NC}"
if [[ "$PYTHON_VERSION" == "3.11" ]]; then
    if [ -f "flash_attn-2.6.3+cu128torch2.10-cp311-cp311-linux_x86_64.whl" ]; then
        echo -e "${YELLOW}Python 3.11 detected. Installing provided Flash Attention wheel...${NC}"
        pip install flash_attn-2.6.3+cu128torch2.10-cp311-cp311-linux_x86_64.whl || echo -e "${RED}Wheel installation failed, skipping...${NC}"
    fi
else
    echo -e "${YELLOW}Python $PYTHON_VERSION detected. Skipping provided cp311 wheel.${NC}"
    echo -e "${YELLOW}Attempting to install flash-attn via pip (requires CUDA)...${NC}"
    # We don't force it as it often requires heavy compilation
    pip install flash-attn --no-build-isolation || echo -e "${YELLOW}Flash Attention installation skipped or failed. This is fine, the app will still work.${NC}"
fi

# 4. Success
echo -e "${GREEN}=== Setup Complete! ===${NC}"
echo -e "${BLUE}To start the server, run:${NC}"
echo -e "${YELLOW}source venv/bin/activate${NC}"
echo -e "${YELLOW}python app.py --model ./Qwen3-TTS-12Hz-1.7B-CustomVoice${NC}"
