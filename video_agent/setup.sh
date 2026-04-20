#!/usr/bin/env bash
# Prime Land Solutions LLC — Video Agent Setup
# Run this once to install all dependencies.

set -e

echo "======================================================"
echo "  Prime Land Solutions — Video Editing Agent Setup"
echo "======================================================"

# 1. Check ffmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo "[setup] Installing ffmpeg..."
    if command -v apt-get &> /dev/null; then
        sudo apt-get update && sudo apt-get install -y ffmpeg
    elif command -v brew &> /dev/null; then
        brew install ffmpeg
    else
        echo "ERROR: Please install ffmpeg manually from https://ffmpeg.org/download.html"
        exit 1
    fi
else
    echo "[setup] ffmpeg already installed: $(ffmpeg -version 2>&1 | head -1)"
fi

# 2. Python virtual environment
if [ ! -d ".venv" ]; then
    echo "[setup] Creating Python virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate
echo "[setup] Virtual environment active: $(which python)"

# 3. Install Python packages
echo "[setup] Installing Python packages..."
pip install --upgrade pip -q
pip install -r requirements.txt

# 4. Create directories
mkdir -p input output assets/music assets/fonts

echo ""
echo "======================================================"
echo "  Setup complete!"
echo ""
echo "  Next steps:"
echo "  1. Set your Anthropic API key:"
echo "     export ANTHROPIC_API_KEY='your-key-here'"
echo ""
echo "  2. Drop your video files into:  input/"
echo ""
echo "  3. (Optional) Drop background music into: assets/music/"
echo "     Supported: .mp3, .wav"
echo ""
echo "  4. Run the agent:"
echo "     source .venv/bin/activate"
echo "     python main.py input/YOUR_VIDEO.mp4 \\"
echo "       --topic 'drainage installation' \\"
echo "       --platforms instagram_reel tiktok facebook_reel youtube"
echo ""
echo "  Output files will be in: output/"
echo "======================================================"
