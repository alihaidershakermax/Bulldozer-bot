"""
معالج ملفات PDF
- كل العمليات الثقيلة في threads منفصلة (asyncio.to_thread)
- تحديثات تقدم حية أثناء الترجمة (كل 5 ثوانٍ)
- اسم ملف الإخراج = اسم الملف الأصلي
"""
import asyncio
import os
import logging
from telegram import Update
from telegram.constants import ParseMode

from processors.pdf_to_images import pdf_to_images
from processors.ocr import extract_text_from_image, clean_text, split_into_paragraphs
from processors.translator import translate_paragraphs_async, validate_and_retry_async
from processors.pdf_builder import build_translation_pdf
from utils.temp_manager import create_temp_dir, cleanup_temp_dir
from utils.logger_channel import log_success
from utils.progress import ProgressMessage
from utils.background import fire
from utils.translation_checker import build_report
from db.convex_client import log_request, get_daily_count, get_setting, is_user_banned
from keyboards import USER_KEYBOARD, ADMIN_KEYBOARD
from handlers.admin_handler import is_admin
from config import MAX_FILE_SIZE_MB

logger = logging.getLogger(__name__)
MAX_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
_FILE_QUEUE = asyncio.Semaphore(int(os.getenv("PDF_CONCURRENCY", "1")))
_QUEUE_WAITING = 0


def _user(update: Update):
    msg = update.message
    if not msg or not msg.from_user:
        return 0, ""
    u = msg.from_user
    return u.id, u.username or ""


async def _daily_limit_text(user_id: int) -> str:
    daily_limit = int(await get_setting("daily_limit", "5"))
    if daily_limit <= 0:
        return "∞"
    count = await get_daily_count(user_id)
    remaining = max(daily_limit - count, 0)
    return f"{count}/{daily_limit} — المتبقي: {remaining}"


async def handle_pdf(update: Update, context) -> None:
    global _QUEUE_WAITING
    user_id, _ = _user(update)
    admin = is_admin(update)
    queue_position = 0
    queue_message = None

    if _FILE_QUEUE.locked():
        _QUEUE_WAITING += 1
        queue_position = _QUEUE_WAITING
        if update.message:
            queue_message = await update.message.reply_text(
                f"⏳ ملفك داخل الطابور الآن\n"
                f"📌 ترتيبك: {queue_position}\n"
                f"👤 الأدمن/الطوارئ تتجاوز الطابور: {'نعم' if admin else 'لا'}",
                parse_mode=ParseMode.HTML,
            )

    async with _FILE_QUEUE:
        if queue_message:
            try:
                await queue_message.edit_text(
                    f"⏳ نبدت المعالجة\n"
                    f"📌 ترتيبك السابق: {queue_position}",
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass
        try:
            await _handle_pdf_locked(update, context)
        finally:
            if queue_position:
                _QUEUE_WAITING = max(_QUEUE_WAITING - 1, 0)


async def _handle_pdf_locked(update: Update, context) -> None:
    logger.info("📄 استقبال ملف PDF")
    if not update.message or not update.message.document:
        return
    doc = update.message.document
    user_id, username = _user(update)
    admin = is_admin(update)
    markup = ADMIN_KEYBOARD if admin else USER_KEYBOARD

    if not admin and user_id:
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

    original_filename = doc.file_name or "document.pdf"
    if not original_filename.lower().endswith(".pdf"):
        original_filename = os.path.splitext(original_filename)[0] + ".pdf"

    temp_dir = create_temp_dir()
    pm = None
    total_pages = 0
    all_paragraphs: list = []

    try:
        pm = await ProgressMessage.create(update.message, "معالجة PDF")
        daily_info = await _daily_limit_text(user_id) if user_id else "∞"
        await pm.update(3, f"حدّك اليومي: {daily_info}", "التحقق")

        await pm.update(5, "گاعد يحمّل الملف…", "تحميل PDF")
        tg_file = await doc.get_file()
        pdf_path = os.path.join(temp_dir, "input.pdf")
        await tg_file.download_to_drive(pdf_path)

        await pm.update(12, "گاعد يجهّز الصفحات…", "تجهيز الصفحات")
        try:
            image_paths = await asyncio.to_thread(pdf_to_images, pdf_path, temp_dir)
        except RuntimeError as e:
            await pm.error(f"ما قدر يفتح الملف: {e}")
            return

        total_pages = len(image_paths)
        raw_texts: list[str] = []
        base, ocr_range = 15, 45
        for i, img_path in enumerate(image_paths):
            pct = base + (i / total_pages) * ocr_range if total_pages else base
            await pm.update(pct, f"گاعد يقرأ الصفحة {i+1} من {total_pages}…", "قراءة النص")
            try:
                raw = await asyncio.to_thread(extract_text_from_image, img_path, True)
                raw_texts.append(raw)
            except RuntimeError as e:
                logger.warning(f"OCR فشل للصفحة {i+1}: {e}")

        if not raw_texts:
            await pm.error("ماكو نص اكو بالملف، تأكد الملف واضح.")
            return

        await pm.update(62, "گاعد يرتّب الفقرات…", "ترتيب النص")
        full_text = "\n\n".join(raw_texts)
        cleaned = clean_text(full_text)
        all_paragraphs = split_into_paragraphs(cleaned)

        if not all_paragraphs:
            await pm.error("ماكو نص واضح بالملف، جرّب ملف ثاني.")
            return

        logger.info(f"PDF: {total_pages} صفحة → {len(all_paragraphs)} فقرة")
        await pm.update(67, f"گاعد يترجم {len(all_paragraphs)} فقرة…", "الترجمة")

        async def _on_progress(done: int, total: int) -> None:
            pct = 67 + int(done / total * 20) if total else 67
            try:
                await pm.update(pct, f"ترجم {done} من {total} فقرة…", "الترجمة")
            except Exception:
                pass

        try:
            arabic_paragraphs = await translate_paragraphs_async(all_paragraphs, _on_progress)
        except Exception as e:
            await pm.error(f"خطأ في الترجمة: {e}")
            return

        await pm.update(88, "گاعد يتحقق من الترجمة…", "التحقق")

        async def _on_validate(done: int, total: int) -> None:
            if total == 0:
                return
            pct = 88 + int(done / total * 2) if total else 88
            try:
                await pm.update(pct, f"يعيد ترجمة {done} من {total} فقرة ما انترجمت…", "التحقق")
            except Exception:
                pass

        try:
            arabic_paragraphs = await validate_and_retry_async(all_paragraphs, arabic_paragraphs, _on_validate)
        except Exception as e:
            logger.warning(f"مرحلة التحقق فشلت (تكملة بدونها): {e}")

        await pm.update(90, "گاعد يسوّي ملف PDF…", "توليد الملف")
        output_pdf = os.path.join(temp_dir, original_filename)
        doc_title = os.path.splitext(original_filename)[0]
        try:
            await asyncio.to_thread(
                build_translation_pdf,
                list(zip(all_paragraphs, arabic_paragraphs)),
                output_pdf,
                doc_title,
            )
        except Exception as e:
            await pm.error(f"فشل إنشاء PDF: {e}")
            return

        await pm.update(97, "جارٍ إرسال الملف…", "الإرسال")
        try:
            with open(output_pdf, "rb") as f:
                await update.message.reply_document(
                    document=f,
                    filename=original_filename,
                    caption=(
                        f"📄 <b>{_esc_html(doc_title)}</b>\n"
                        f"📄 {total_pages} صفحة  |  📝 {len(all_paragraphs)} فقرة\n"
                        f"📊 حدّك اليومي: <b>{daily_info}</b>\n"
                        "<i>النص الأصلي مع ترجمته لكل فقرة</i>"
                    ),
                    parse_mode=ParseMode.HTML,
                    reply_markup=markup,
                )
        except Exception as e:
            logger.exception(f"فشل إرسال الملف: {e}")
            await update.message.reply_text("❌ فشل إرسال الملف. حاول مرة أخرى.", reply_markup=markup)
            return

        await pm.done(
            f"✅ <b>اكتملت المعالجة!</b>\n"
            f"📄 {total_pages} صفحة  |  📝 {len(all_paragraphs)} فقرة"
        )

        fire(log_success(user_id, username, "PDF", total_pages, len(all_paragraphs)))
        fire(log_request(user_id, username, "PDF", total_pages, len(all_paragraphs), "success"))

    except Exception as e:
        logger.exception(f"خطأ في handle_pdf: {e}")
        try:
            if pm:
                await pm.error("حدث خطأ غير متوقع أثناء المعالجة.")
        except Exception:
            pass
        fire(log_request(user_id, username, "PDF", total_pages, len(all_paragraphs), "error", str(e)))
    finally:
        cleanup_temp_dir(temp_dir)


def _esc_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")