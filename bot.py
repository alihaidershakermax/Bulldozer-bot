"""
بوت ترجمة المستندات والصور
============================
يدعم: PDF، صور، سكانر
لوحة أدمن كاملة على Telegram فقط (بدون ويب)
الكيبورد المتقدم للأدمن فقط — مخفي عن المستخدمين العاديين
تسجيل كل المستخدمين في Convex + إشعار القناة للجدد فقط
ترجمة متوازية مع تجاوز المعادلات الرياضية
حذف تلقائي للملفات المؤقتة بعد 30 دقيقة
"""
import asyncio
import logging
import os
import shutil
import sys
import threading
import time as _time
from aiohttp import web

from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ParseMode

from config import (
    TELEGRAM_BOT_TOKEN, TEMP_DIR,
    BOT_NAME, WELCOME_PHOTO,
    DEVELOPER_NAME, DEVELOPER_BIO,
    DEVELOPER_USERNAME, DEVELOPER_INSTAGRAM,
    DEVELOPER_CONTACT, DEVELOPER_CHANNEL,
    DEVELOPER_PHOTO, DEVELOPER_WEBSITE,
)
from handlers.pdf_handler     import handle_pdf
from handlers.image_handler   import handle_image_document, handle_photo
from handlers.admin_handler   import (
    cmd_admin, cmd_stats, cmd_recent, cmd_broadcast,
    handle_admin_callback, handle_broadcast_text, is_admin,
    load_dynamic_admins,
)
from handlers.support_handler import (
    cmd_support, handle_support_message, handle_support_callback,
    handle_admin_reply_text,
)
from handlers.moderation_handler import (
    handle_moderation_callback, handle_moderation_text,
    show_banned_list, show_admins_list, show_settings, show_activity,
)
from keyboards import USER_KEYBOARD, ADMIN_KEYBOARD, user_stats_inline, user_register_inline
from utils.temp_manager import ensure_dirs
from utils.logger_channel import log_new_user
from db.convex_client import get_user_stats, register_user

logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


# ─── حذف الملفات المؤقتة القديمة (كل 10 دقائق) ──────────────────────────────

async def _cleanup_old_temp(context: ContextTypes.DEFAULT_TYPE) -> None:
    """يحذف أي مجلد مؤقت أقدم من 30 دقيقة."""
    if not os.path.exists(TEMP_DIR):
        return
    cutoff = _time.time() - 30 * 60
    deleted = 0
    try:
        for d in os.listdir(TEMP_DIR):
            path = os.path.join(TEMP_DIR, d)
            if os.path.isdir(path):
                try:
                    if os.path.getmtime(path) < cutoff:
                        shutil.rmtree(path)
                        deleted += 1
                except Exception:
                    pass
    except Exception as e:
        logger.warning(f"cleanup error: {e}")
    if deleted:
        logger.info(f"🗑 حُذف {deleted} مجلد مؤقت (أقدم من 30 دقيقة)")


# ─── /start ─────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user  = update.message.from_user
    name  = user.first_name or "صديقي"
    admin = is_admin(update)

    # تسجيل في DB في الخلفية — إشعار القناة للمستخدمين الجدد فقط
    async def _register():
        try:
            is_new = await register_user(
                user.id,
                user.username or "",
                user.full_name or name,
            )
            if is_new:
                await log_new_user(user.id, user.username or "", user.full_name or name)
        except Exception as e:
            logger.warning(f"register_user failed: {e}")

    asyncio.ensure_future(_register())

    caption = (
        f"👋 <b>هلا {name}! شلونك؟</b>\n\n"
        f"أنا <b>{BOT_NAME}</b> — أرسل ملفك أترجمه… وروّق، اشرب چايك ☕\n\n"
        "👨‍💻 <b>معرف المطور:</b> @dextermorgenk\n\n"
        "📎 <b>ابعث الملف أو الصورة وأنا أشتغل!</b>"
    )
    markup = ADMIN_KEYBOARD if admin else USER_KEYBOARD

    if WELCOME_PHOTO:
        try:
            await update.message.reply_photo(
                photo=WELCOME_PHOTO,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=markup,
            )
            return
        except Exception as e:
            logger.warning(f"فشل إرسال صورة الترحيب: {e}")

    await update.message.reply_text(caption, parse_mode=ParseMode.HTML, reply_markup=markup)


# ─── /help ──────────────────────────────────────────────────────────────────

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin = is_admin(update)
    extra = "\n\n⚙️ <b>للأدمن:</b> /admin لفتح لوحة التحكم." if admin else ""
    await update.message.reply_text(
        "المساعدة\n\n"
        "📎 <b>الاستخدام:</b>\n"
        "ارسل ملف أو صورة والبوت يشتغل تلقائي\n\n"
        "📂 <b>المدعوم:</b>\n"
        "PDF + صور (JPG / PNG / WEBP...)\n\n"
        "⌨️ <b>الأوامر:</b>\n"
        "/start — بدء\n"
        "/help — مساعدة\n"
        "/cancel — إلغاء"
        + extra,
        parse_mode=ParseMode.HTML,
        reply_markup=ADMIN_KEYBOARD if admin else USER_KEYBOARD,
    )


# ─── ردود الكيبورد النصية ────────────────────────────────────────────────────

_ADMIN_ONLY_TEXTS = {
    # ── إحصائيات ──
    "📊 إحصائيات",
    "📋 آخر الطلبات",
    "📈 النشاط",
    # ── إدارة مستخدمين ──
    "👥 المستخدمون",
    "🚫 المحظورون",
    "👮 الأدمنية",
    # ── أدوات ──
    "⚙️ الإعدادات",
    "📢 إذاعة",
    "☁️ Convex",
    # ── قديمة (للتوافق مع أي كاش) ──
    "📊 إحصائيات البوت",
    "📢 إذاعة للجميع",
    "⚙️ لوحة الأدمن",
}


async def handle_keyboard_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text  = (update.message.text or "").strip()
    admin = is_admin(update)
    # المستخدم العادي يرى USER_KEYBOARD فقط — لا يُعطى ADMIN_KEYBOARD أبداً
    markup = ADMIN_KEYBOARD if admin else USER_KEYBOARD

    # ── الأوامر المشتركة (متاحة للجميع) ─────────────────────────────────
    if text == "❓ مساعدة":
        await cmd_help(update, context)
        return

    if text == "📊 إحصائياتي":
        await update.message.reply_text(
            "📊 <b>إحصائياتك</b>\nاختر الفترة الزمنية:",
            parse_mode=ParseMode.HTML,
            reply_markup=user_stats_inline(),
        )
        return

    if text == "👨‍💻 المطور":
        await _show_developer_info(update, admin)
        return

    if text == "🛠 الدعم الفني":
        await cmd_support(update, context)
        return

    # ── أوامر الأدمن — محجوبة تماماً عن أي شخص آخر ────────────────────
    if text in _ADMIN_ONLY_TEXTS:
        if not admin:
            # لا تُظهر حتى رسالة خطأ توحي بوجود هذه الأزرار
            await update.message.reply_text(
                "📎 أرسل لي ملف PDF أو صورة لأبدأ الترجمة.",
                reply_markup=USER_KEYBOARD,
            )
            return
        # أدمن فقط
        if text in ("📊 إحصائيات", "📊 إحصائيات البوت"):
            await cmd_stats(update, context)
        elif text == "📋 آخر الطلبات":
            await cmd_recent(update, context)
        elif text == "📈 النشاط":
            await show_activity(update)
        elif text == "👥 المستخدمون":
            await _show_users_text(update)
        elif text == "🚫 المحظورون":
            await show_banned_list(update)
        elif text == "👮 الأدمنية":
            await show_admins_list(update)
        elif text == "⚙️ الإعدادات":
            await show_settings(update)
        elif text in ("📢 إذاعة", "📢 إذاعة للجميع"):
            await cmd_broadcast(update, context)
        elif text == "☁️ Convex":
            await _show_convex_info(update)
        elif text == "⚙️ لوحة الأدمن":
            await cmd_admin(update, context)
        return

    # ── انتظار رد الأدمن على مستخدم دعم فني ─────────────────────────────
    if admin and context.user_data.get("awaiting_reply_to"):
        handled = await handle_admin_reply_text(update, context)
        if handled:
            return

    # ── انتظار رسالة الدعم الفني ─────────────────────────────────────────
    if context.user_data.get("awaiting_support"):
        handled = await handle_support_message(update, context)
        if handled:
            return

    # ── انتظار أوامر الإشراف (أدمن فقط) ─────────────────────────────────
    if admin and any(context.user_data.get(k) for k in (
        "awaiting_ban", "awaiting_add_admin", "awaiting_set_limit"
    )):
        handled = await handle_moderation_text(update, context)
        if handled:
            return

    # ── انتظار نص الإذاعة (أدمن فقط) ────────────────────────────────────
    if context.user_data.get("awaiting_broadcast"):
        if admin:
            await handle_broadcast_text(update, context)
        return

    # ── نص غير معروف ─────────────────────────────────────────────────────
    await update.message.reply_text(
        "📎 أرسل لي ملف PDF أو صورة لأبدأ الترجمة.", reply_markup=markup
    )


async def _show_users_text(update: Update) -> None:
    from db.convex_client import get_all_users
    users = await get_all_users()
    lines = [f"👥 <b>المستخدمون المسجّلون ({len(users)})</b>\n"]
    for u in users[:25]:
        uname_str = f"@{u.get('username')}" if u.get("username") else "—"
        ban_tag   = " 🚫" if u.get("isBanned") else ""
        lines.append(
            f"• <code>{u.get('userId','?')}</code> {uname_str} — {u.get('fullName','')[:20]}{ban_tag}\n"
            f"  📅 {u.get('firstSeen','')[:10]}"
        )
    if len(users) > 25:
        lines.append(f"\n…و {len(users)-25} مستخدم آخر")
    await update.message.reply_text(
        "\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=ADMIN_KEYBOARD
    )


async def _show_convex_info(update: Update) -> None:
    """يعرض معلومات Convex DB مع رابط لوحة التحكم."""
    from db.convex_client import get_stats, get_user_count
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    try:
        stats = await get_stats()
        users = await get_user_count()
        total_req   = stats.get("totalRequests",  0)
        today_req   = stats.get("todayRequests",  0)
        convex_url  = os.getenv("CONVEX_URL", "").replace(".convex.cloud", ".convex.site")
        dashboard   = "https://dashboard.convex.dev"
        text = (
            "☁️ <b>Convex DB — معلومات قاعدة البيانات</b>\n\n"
            f"👥 إجمالي المستخدمين: <b>{users}</b>\n"
            f"📦 إجمالي الطلبات: <b>{total_req}</b>\n"
            f"📅 طلبات اليوم: <b>{today_req}</b>\n\n"
            "<i>استخدم الأزرار للوصول للوحة Convex.</i>"
        )
    except Exception as e:
        text = f"☁️ <b>Convex DB</b>\n\n⚠️ خطأ في الاتصال: {e}"
        dashboard = "https://dashboard.convex.dev"

    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 مزامنة البيانات", callback_data="adm:sync_convex")],
        [InlineKeyboardButton("🌐 لوحة Convex", url=dashboard)],
    ])
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)


# ─── Callback: إحصائيات المستخدم ─────────────────────────────────────────────

async def handle_user_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q    = update.callback_query
    await q.answer()
    data = q.data or ""
    user = q.from_user

    if data == "stats:close":
        await q.delete_message()
        return

    period_map = {
        "stats:today": ("اليوم",     "today"),
        "stats:month": ("هذا الشهر", "month"),
        "stats:year":  ("هذه السنة", "year"),
    }
    if data not in period_map:
        return

    label, key   = period_map[data]
    stats        = await get_user_stats(user.id)
    total        = stats.get("total",  0)
    period_count = stats.get(key,      0)

    await q.edit_message_text(
        f"📊 <b>إحصائياتك — {label}</b>\n\n"
        f"📁 ملفات {label}: <b>{period_count}</b>\n"
        f"📦 الإجمالي الكلي: <b>{total}</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=user_stats_inline(),
    )


# ─── معلومات المطور ──────────────────────────────────────────────────────────

async def _handle_register(update: Update, admin: bool) -> None:
    """يعرض معلومات التسجيل الحالية للمستخدم."""
    user   = update.message.from_user
    markup = ADMIN_KEYBOARD if admin else USER_KEYBOARD
    try:
        is_new = await register_user(
            user.id, user.username or "", user.full_name or ""
        )
        if is_new:
            await log_new_user(user.id, user.username or "", user.full_name or "")
        status = "✅ تم تسجيلك حديثاً" if is_new else "✔️ أنت مسجّل مسبقاً"
    except Exception:
        status = "⚠️ خطأ في التسجيل، حاول مجدداً."

    name   = user.full_name or user.first_name or "—"
    uname  = f"@{user.username}" if user.username else "—"
    await update.message.reply_text(
        f"📝 <b>معلومات التسجيل</b>\n\n"
        f"{status}\n\n"
        f"👤 <b>الاسم:</b> {name}\n"
        f"🔗 <b>المعرّف:</b> {uname}\n"
        f"🆔 <b>ID:</b> <code>{user.id}</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=markup,
    )


async def _show_developer_info(update: Update, admin: bool) -> None:
    from keyboards import developer_contact_inline
    kb = ADMIN_KEYBOARD if admin else USER_KEYBOARD

    caption = f"👨‍💻 <b>{DEVELOPER_NAME}</b>\n"
    if DEVELOPER_BIO:
        caption += f"<i>{DEVELOPER_BIO}</i>\n"
    caption += "\n━━━━━━━━━━━━━━━\n"
    caption += f"🤖 <b>مطوّر بوت:</b> {BOT_NAME}\n"
    if DEVELOPER_CONTACT:
        caption += f"📬 <b>تواصل:</b> {DEVELOPER_CONTACT}\n"
    if DEVELOPER_CHANNEL:
        caption += f"📢 <b>قناة:</b> {DEVELOPER_CHANNEL}\n"
    caption += "\n<i>اضغط أحد الأزرار أدناه للتواصل 👇</i>"

    inline = developer_contact_inline()   # دائماً غير None

    # ── أرسل الصورة مع الأزرار الـ inline ──────────────────────────
    sent = False
    if DEVELOPER_PHOTO:
        try:
            await update.message.reply_photo(
                photo=DEVELOPER_PHOTO,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=inline,
            )
            sent = True
        except Exception:
            pass

    if not sent:
        await update.message.reply_text(
            caption, parse_mode=ParseMode.HTML,
            reply_markup=inline,
        )

    # ── أعد تحديث الكيبورد السفلي دائماً ───────────────────────────
    await update.message.reply_text(
        "👆 اختر من الأزرار أعلاه للتواصل المباشر.",
        reply_markup=kb,
    )


# ─── توجيه المستندات ─────────────────────────────────────────────────────────

async def route_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    doc  = update.message.document
    if not doc:
        return
    mime = doc.mime_type or ""
    name = (doc.file_name or "").lower()

    if mime == "application/pdf" or name.endswith(".pdf"):
        await handle_pdf(update, context)
    elif mime.startswith("image/") or any(
        name.endswith(e)
        for e in (".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp", ".gif")
    ):
        await handle_image_document(update, context)
    else:
        await update.message.reply_text(
            "⚠️ <b>نوع الملف غير مدعوم.</b>\n"
            "أرسل <b>PDF</b> أو صورة (JPG، PNG، BMP، TIFF، WEBP).",
            parse_mode=ParseMode.HTML,
        )


# ─── /cancel ─────────────────────────────────────────────────────────────────

async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    for k in ("awaiting_broadcast", "broadcast_text", "awaiting_support",
              "awaiting_ban", "awaiting_add_admin", "awaiting_set_limit",
              "awaiting_reply_to"):
        context.user_data.pop(k, None)
    markup = ADMIN_KEYBOARD if is_admin(update) else USER_KEYBOARD
    await update.message.reply_text("✅ تم الإلغاء.", reply_markup=markup)


# ─── معالج الأخطاء العامة ────────────────────────────────────────────────────

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("خطأ غير متوقع:", exc_info=context.error)


# ─── تسجيل الأوامر ───────────────────────────────────────────────────────────

async def post_init(application: Application) -> None:
    await application.bot.set_my_commands([
        BotCommand("start",     "رسالة الترحيب"),
        BotCommand("help",      "المساعدة"),
        BotCommand("admin",     "لوحة تحكم الأدمن"),
        BotCommand("stats",     "إحصائيات البوت (أدمن)"),
        BotCommand("recent",    "آخر الطلبات (أدمن)"),
        BotCommand("broadcast", "إذاعة للجميع (أدمن)"),
        BotCommand("cancel",    "إلغاء العملية الحالية"),
    ])
    logger.info("تم تسجيل أوامر البوت.")
    logger.info("☁️ Convex قاعدة البيانات الأساسية — جاهز للاتصال")
    await load_dynamic_admins()


# ─── main ────────────────────────────────────────────────────────────────────

def main() -> None:
    ensure_dirs()
    logger.info("بدء تشغيل البوت…")

    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .concurrent_updates(True)   # ← معالجة متزامنة لكل المستخدمين
        .build()
    )

    # ── تنظيف الملفات المؤقتة كل 10 دقائق ──
    if app.job_queue:
        app.job_queue.run_repeating(_cleanup_old_temp, interval=600, first=60)
    else:
        logger.warning("job_queue غير متاح — التنظيف التلقائي معطّل")

    # ── أوامر ──
    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("help",      cmd_help))
    app.add_handler(CommandHandler("admin",     cmd_admin))
    app.add_handler(CommandHandler("stats",     cmd_stats))
    app.add_handler(CommandHandler("recent",    cmd_recent))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    app.add_handler(CommandHandler("cancel",    cmd_cancel))

    # ── Inline callbacks ──
    app.add_handler(CallbackQueryHandler(handle_admin_callback,       pattern=r"^adm:"))
    app.add_handler(CallbackQueryHandler(handle_moderation_callback,  pattern=r"^mod:"))
    app.add_handler(CallbackQueryHandler(handle_user_stats_callback,  pattern=r"^stats:"))
    app.add_handler(CallbackQueryHandler(handle_support_callback,     pattern=r"^support:"))

    # ── ملفات وصور ──
    app.add_handler(MessageHandler(filters.Document.ALL, route_document))
    app.add_handler(MessageHandler(filters.PHOTO,        handle_photo))

    # ── نص الكيبورد ──
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_keyboard_text))

    # ── معالج أخطاء عام ──
    app.add_error_handler(error_handler)

    logger.info("البوت يعمل ✅")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


def _start_health_server() -> None:
    port = int(os.getenv("PORT", "8000"))
    aio_app = web.Application()

    async def health(_: web.Request) -> web.Response:
        return web.Response(text="ok")

    aio_app.router.add_get("/", health)
    aio_app.router.add_get("/healthz", health)

    runner = web.AppRunner(aio_app)

    async def _run() -> None:
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(_run())
    loop.run_forever()


if __name__ == "__main__":
    threading.Thread(target=_start_health_server, daemon=True).start()
    main()
