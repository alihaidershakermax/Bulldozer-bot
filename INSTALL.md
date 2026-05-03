# PDF OCR Translator Bot — Installation Guide

## Quick Start

```bash
cd telegram_pdf_bot
bash setup.sh
# Then edit .env with your token
python bot.py
```

---

## Manual Installation

### 1. System Dependencies

#### Ubuntu / Debian / Replit / Linux
```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng poppler-utils
```

#### macOS
```bash
brew install tesseract poppler
```

#### Windows
- Download Tesseract installer from: https://github.com/UB-Mannheim/tesseract/wiki
- Add Tesseract to your PATH, e.g.: `C:\Program Files\Tesseract-OCR\`
- Set in `.env`: `TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe`

---

### 2. Python Dependencies

```bash
pip install -r requirements.txt
```

Dependencies:
| Package | Purpose |
|---|---|
| `python-telegram-bot` | Telegram Bot API client |
| `pytesseract` | Tesseract OCR Python wrapper |
| `pdf2image` | Convert PDF pages to images |
| `reportlab` | Generate output PDF |
| `deep-translator` | Google Translate API (free, no key needed) |
| `arabic-reshaper` | Reshape Arabic glyphs for correct display |
| `python-bidi` | BiDi algorithm for RTL Arabic text |
| `Pillow` | Image processing |
| `python-dotenv` | Load .env configuration |

---

### 3. Arabic Font

Download Amiri font and place in the `fonts/` directory:

```bash
mkdir -p fonts
wget https://github.com/alif-type/amiri/releases/download/1.000/Amiri-1.000.zip -O fonts/Amiri.zip
cd fonts && unzip Amiri.zip Amiri-Regular.ttf && cd ..
```

Or use the Cairo font — download from Google Fonts:
https://fonts.google.com/specimen/Cairo

Place the `.ttf` file as `fonts/Amiri-Regular.ttf`.

---

### 4. Bot Token

1. Open Telegram, search for `@BotFather`
2. Send `/newbot` and follow the prompts
3. Copy your token
4. Create `.env`:
```
TELEGRAM_BOT_TOKEN=123456789:ABC-your-token-here
```

---

### 5. Run

```bash
python bot.py
```

---

## Project Structure

```
telegram_pdf_bot/
├── bot.py                    # Entry point — starts the Telegram bot
├── config.py                 # Configuration (token, paths, constants)
├── requirements.txt          # Python dependencies
├── setup.sh                  # Automated setup script
├── .env.example              # Template for environment variables
├── fonts/
│   └── Amiri-Regular.ttf    # Arabic font for PDF output
├── handlers/
│   └── pdf_handler.py        # Telegram message handler for PDF uploads
├── processors/
│   ├── pdf_to_images.py      # PDF → PNG pages via pdf2image
│   ├── ocr.py                # Tesseract OCR + text cleaning
│   ├── translator.py         # English → Arabic via deep-translator
│   └── pdf_builder.py        # Builds bilingual output PDF via ReportLab
└── utils/
    └── temp_manager.py       # Temp directory lifecycle management
```

---

## How It Works

```
User sends PDF
     │
     ▼
Download to temp dir
     │
     ▼
pdf2image → PNG per page
     │
     ▼
Tesseract OCR → raw text per page
     │
     ▼
Clean text (noise, broken words, blank lines)
     │
     ▼
Split into lines
     │
     ▼
deep-translator → Arabic line for each English line
     │
     ▼
ReportLab → Bilingual PDF
  (English left-aligned + Arabic right-aligned)
     │
     ▼
Send PDF back to user via Telegram
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `TesseractNotFoundError` | Install tesseract-ocr system package or set `TESSERACT_CMD` in `.env` |
| `PDFPageCountError` | Install `poppler-utils` system package |
| Arabic text appears as boxes | Ensure `fonts/Amiri-Regular.ttf` exists |
| Translation returns original text | Check internet connection; deep-translator uses Google Translate |
| `TELEGRAM_BOT_TOKEN` error | Create `.env` file from `.env.example` and add your token |
