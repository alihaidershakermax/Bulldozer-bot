import os
from dotenv import load_dotenv

load_dotenv()

# -- مطلوب
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN غير محدد في متغيرات البيئة.")

# -- اختياري
CONVEX_URL:           str = os.getenv("CONVEX_URL", "")
TELEGRAM_LOG_CHANNEL: str = os.getenv("TELEGRAM_LOG_CHANNEL", "")
ADMIN_IDS_RAW:        str = os.getenv("ADMIN_IDS", "")

# -- Tesseract
TESSERACT_CMD: str = os.getenv("TESSERACT_CMD", "tesseract")

# -- حدود
MAX_FILE_SIZE_MB: int = 50

# -- مسارات
_BASE      = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR:  str = os.path.join(_BASE, "tmp")
FONTS_DIR: str = os.path.join(_BASE, "fonts")

# -- OCR / PDF
OCR_LANG: str = "eng"
PDF_DPI:  int = 250

# -- اسم البوت
BOT_NAME: str = os.getenv("BOT_NAME", "بلدوزر")

# -- صورة الترحيب
WELCOME_PHOTO: str = os.getenv("WELCOME_PHOTO", "https://a.top4top.io/p_3775becgi1.jpg")

# -- معلومات المطور
DEVELOPER_NAME:      str = os.getenv("DEVELOPER_NAME",      "علي الاكبر حيدر شاكر")
DEVELOPER_BIO:       str = os.getenv("DEVELOPER_BIO",       "المدير التنفيذي لشركة صيادين العراق\nمطور برمجيات | طالب هندسة")
DEVELOPER_USERNAME:  str = os.getenv("DEVELOPER_USERNAME",  "")
DEVELOPER_INSTAGRAM: str = os.getenv("DEVELOPER_INSTAGRAM", "https://www.instagram.com/dxet1?igsh=N20wNnJ5bjh0bmJx")
DEVELOPER_CHANNEL:   str = os.getenv("DEVELOPER_CHANNEL",   "")
DEVELOPER_CONTACT:   str = os.getenv("DEVELOPER_CONTACT",   "")
DEVELOPER_PHOTO:     str = os.getenv("DEVELOPER_PHOTO",     "https://k.top4top.io/p_37754v4eb1.jpg")
DEVELOPER_WEBSITE:   str = os.getenv("DEVELOPER_WEBSITE",   "https://alialakbarhaidarshaker.vercel.app/")
