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

# 3. Handle Flash Attention (optional, recommended for CUDA GPUs)
echo -e "${BLUE}Attempting to install Flash Attention (optional)...${NC}"
echo -e "${YELLOW}If this fails, download a pre-built wheel from:${NC}"
echo -e "${YELLOW}  https://github.com/Dao-AILab/flash-attention/releases${NC}"
echo -e "${YELLOW}Then run: pip install <wheel-file>${NC}"
pip install flash-attn --no-build-isolation || echo -e "${YELLOW}Flash Attention skipped — the app will work without it.${NC}"

# 4. Success
echo -e "${GREEN}=== Setup Complete! ===${NC}"
echo -e "${BLUE}To start the server, run:${NC}"
echo -e "${YELLOW}source venv/bin/activate${NC}"
echo -e "${YELLOW}python app.py --model ./Qwen3-TTS-12Hz-1.7B-CustomVoice${NC}"
