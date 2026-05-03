"""
معالج الصور (JPG / PNG / TIFF / WEBP / ...)
- كل العمليات الثقيلة تعمل في threads منفصلة (asyncio.to_thread)
  لمنع تجميد حلقة الأحداث وإيقاف البوت
"""
import asyncio
import os
import logging
from telegram import Update, PhotoSize
from telegram.constants import ParseMode

from processors.ocr import extract_text_from_image, clean_text, split_into_paragraphs
from processors.translator import translate_paragraphs_async, validate_and_retry_async
from processors.pdf_builder import build_translation_pdf
from utils.temp_manager import create_temp_dir, cleanup_temp_dir
from utils.logger_channel import log_success
from utils.progress import ProgressMessage
from utils.background import fire
from utils.translation_checker import build_report
from db.convex_client import log_request
from keyboards import USER_KEYBOARD, ADMIN_KEYBOARD
from handlers.admin_handler import is_admin
from config import MAX_FILE_SIZE_MB

logger = logging.getLogger(__name__)
MAX_BYTES     = MAX_FILE_SIZE_MB * 1024 * 1024
SUPPORTED_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp", ".gif"}


def _user(update: Update):
    msg = update.message
    if not msg or not msg.from_user:
        return 0, ""
    u = msg.from_user
    return u.id, u.username or ""


# ─── صورة كمستند ─────────────────────────────────────────────────────────────

async def handle_image_document(update: Update, context) -> None:
    logger.info("📎 استقبال صورة كمستند")
    if not update.message or not update.message.document:
        return
    doc  = update.message.document
    ext  = os.path.splitext(doc.file_name or "")[1].lower()
    user_id, username = _user(update)
    admin  = is_admin(update)
    markup = ADMIN_KEYBOARD if admin else USER_KEYBOARD

    if ext not in SUPPORTED_EXT:
        await update.message.reply_text(
            "⚠️ صيغة غير مدعومة.\nالصيغ المقبولة: JPG PNG BMP TIFF WEBP أو PDF.",
            reply_markup=markup,
        )
        return

    # ── تحقق من الحظر والحد اليومي (الأدمن معفى) ────────────────────────
    if not admin and user_id:
        from db.convex_client import is_user_banned, get_daily_count, get_setting
        banned, reason = await is_user_banned(user_id)
        if banned:
            await update.message.reply_text(
                "⛔ <b>أنت محظور من استخدام البوت.</b>"
                + (f"\nالسبب: {reason}" if reason else ""),
                parse_mode=ParseMode.HTML,
            )
            return
        daily_limit = int(await get_setting("daily_limit", "5"))
        if daily_limit > 0:
            count = await get_daily_count(user_id)
            if count >= daily_limit:
                await update.message.reply_text(
                    f"⚠️ <b>وصلت الحد اليومي ({daily_limit} طلبات).</b>\n"
                    "يُعاد ضبط العداد كل يوم — جرّب غداً! 🌙",
                    parse_mode=ParseMode.HTML,
                )
                return

    if doc.file_size and doc.file_size > MAX_BYTES:
        await update.message.reply_text(
            f"⚠️ الملف كبير جداً. الحد الأقصى <b>{MAX_FILE_SIZE_MB} MB</b>.",
            parse_mode=ParseMode.HTML,
        )
        return

    temp_dir = create_temp_dir()
    pm = None
    try:
        pm = await ProgressMessage.create(update.message, "گاعد يشتغل على الصورة")
        await pm.update(10, "گاعد يحمّل الصورة…", "تحميل")
        tg_file    = await doc.get_file()
        image_path = os.path.join(temp_dir, f"input{ext}")
        await tg_file.download_to_drive(image_path)
        await _process(update, pm, image_path, temp_dir, "صورة", user_id, username, markup)
    except Exception as e:
        logger.exception(f"خطأ في handle_image_document: {e}")
        try:
            if pm:
                await pm.error("حدث خطأ أثناء معالجة الصورة.")
            else:
                await update.message.reply_text("❌ حدث خطأ أثناء معالجة الصورة.")
        except Exception:
            pass
    finally:
        cleanup_temp_dir(temp_dir)


# ─── صورة مضغوطة (photo) ─────────────────────────────────────────────────────

async def handle_photo(update: Update, context) -> None:
    logger.info("📸 استقبال صورة مضغوطة")
    if not update.message or not update.message.photo:
        return
    photos: list[PhotoSize] = list(update.message.photo)
    if not photos:
        return
    best   = max(photos, key=lambda p: p.file_size or 0)
    user_id, username = _user(update)
    admin  = is_admin(update)
    markup = ADMIN_KEYBOARD if admin else USER_KEYBOARD

    temp_dir = create_temp_dir()
    pm = None
    try:
        pm = await ProgressMessage.create(update.message, "گاعد يشتغل على الصورة")
        await pm.update(
            10,
            "گاعد يحمّل الصورة…\n<i>تلميح: ارسلها كـ«ملف» للحصول على جودة أحسن</i>",
            "تحميل",
        )
        tg_file    = await best.get_file()
        image_path = os.path.join(temp_dir, "input.jpg")
        await tg_file.download_to_drive(image_path)
        await _process(update, pm, image_path, temp_dir, "صورة", user_id, username, markup)
    except Exception as e:
        logger.exception(f"خطأ في handle_photo: {e}")
        try:
            if pm:
                await pm.error("حدث خطأ أثناء معالجة الصورة.")
            else:
                await update.message.reply_text("❌ حدث خطأ أثناء معالجة الصورة.")
        except Exception:
            pass
    finally:
        cleanup_temp_dir(temp_dir)


# ─── معالجة مشتركة ───────────────────────────────────────────────────────────

async def _process(
    update, pm: ProgressMessage,
    image_path: str, temp_dir: str,
    file_type: str, user_id: int, username: str,
    markup=None,
) -> None:
    if markup is None:
        markup = USER_KEYBOARD

    # ① OCR
    await pm.update(28, "گاعد يقرأ النص من الصورة…", "قراءة النص")
    try:
        raw = await asyncio.to_thread(extract_text_from_image, image_path, True)
    except RuntimeError as e:
        await pm.error(f"ما قدر يقرأ الصورة: {e}")
        return

    if not raw or not raw.strip():
        await pm.error("ماكو نص بالصورة، تأكد الصورة واضحة ومو مايلة.")
        return

    # ② تنظيف وتقسيم
    await pm.update(45, "گاعد يرتّب الفقرات…", "ترتيب النص")
    cleaned    = clean_text(raw)
    paragraphs = split_into_paragraphs(cleaned)

    if not paragraphs:
        await pm.error("النص مو واضح، جرّب صورة بجودة أحسن.")
        return

    logger.info(f"صورة: {len(paragraphs)} فقرة")

    # ③ ترجمة
    await pm.update(55, f"گاعد يترجم {len(paragraphs)} فقرة…", "الترجمة")

    async def _on_progress(done: int, total: int) -> None:
        pct = 55 + int(done / total * 25) if total else 55
        try:
            await pm.update(pct, f"ترجم {done} من {total} فقرة…", "الترجمة")
        except Exception:
            pass

    try:
        arabic_paragraphs = await translate_paragraphs_async(paragraphs, _on_progress)
    except Exception as e:
        await pm.error(f"صار خطأ بالترجمة: {e}")
        return

    if not arabic_paragraphs or len(arabic_paragraphs) != len(paragraphs):
        await pm.error("فشل توليد الترجمة بشكل صحيح.")
        return

    # ③.5 تحقق وإعادة ترجمة الفقرات الفاشلة
    await pm.update(82, "گاعد يتحقق من الترجمة…", "التحقق")

    async def _on_validate(done: int, total: int) -> None:
        if total == 0:
            return
        pct = 82 + int(done / total * 2) if total else 82
        try:
            await pm.update(
                pct,
                f"يعيد ترجمة {done} من {total} فقرة ما انترجمت…",
                "التحقق",
            )
        except Exception:
            pass

    try:
        arabic_paragraphs = await validate_and_retry_async(
            paragraphs, arabic_paragraphs, _on_validate
        )
    except Exception as e:
        logger.warning(f"مرحلة التحقق فشلت (تكملة بدونها): {e}")

    # ④ إنشاء PDF
    await pm.update(85, "گاعد يسوّي ملف PDF…", "توليد الملف")
    output_pdf = os.path.join(temp_dir, "ترجمة.pdf")
    try:
        await asyncio.to_thread(
            build_translation_pdf,
            list(zip(paragraphs, arabic_paragraphs)),
            output_pdf,
            "ترجمة",
        )
    except Exception as e:
        await pm.error(f"ما قدر يسوّي PDF: {e}")
        return

    # ⑤ إرسال الملف
    await pm.update(97, "گاعد يرسل الملف…", "الإرسال")
    try:
        with open(output_pdf, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename="ترجمة.pdf",
                caption=(
                    f"📄 <b>ترجمتك جاهزة يبه!</b>  |  📝 {len(paragraphs)} فقرة\n"
                    "<i>النص الأصلي وترجمته جنب بعض</i>"
                ),
                parse_mode=ParseMode.HTML,
                reply_markup=markup,
            )
    except Exception as e:
        logger.exception(f"فشل إرسال الملف: {e}")
        await update.message.reply_text(
            "❌ ما قدر يرسل الملف، جرّب مرة ثانية.", reply_markup=markup
        )
        return

    # ⑥ تحديث شريط التقدم
    await pm.done(
        f"✅ <b>خوش، ابشر! الترجمة جاهزة</b>\n"
        f"📝 {len(paragraphs)} فقرة"
    )

    # ⑧ تسجيل في الخلفية
    fire(log_success(user_id, username, file_type, 1, len(paragraphs)))
    fire(log_request(user_id, username, file_type, 1, len(paragraphs), "success"))
