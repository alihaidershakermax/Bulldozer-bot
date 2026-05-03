"""
استخراج النص عبر Tesseract OCR مع تنظيف ذكي وتقسيم دلالي.
"""
import re
import logging
from typing import List
import pytesseract
from PIL import Image
from config import OCR_LANG, TESSERACT_CMD
from processors.scanner_enhance import enhance_for_ocr

logger = logging.getLogger(__name__)
pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

# ── أنماط التنظيف ──────────────────────────────────────────────────────────

# نحافظ على: ASCII + Latin Extended + عربية + علامات ترقيم Unicode شائعة
_NOISE_PATTERN = re.compile(
    "[^"
    r"\x20-\xFF"          # ASCII العادية + Latin Extended (é ü ñ …)
    r"\u0600-\u06FF"      # عربية
    r"\u2010-\u2027"      # واصلات وشرطات واقتباسات (— – ' ' " ")
    r"\u2030-\u205E"      # ترقيم إضافي
    r"\u20A0-\u20CF"      # رموز عملات
    r"\n\r\t"
    "]"
)
_MULTI_SPACE   = re.compile(r" {2,}")
_MULTI_NEWLINE = re.compile(r"\n{3,}")
# أصلح فقط الكلمات المقطوعة بواصلة في نهاية السطر: "inter-\nnational"
_BROKEN_WORD   = re.compile(r"(\w)-\n(\w)")
_SENTENCE_END  = re.compile(r'[.!?)\u201D"]$')

# PSM 3 = تقسيم تلقائي للصفحة (أفضل للوثائق ذات التخطيط المتنوع)
TESSERACT_CONFIG = "--oem 3 --psm 3"


# ─── OCR خام ─────────────────────────────────────────────────────────────────

def extract_text_from_image(image_path: str, enhance: bool = True) -> str:
    """يستخرج النص من الصورة — دالة تزامنية (شغّلها في thread منفصل)."""
    if enhance:
        image_path = enhance_for_ocr(image_path)
    try:
        image = Image.open(image_path)
        raw = pytesseract.image_to_string(image, lang=OCR_LANG, config=TESSERACT_CONFIG)
        return raw
    except Exception as e:
        raise RuntimeError(f"فشل OCR: {e}") from e


# ─── تنظيف النص ──────────────────────────────────────────────────────────────

def clean_text(raw: str) -> str:
    """
    تنظيف خفيف يحافظ على محتوى النص الأصلي:
    - يحذف فقط الرموز غير المطبوعة فعلاً
    - يُصلح الكلمات المقطوعة بواصلة عند نهاية السطر
    - يطبّع المسافات المتعددة والأسطر الفارغة المتكررة
    """
    text = _NOISE_PATTERN.sub("", raw)
    text = _BROKEN_WORD.sub(r"\1\2", text)    # "inter-\nnational" → "international"
    text = _MULTI_SPACE.sub(" ", text)
    text = _MULTI_NEWLINE.sub("\n\n", text)   # أكثر من سطرين فارغين → سطران
    return text.strip()


# ─── تقسيم ذكي إلى فقرات ────────────────────────────────────────────────────

def split_into_paragraphs(text: str) -> List[str]:
    """
    يقسّم النص إلى فقرات دلالية:
      1. الفاصل الأساسي = سطر فارغ (\n\n)
      2. كل الأسطر داخل block واحد تُدمج في فقرة واحدة كاملة
      3. فقرات طويلة جداً (> 1200 حرف) تُقسَّم عند نهايات الجمل فقط
    """
    blocks = re.split(r"\n{2,}", text)
    paragraphs: List[str] = []

    for block in blocks:
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if not lines:
            continue
        # ادمج كل الأسطر في فقرة واحدة — لا تقسيم داخل الـ block
        merged = " ".join(lines)
        paragraphs.append(merged)

    result: List[str] = []
    for p in paragraphs:
        if len(p) > 1200:
            result.extend(_split_long(p))
        else:
            result.append(p)

    return [p.strip() for p in result if len(p.strip()) > 3]


def _split_long(text: str) -> List[str]:
    parts: List[str] = []
    chunk: List[str] = []
    chunk_len = 0
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if chunk_len + len(sentence) > 900 and chunk:
            parts.append(" ".join(chunk))
            chunk = []
            chunk_len = 0
        chunk.append(sentence)
        chunk_len += len(sentence) + 1
    if chunk:
        parts.append(" ".join(chunk))
    return parts


def split_into_lines(text: str) -> List[str]:
    return split_into_paragraphs(text)
