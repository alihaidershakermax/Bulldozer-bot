"""
منشئ PDF — تخطيط عمودي ثنائي اللغة
  • النص الإنجليزي (هايلايت أصفر) فوق
  • الترجمة العربية (أبيض) تحته مباشرة
  • إطار رسمي مزدوج حول الصفحة
  • اسم المطور في وسط رأس كل صفحة (خط عربي)
  • أرقام الصفحات في الأسفل
"""
import os
import logging
from typing import List, Tuple

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    Paragraph, Spacer,
    Frame, PageTemplate, BaseDocTemplate,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import arabic_reshaper
from bidi.algorithm import get_display
from config import FONTS_DIR, DEVELOPER_NAME

logger = logging.getLogger(__name__)

PAGE_W, PAGE_H = A4
MARGIN = 2.0 * cm
BORDER_OUT = 0.50 * cm
BORDER_IN = 0.75 * cm

_AF = "Amiri"
_EF = "TRYGrtsk"
_FB = "Helvetica"
_fonts_ok = False


def _reg():
    global _fonts_ok
    if _fonts_ok:
        return
    for name, fname in (
        (_AF, "Amiri-Regular.ttf"),
        (_EF, "TRYGrtsk-Regular.ttf"),
        ("TRYGrtsk-SemiBold", "TRYGrtsk-SemiBold.ttf"),
    ):
        path = os.path.join(FONTS_DIR, fname)
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
            except Exception:
                pass
    _fonts_ok = True


def _ar(t: str) -> str:
    return get_display(arabic_reshaper.reshape(t))


def _esc(t: str) -> str:
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


C_EN_BG = HexColor("#FFF7D6")
C_BORDER = HexColor("#2c3e50")
C_FOOTER = HexColor("#7f8c8d")
C_MATH = HexColor("#555555")
C_TEXT = HexColor("#1a1a1a")


def _page_deco(canvas, doc):
    canvas.saveState()
    af = _AF if _fonts_ok else _FB
    canvas.setStrokeColor(C_BORDER)
    canvas.setLineWidth(1.6)
    canvas.roundRect(
        BORDER_OUT, BORDER_OUT,
        PAGE_W - 2 * BORDER_OUT,
        PAGE_H - 2 * BORDER_OUT,
        8,
    )
    canvas.setLineWidth(0.5)
    canvas.roundRect(
        BORDER_IN, BORDER_IN,
        PAGE_W - 2 * BORDER_IN,
        PAGE_H - 2 * BORDER_IN,
        6,
    )
    canvas.setFillColor(C_BORDER)
    for x in (BORDER_IN, PAGE_W - BORDER_IN - 3):
        for y in (BORDER_IN, PAGE_H - BORDER_IN - 3):
            canvas.rect(x, y, 3, 3, fill=1, stroke=0)
    dev = DEVELOPER_NAME or "بوت الترجمة"
    dev_ar = _ar(f"مطور البوت: {dev}")
    canvas.setFont(af, 8)
    canvas.setFillColor(C_BORDER)
    canvas.drawCentredString(PAGE_W / 2, PAGE_H - BORDER_IN - 14, dev_ar)
    canvas.setStrokeColor(HexColor("#d7d7d7"))
    canvas.setLineWidth(0.3)
    canvas.line(MARGIN, PAGE_H - BORDER_IN - 18, PAGE_W - MARGIN, PAGE_H - BORDER_IN - 18)
    canvas.setFont(_FB, 8)
    canvas.setFillColor(C_FOOTER)
    canvas.drawCentredString(PAGE_W / 2, BORDER_IN + 5, f"— {doc.page} —")
    canvas.restoreState()


def build_translation_pdf(
    paragraph_pairs: List[Tuple[str, str]],
    output_path: str,
    doc_title: str = "ترجمة",
) -> str:
    _reg()
    af = _AF if _fonts_ok else _FB
    ef = _EF if _fonts_ok else _FB
    doc = BaseDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN + 0.5 * cm,
        bottomMargin=MARGIN,
        title=doc_title,
        author=DEVELOPER_NAME,
    )
    frame = Frame(
        MARGIN, MARGIN,
        PAGE_W - 2 * MARGIN,
        PAGE_H - 2 * MARGIN - 0.5 * cm,
        id="main", showBoundary=0,
    )
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=_page_deco)])

    en_style = ParagraphStyle(
        "EN",
        fontName=ef, fontSize=11, leading=16,
        alignment=TA_LEFT,
        textColor=C_TEXT,
        backColor=C_EN_BG,
        borderPadding=5,
        spaceBefore=0, spaceAfter=0,
    )
    ar_style = ParagraphStyle(
        "AR",
        fontName=af, fontSize=11.2, leading=17,
        alignment=TA_LEFT,
        textColor=C_TEXT,
        spaceBefore=0, spaceAfter=0,
        wordWrap="RTL",
    )
    title_style = ParagraphStyle(
        "TITLE",
        fontName=af, fontSize=13, leading=18,
        alignment=TA_LEFT,
        textColor=C_BORDER,
        spaceAfter=8,
    )
    math_style = ParagraphStyle(
        "MATH",
        fontName="Courier", fontSize=9.5, leading=13,
        alignment=TA_LEFT,
        textColor=C_MATH,
        spaceBefore=0, spaceAfter=0,
    )

    story = [Paragraph(_esc(_ar(doc_title)), title_style), Spacer(1, 4)]
    written = 0

    for idx, (eng, arb) in enumerate(paragraph_pairs, start=1):
        eng = (eng or "").strip()
        arb = (arb or "").strip()
        if not eng and not arb:
            continue
        is_passthrough = (eng == arb and bool(arb))
        if is_passthrough:
            story.append(Paragraph(f"<b>{idx}.</b> {_esc(eng)}", math_style))
        else:
            if eng:
                story.append(Paragraph(f"<b>{idx}.</b> {_esc(eng)}", en_style))
            if eng and arb:
                story.append(Spacer(1, 4))
            if arb:
                story.append(Paragraph(_esc(_ar(arb)), ar_style))
        story.append(Spacer(1, 14))
        written += 1

    if written == 0:
        story.append(Paragraph(_esc(_ar("لم يُعثر على نص قابل للقراءة.")), ar_style))

    if not story:
        story.append(Paragraph(_esc(_ar("لم يُعثر على نص قابل للقراءة.")), ar_style))

    doc.build(story)
    logger.info(f"PDF جاهز ({written} فقرة): {output_path}")
    return output_path