#!/usr/bin/env bash
# =============================================================================
# Setup script for PDF OCR Translator Telegram Bot
# =============================================================================
set -e

echo "=== Step 1: Install system dependencies ==="

if command -v apt-get &>/dev/null; then
    sudo apt-get update -y
    sudo apt-get install -y \
        tesseract-ocr \
        tesseract-ocr-eng \
        poppler-utils \
        wget \
        libglib2.0-0 \
        libsm6 \
        libxrender1 \
        libxext6
    echo "✅ System dependencies installed (Debian/Ubuntu)"

elif command -v brew &>/dev/null; then
    brew install tesseract poppler wget
    echo "✅ System dependencies installed (macOS)"

elif command -v dnf &>/dev/null; then
    sudo dnf install -y tesseract tesseract-langpack-eng poppler-utils wget
    echo "✅ System dependencies installed (Fedora/RHEL)"

else
    echo "⚠️  Could not detect package manager. Please install manually:"
    echo "   - tesseract-ocr"
    echo "   - poppler-utils"
fi

echo ""
echo "=== Step 2: Install Python dependencies ==="
pip install --upgrade pip
pip install -r requirements.txt
echo "✅ Python packages installed"

echo ""
echo "=== Step 3: Download Amiri Arabic font ==="
mkdir -p fonts
FONT_URL="https://github.com/alif-type/amiri/releases/download/1.000/Amiri-1.000.zip"
FONT_ZIP="fonts/Amiri.zip"

if [ ! -f "fonts/Amiri-Regular.ttf" ]; then
    echo "Downloading Amiri font…"
    wget -q "$FONT_URL" -O "$FONT_ZIP"
    cd fonts
    unzip -o Amiri.zip "Amiri-Regular.ttf" 2>/dev/null || unzip -o Amiri.zip "*.ttf" 2>/dev/null
    cd ..
    rm -f "$FONT_ZIP"
    echo "✅ Amiri-Regular.ttf saved to fonts/"
else
    echo "✅ Amiri font already present, skipping download."
fi

echo ""
echo "=== Step 4: Configure environment ==="
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "✅ Created .env from .env.example"
    echo "👉 IMPORTANT: Open .env and set your TELEGRAM_BOT_TOKEN"
else
    echo "✅ .env already exists"
fi

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit .env and add your Telegram bot token"
echo "     (Get one from @BotFather on Telegram)"
echo "  2. Run: python bot.py"
echo ""
echo "To verify Tesseract is installed correctly:"
echo "  tesseract --version"
