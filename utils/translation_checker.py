"""
فاحص جودة الترجمة
يصنّف كل فقرة:
  ✅ مترجمة  — النص العربي مختلف وفيه عربي كافي
  📐 رياضيات — النص ما تغيّر (passthrough)
  ❌ فاشلة   — النص رجع إنجليزي أو ناقص
ويُنتج تقريراً مختصراً يُرسل للمستخدم.
"""
from typing import List, Tuple

_PREVIEW_LEN = 55   # طول المعاينة لكل فقرة في التقرير
_MAX_FAILS   = 20   # أقصى عدد فقرات فاشلة تُظهر بالتفصيل


def _ar_ratio(text: str) -> float:
    chars = [c for c in text if c.isalpha()]
    if not chars:
        return 0.0
    ar = sum(1 for c in chars if "\u0600" <= c <= "\u06FF")
    return ar / len(chars)


def _classify(eng: str, arb: str) -> str:
    """
    يُصنّف الزوج (إنجليزي، عربي):
    "math"        → passthrough (eng == arb)
    "translated"  → عربي صحيح
    "failed"      → فشلت الترجمة
    """
    eng = (eng or "").strip()
    arb = (arb or "").strip()

    # passthrough / رياضيات
    if eng == arb:
        return "math"

    # فارغ أو رجع نفس الإنجليزي
    if not arb or arb.lower() == eng.lower():
        return "failed"

    # نسبة عربي منخفضة جداً → فشل
    if _ar_ratio(arb) < 0.30:
        return "failed"

    return "translated"


def build_report(
    pairs: List[Tuple[str, str]],
    title: str = "",
) -> str:
    """
    يبني رسالة تقرير HTML تُرسل للمستخدم.
    pairs: قائمة (نص_إنجليزي, نص_عربي)
    """
    translated, math_count, failed = [], [], []

    for i, (eng, arb) in enumerate(pairs, 1):
        status = _classify(eng, arb)
        preview = (eng or "")[:_PREVIEW_LEN].replace("&", "&amp;").replace("<", "&lt;")
        if preview and len(eng) > _PREVIEW_LEN:
            preview += "…"

        if status == "math":
            math_count.append((i, preview))
        elif status == "failed":
            failed.append((i, preview))
        else:
            translated.append((i, preview))

    total = len(pairs)
    t = len(translated)
    m = len(math_count)
    f = len(failed)

    header = f"📊 <b>تقرير الترجمة</b>"
    if title:
        header += f" — <i>{title}</i>"

    summary = (
        f"\n├ ✅ مترجمة:  <b>{t}</b>"
        f"\n├ 📐 رياضيات: <b>{m}</b>"
        f"\n└ ❌ فاشلة:   <b>{f}</b>"
        f"\n<i>المجموع: {total} فقرة</i>"
    )

    lines = [header, summary]

    if f == 0:
        lines.append("\n<b>ما اكو فقرات فاشلة — كل شيء انترجم ✅</b>")
    else:
        lines.append(f"\n<b>⚠️ الفقرات الفاشلة ({min(f, _MAX_FAILS)} من {f}):</b>")
        for idx, (i, preview) in enumerate(failed[:_MAX_FAILS]):
            lines.append(f"❌ §{i}: <code>{preview}</code>")
        if f > _MAX_FAILS:
            lines.append(f"<i>…و{f - _MAX_FAILS} فقرة أخرى</i>")

    return "\n".join(lines)


def per_line_report(
    pairs: List[Tuple[str, str]],
    max_lines: int = 80,
) -> str:
    """
    تقرير مفصّل سطر-بسطر (مناسب للملفات الصغيرة).
    يُظهر كل فقرة مع حالتها.
    """
    lines = ["📋 <b>تفصيل الفقرات:</b>\n"]
    icons = {"translated": "✅", "math": "📐", "failed": "❌"}

    for i, (eng, arb) in enumerate(pairs[:max_lines], 1):
        status  = _classify(eng, arb)
        icon    = icons[status]
        preview = (eng or "")[:_PREVIEW_LEN].replace("&", "&amp;").replace("<", "&lt;")
        if preview and len(eng) > _PREVIEW_LEN:
            preview += "…"
        lines.append(f"{icon} §{i}: <code>{preview}</code>")

    if len(pairs) > max_lines:
        lines.append(f"\n<i>…والباقي {len(pairs) - max_lines} فقرة</i>")

    return "\n".join(lines)
