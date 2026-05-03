"""
مترجم فقرات — إنجليزي → عربي
=================================
المحركات:
- Bing / Microsoft / Google / Yandex
- بدون API key
- async عبر asyncio.to_thread
- 5 فقرات بالتوازي
- فحص جودة الترجمة — لو فشلت تُبقى النص الإنجليزي الأصلي كاملاً
"""
import re
import asyncio
import logging
from typing import List, Tuple, Callable, Awaitable, Optional

logger = logging.getLogger(__name__)

_MAX_CONCURRENCY = 5
_semaphore: Optional[asyncio.Semaphore] = None

# الحد الأقصى لكل chunk قبل التقسيم (Bing يتعثر فوق 2000)
_CHUNK_LIMIT = 2000


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(_MAX_CONCURRENCY)
    return _semaphore


# ─── كشف المحتوى الرياضي / العلمي ────────────────────────────────────────────

_MATH_UNICODE = set(
    "∫∑∏√∞∂∇∀∃∈∉⊆⊂∪∩≤≥≠±×÷∝≈≡∼⊕⊗⊥∠∥"
    "αβγδεζηθικλμνξπρστυφχψω"
    "ΑΒΓΔΕΖΗΘΚΛΜΝΞΠΡΣΤΥΦΧΨΩ"
    "⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺ₐₑₒₓ₀₁₂₃₄₅₆₇₈₉"
)

_PAT_LATEX       = re.compile(r"\\[a-zA-Z]+\s*[\{\(]|\\[a-zA-Z]+")
_PAT_DOLLAR      = re.compile(r"\$[^$]{1,}\$")
_PAT_BRACKET_EQ  = re.compile(r"\\\[[^\]]{2,}\\\]")
_PAT_SUPERSCRIPT = re.compile(r"[a-zA-Z]\^[\{\d\-\+\(]")
_PAT_SUBSCRIPT   = re.compile(r"[a-zA-Z]_[\{\(a-zA-Z0-9]")
_PAT_EQ_ASSIGN   = re.compile(
    r"[a-zA-Zα-ωΑ-Ωφμλκσρτπθε₀₁₂₃₄₅₆₇₈₉]\s*=\s*[\d\-\+\(a-zA-Z]"
)
_PAT_FRACTION    = re.compile(r"[a-zA-Zα-ωΑ-Ω\d]\s*/\s*[a-zA-Zα-ωΑ-Ω\d]")
_PAT_MULTIPLY    = re.compile(r"\d\s*[×÷·⋅]\s*\d|[a-zA-Z]\s*[×·]\s*[a-zA-Z\d]")
_PAT_SCIENTIFIC  = re.compile(
    r"\d+\.\d+\s*[eE][+\-]?\d+"
    r"|\d+\s*[×x]\s*10\s*[\^⁻⁺\-\d]"
    r"|\d+\.\d{2,}\s*[×x]"
)
_PAT_UNITS = re.compile(
    r"\b(m[dD]|milli[dD]arcy|darcy|psi|kPa|MPa|GPa|Pa|bar|atm"
    r"|bbl|stb|scf|Mcf|MMscf|Mscf|rbbl"
    r"|ft|in|cm|mm|km|m|acre|ha"
    r"|kg|g|mg|lb|ton|tonne"
    r"|cp|cP|mPa\.s|Pa\.s"
    r"|bbl\/d|bbl\/day|scf\/d|scf\/day|m3\/d|STB\/d"
    r"|kJ|MJ|GJ|kcal|Btu|cal|J"
    r"|kW|MW|GW|hp|W"
    r"|°C|°F|°R|K"
    r"|mol|mmol|kmol|ppm|ppb|wt%|vol%"
    r"|Hz|kHz|MHz|rpm"
    r"|API|SG|sg)\b"
)
_PAT_CHEM      = re.compile(r"\b[A-Z][a-z]?\d*([A-Z][a-z]?\d*){1,6}\b")
_PAT_TABLE_ROW = re.compile(r"^[\d\s.,\-\+eE×/°%()\[\]]+$")
_OPERATOR_SET  = set("+-*/=^_|\\&<>~")


def _operator_ratio(text: str) -> float:
    return sum(1 for c in text if c in _OPERATOR_SET) / max(len(text), 1)


def _digit_ratio(text: str) -> float:
    return sum(1 for c in text if c.isdigit()) / max(len(text), 1)


def _alpha_ratio(text: str) -> float:
    return sum(1 for c in text if c.isalpha() and ord(c) < 0x370) / max(len(text), 1)


def is_math_paragraph(text: str) -> bool:
    text = text.strip()
    if not text or len(text) < 2:
        return False
    if any(c in _MATH_UNICODE for c in text):
        return True
    if _PAT_LATEX.search(text) or _PAT_DOLLAR.search(text) or _PAT_BRACKET_EQ.search(text):
        return True
    wc = len(text.split())

    # 3. أسس وتحتيات — موثوقة بأي طول
    if _PAT_SUPERSCRIPT.search(text) or _PAT_SUBSCRIPT.search(text):
        return True

    # 4. معادلة إسناد: "x = 2.5" — لكن ليس "Results show that k = 50 mD in the upper zone"
    if _PAT_EQ_ASSIGN.search(text) and wc <= 10:
        return True

    # 5. كسر رمزي: "k/μ", "dP/dx", "dp/dL"
    #    wc ≤ 6  → كسر مباشر بدون شرط كثافة (قصير جداً = رياضي)
    #    wc ≤ 10 → نقبله لو فيه كثافة مشغّلات كافية
    if _PAT_FRACTION.search(text):
        if wc <= 6:
            return True
        if wc <= 10 and _operator_ratio(text) > 0.08:
            return True

    # 6. رقم علمي
    if _PAT_SCIENTIFIC.search(text):
        return True

    # 7. وحدات هندسية — فقط في نصوص قصيرة (قياس/تعريف لا جملة كاملة)
    #    "k = 50 mD"  (4 كلمات) → رياضي ✓
    #    "Pressure was maintained at 3500 psi during the experiment" (9 كلمات) → جملة تُترجم ✗
    if _PAT_UNITS.search(text) and re.search(r"\d", text) and wc <= 8:
        return True

    # 8. ضرب رمزي
    if _PAT_MULTIPLY.search(text):
        return True

    # 9. صيغة كيميائية (CO2, CH4, H2O) — تحتاج رقماً لتمييزها عن اختصارات (MRI, API)
    if _PAT_CHEM.findall(text) and wc <= 8 and re.search(r"\d", text):
        return True

    # 10. صف جدول: أرقام وفواصل فقط
    if _PAT_TABLE_ROW.match(text) and re.search(r"\d", text):
        return True

    # 11. نص قصير بكثافة عالية من المشغّلات أو الأرقام
    if wc <= 12:
        if _operator_ratio(text) >= 0.15 or _digit_ratio(text) >= 0.40:
            return True

    # 12. نص متوسط أكثر من 65% منه رموز وأرقام (ليس نثراً)
    if len(text) <= 200:
        if (1.0 - _alpha_ratio(text)) >= 0.65 and re.search(r"\d", text):
            return True

    return False


# ─── فحص جودة الترجمة ────────────────────────────────────────────────────────

def _arabic_char_ratio(text: str) -> float:
    """نسبة الحروف العربية من مجموع الحروف (بدون مسافات وأرقام)."""
    chars = [c for c in text if c.isalpha()]
    if not chars:
        return 0.0
    arabic = sum(1 for c in chars if "\u0600" <= c <= "\u06FF")
    return arabic / len(chars)


def _is_valid_translation(original: str, result: str) -> bool:
    """
    يتحقق إذا كانت الترجمة مقبولة:
    - مو فارغة
    - فيها حروف عربية
    - نسبة العربي ≥ 40% من الحروف الكلية
    - مو نفس الأصل بالضبط (ما ترجم)
    - مو مقطوعة (على الأقل 20% من عدد كلمات الأصل)
    """
    if not result or not result.strip():
        return False
    # لازم يكون فيها عربي
    if not any("\u0600" <= c <= "\u06FF" for c in result):
        return False
    # نسبة العربي لازم تكون كافية — ما تطلع بالإنجليزي
    ar_ratio = _arabic_char_ratio(result)
    if ar_ratio < 0.60:
        logger.warning(f"نسبة عربي منخفضة ({ar_ratio:.0%}): {result[:50]!r}")
        return False
    # ما ترجم (نفس الإنجليزي)
    if result.strip().lower() == original.strip().lower():
        return False
    # فحص الاكتمال — ما يكون مقطوع
    orig_words = len(original.split())
    res_words  = len(result.split())
    if orig_words > 8 and res_words < orig_words * 0.20:
        logger.warning(f"ترجمة مقطوعة: {res_words}/{orig_words} كلمة — {original[:40]}")
        return False
    return True


# ─── محركات الترجمة ──────────────────────────────────────────────────────────

def _split_text(text: str, limit: int = _CHUNK_LIMIT) -> List[str]:
    """يقسّم النص إلى chunks لا تتجاوز الحد المسموح."""
    if len(text) <= limit:
        return [text]
    lines, chunks, current = text.splitlines(), [], ""
    for line in lines:
        if len(current) + len(line) + 1 > limit:
            if current:
                chunks.append(current.strip())
            # لو السطر وحده أطول من الحد، اقطعه على مسافة
            if len(line) > limit:
                for start in range(0, len(line), limit):
                    chunks.append(line[start:start + limit])
                current = ""
            else:
                current = line
        else:
            current += ("\n" if current else "") + line
    if current:
        chunks.append(current.strip())
    return [c for c in chunks if c]


def _bing_translate(text: str) -> str:
    import translators as ts
    result = ts.translate_text(
        text, translator="bing", from_language="en", to_language="ar",
    )
    return _normalize_translate_result(result)


def _google_translate(text: str) -> str:
    from deep_translator import GoogleTranslator
    result = GoogleTranslator(source="en", target="ar").translate(text)
    return _normalize_translate_result(result)


def _normalize_translate_result(result) -> str:
    if isinstance(result, str):
        return result.strip()
    if isinstance(result, dict):
        for key in ("text", "result", "translation", "translatedText"):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""
    if result is None:
        return ""
    return str(result).strip()


def _microsoft_translate(text: str) -> str:
    import translators as ts
    result = ts.translate_text(
        text, translator="microsoft", from_language="en", to_language="ar",
    )
    return _normalize_translate_result(result)


def _yandex_translate(text: str) -> str:
    import translators as ts
    result = ts.translate_text(
        text, translator="yandex", from_language="en", to_language="ar",
    )
    return _normalize_translate_result(result)


def _translate_sync(text: str) -> str:
    """
    يترجم النص مع تقسيم تلقائي وتحقق من الجودة.
    يُرجع الإنجليزي الأصلي لو فشل كل شيء.
    """
    text = text.strip()
    if not text:
        return text

    chunks = _split_text(text)

    translated_chunks: List[str] = []
    for chunk in chunks:
        result = _translate_chunk(chunk)
        translated_chunks.append(result)

    return "\n".join(translated_chunks)


def _translate_chunk(text: str) -> str:
    """
    يترجم chunk واحد بنظام متعدد المحاولات:
      Bing → Microsoft → Google → Yandex
    بعد كل فشل يتحقق من نسبة العربي (≥ 40%) قبل القبول.
    """
    import time

    providers = [
        ("microsoft", _microsoft_translate),
        ("google", _google_translate),
        ("bing", _bing_translate),
    ]

    for name, fn in providers:
        for attempt in range(1, 4):
            try:
                result = fn(text)
                if name == "bing" and "JavaScript runtime" in result:
                    raise RuntimeError(result)
                if _is_valid_translation(text, result):
                    return result
                logger.warning(
                    f"{name} محاولة {attempt}/3 — نتيجة غير مقبولة: {result[:50]!r}"
                )
            except Exception as e:
                logger.warning(f"{name} خطأ (محاولة {attempt}/3): {e}")
            if attempt < 3:
                time.sleep(0.5)

    # ── آخر ملاذ: أبقِ الإنجليزي ─────────────────────────────────────────────
    logger.error(f"فشل الترجمة كلياً بعد 9 محاولات — يُبقى الأصل: {text[:60]}")
    return text


async def _translate_one(text: str) -> str:
    """ترجمة فقرة واحدة async."""
    text = text.strip()
    if not text:
        return text
    async with _get_semaphore():
        try:
            return await asyncio.to_thread(_translate_sync, text)
        except Exception as e:
            logger.error(f"_translate_one استثناء: {e}")
            return text  # fallback: الأصل


# ─── الدالة الرئيسية ──────────────────────────────────────────────────────────

async def translate_paragraphs_async(
    paragraphs: List[str],
    on_progress: Optional[Callable[[int, int], Awaitable[None]]] = None,
) -> List[str]:
    """
    يترجم قائمة فقرات.
    - المحتوى الرياضي يُبقى كما هو.
    - لو فشلت الترجمة يُعاد الإنجليزي الأصلي (ما يُترك فراغ).
    """
    total   = len(paragraphs)
    results: List[str] = [""] * total
    logger.info(f"بدء الترجمة: {total} فقرة")

    to_translate: List[Tuple[int, str]] = []
    for i, para in enumerate(paragraphs):
        p = para.strip()
        if is_math_paragraph(p):
            logger.info(f"📐 رياضيات §{i+1} (محفوظة): {p[:60]}")
            results[i] = p
        else:
            to_translate.append((i, p))

    skipped = total - len(to_translate)
    logger.info(f"للترجمة: {len(to_translate)} | محفوظة: {skipped}")

    if not to_translate:
        if on_progress:
            await on_progress(total, total)
        return results

    done_count = 0

    async def _do(idx: int, text: str) -> None:
        nonlocal done_count
        translated = await _translate_one(text)
        # فحص أخير — لو ما اكتمل يُرجع الأصل
        if not _is_valid_translation(text, translated):
            logger.warning(f"§{idx+1} فشل فحص الجودة النهائي — يُبقى الأصل")
            results[idx] = text
        else:
            results[idx] = translated
        done_count += 1
        logger.info(f"الترجمة: {done_count}/{len(to_translate)}")
        if on_progress:
            try:
                await on_progress(done_count, len(to_translate))
            except Exception:
                pass

    await asyncio.gather(*[_do(i, t) for i, t in to_translate])

    # ضمان أخير: أي فقرة فارغة تأخذ نصها الأصلي
    for i, r in enumerate(results):
        if not r or not r.strip():
            logger.warning(f"§{i+1} فارغة — يُبقى الأصل")
            results[i] = paragraphs[i]

    return results


# ─── مرحلة التحقق وإعادة الترجمة ─────────────────────────────────────────────

async def validate_and_retry_async(
    paragraphs: List[str],
    translated: List[str],
    on_progress: Optional[Callable[[int, int], Awaitable[None]]] = None,
) -> List[str]:
    """
    يمر على كل فقرة ويتأكد إنها انترجمت للعربي.
    أي فقرة فاشلة (عربي ناقص أو رجعت إنجليزي) يعيد ترجمتها مرة ثانية.
    الرياضيات/passthrough تتجاهل تلقائياً.
    يُرجع قائمة محدّثة.
    """
    result = list(translated)   # نسخة قابلة للتعديل
    failed_indices: List[int] = []

    for i, (eng, arb) in enumerate(zip(paragraphs, translated)):
        eng = (eng or "").strip()
        arb = (arb or "").strip()

        # الرياضيات / passthrough — ما تُعاد
        if is_math_paragraph(eng):
            continue

        # فحص صحة الترجمة
        if not _is_valid_translation(eng, arb):
            failed_indices.append(i)

    total_failed = len(failed_indices)
    if total_failed == 0:
        logger.info("✅ مرحلة التحقق: كل الفقرات مترجمة، ما يحتاج إعادة")
        if on_progress:
            await on_progress(0, 0)
        return result

    logger.info(f"⚠️ مرحلة التحقق: {total_failed} فقرة تحتاج إعادة ترجمة")
    fixed = 0

    for pos, i in enumerate(failed_indices):
        eng = paragraphs[i].strip()
        logger.info(f"🔄 إعادة ترجمة §{i+1}: {eng[:60]}")

        # محاولة إعادة الترجمة مرتين
        retry_result = ""
        for attempt in range(2):
            candidate = await _translate_one(eng)
            if _is_valid_translation(eng, candidate):
                retry_result = candidate
                break
            logger.warning(f"محاولة {attempt+1}/2 فشلت لـ §{i+1}")

        if retry_result:
            result[i] = retry_result
            fixed += 1
            logger.info(f"✅ §{i+1} أُصلحت: {retry_result[:60]}")
        else:
            logger.error(f"❌ §{i+1} فشلت بعد إعادة المحاولة — تبقى الأصل")

        if on_progress:
            try:
                await on_progress(pos + 1, total_failed)
            except Exception:
                pass

    logger.info(f"مرحلة التحقق انتهت: أُصلح {fixed} من {total_failed}")
    return result


# ─── نسخة sync للتوافق ────────────────────────────────────────────────────────

def translate_paragraphs(paragraphs: List[str], on_progress=None) -> List[str]:
    return asyncio.run(translate_paragraphs_async(paragraphs))


def translate_lines(lines: List[str]) -> List[str]:
    return asyncio.run(translate_paragraphs_async(lines))
