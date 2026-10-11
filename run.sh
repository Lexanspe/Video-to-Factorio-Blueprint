#!/usr/bin/env bash
# ==============================================================================
# Factorio 2.0 Video to Blueprint Generator — Linux & macOS Launcher
# ==============================================================================

set -e

# Change directory to the repository root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Detect Python executable
if command -v python3 &>/dev/null; then
    PYTHON_BIN="python3"
elif command -v python &>/dev/null; then
    PYTHON_BIN="python"
else
    echo "❌ Error: Python 3 could not be found."
    echo "Please install Python 3.10 or newer (e.g., sudo apt install python3 python3-pip or brew install python)."
    exit 1
fi

echo "======================================================================"
echo "⚡ Factorio 2.0 Video-to-Blueprint Generator"
echo "💻 Platform: $(uname -s) ($(uname -m)) | Python: $($PYTHON_BIN --version)"
echo "======================================================================"

# Check Python dependencies
if ! $PYTHON_BIN -c "import cv2, PIL, numpy" &>/dev/null; then
    echo "📦 Required packages missing. Installing dependencies from requirements.txt..."
    $PYTHON_BIN -m pip install -r requirements.txt
fi

# Run the cross-platform Web GUI server
exec $PYTHON_BIN server.py "$@"
