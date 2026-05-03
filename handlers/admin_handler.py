"""
لوحة تحكم الأدمن الكاملة على Telegram
- /admin  — لوحة inline
- إذاعة للجميع (broadcast)
- إحصائيات + آخر الطلبات + قائمة المستخدمين
"""
import logging
import asyncio
from telegram import Update, Bot
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db.convex_client import (
    get_stats, get_recent_requests, get_all_users, get_user_count
)
from keyboards import (
    admin_home_inline, back_inline, requests_nav_inline,
    broadcast_confirm_inline, ADMIN_KEYBOARD,
)
from config import TELEGRAM_LOG_CHANNEL, TELEGRAM_BOT_TOKEN

logger = logging.getLogger(__name__)
PAGE_SIZE = 5


# ─── صلاحية الأدمن ──────────────────────────────────────────────────────────

# مجموعة ديناميكية تُحمَّل من Convex عند البدء وتُحدَّث عند الإضافة/الحذف
_extra_admin_ids: set[int] = set()


def _get_admin_ids() -> set:
    import os
    raw = os.getenv("ADMIN_IDS", "960173511")
    ids = set()
    for x in raw.split(","):
        x = x.strip()
        if x.isdigit():
            ids.add(int(x))
    ids |= _extra_admin_ids
    return ids


def is_admin(update: Update) -> bool:
    admin_ids = _get_admin_ids()
    uid = None
    if update.message and update.message.from_user:
        uid = update.message.from_user.id
    elif update.callback_query and update.callback_query.from_user:
        uid = update.callback_query.from_user.id
    if uid is None:
        return False
    return uid in admin_ids


async def load_dynamic_admins() -> None:
    """يُحمِّل الأدمنية الديناميكيين من Convex إلى الكاش المحلي."""
    global _extra_admin_ids
    try:
        from db.convex_client import get_admins
        admins = await get_admins()
        _extra_admin_ids = {int(a["userId"]) for a in admins if str(a.get("userId","")).isdigit()}
        logger.info(f"👮 أُحمِّل {len(_extra_admin_ids)} أدمن من Convex")
    except Exception as e:
        logger.warning(f"load_dynamic_admins: {e}")


def _uid(update: Update) -> tuple[int, str]:
    if update.callback_query and update.callback_query.from_user:
        u = update.callback_query.from_user
    elif update.message and update.message.from_user:
        u = update.message.from_user
    else:
        return 0, ""
    return u.id, u.username or ""


# ─── /admin ─────────────────────────────────────────────────────────────────

async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        await update.message.reply_text("⛔ ليس لديك صلاحية.")
        return
    await update.message.reply_text(
        "🛠 <b>لوحة تحكم الأدمن</b>\nاختر ما تريد:",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_home_inline(),
    )


# ─── /stats ─────────────────────────────────────────────────────────────────

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        await update.message.reply_text("⛔ ليس لديك صلاحية.")
        return
    stats = await get_stats()
    users_count = await get_user_count()
    await update.message.reply_text(
        _format_stats(stats, users_count),
        parse_mode=ParseMode.HTML,
        reply_markup=back_inline(),
    )


# ─── /recent ────────────────────────────────────────────────────────────────

async def cmd_recent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        await update.message.reply_text("⛔ ليس لديك صلاحية.")
        return
    reqs = await get_recent_requests(50)
    msg = _format_recent(reqs, 0)
    await update.message.reply_text(
        msg, parse_mode=ParseMode.HTML,
        reply_markup=requests_nav_inline(0, len(reqs) > PAGE_SIZE),
    )


# ─── /broadcast ─────────────────────────────────────────────────────────────

async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        await update.message.reply_text("⛔ ليس لديك صلاحية.")
        return
    context.user_data["awaiting_broadcast"] = True
    await update.message.reply_text(
        "📢 <b>إذاعة للجميع</b>\n\n"
        "أرسل النص الذي تريد إرساله لجميع المستخدمين.\n"
        "/cancel للإلغاء.",
        parse_mode=ParseMode.HTML,
        reply_markup=ADMIN_KEYBOARD,
    )


# ─── معالج نص الإذاعة ───────────────────────────────────────────────────────

async def handle_broadcast_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.user_data.pop("awaiting_broadcast", False):
        return
    if not is_admin(update):
        return

    text = update.message.text or ""
    if not text or text.startswith("/"):
        await update.message.reply_text("❌ لم يُرسَل أي نص.")
        return

    context.user_data["broadcast_text"] = text
    await update.message.reply_text(
        f"📢 <b>معاينة الإذاعة:</b>\n\n{text}\n\n"
        "هل تريد الإرسال للجميع؟",
        parse_mode=ParseMode.HTML,
        reply_markup=broadcast_confirm_inline(),
    )


# ─── تنفيذ الإذاعة ──────────────────────────────────────────────────────────

async def execute_broadcast(bot: Bot, text: str) -> tuple[int, int]:
    """يُرسل رسالة لكل المستخدمين المسجّلين. يُعيد (sent, failed)."""
    users = await get_all_users()
    sent = failed = 0
    for user in users:
        try:
            await bot.send_message(
                chat_id=int(user["userId"]),
                text=text,
                parse_mode=ParseMode.HTML,
            )
            sent += 1
        except Exception as e:
            logger.warning(f"فشل إرسال إذاعة لـ {user.get('userId')}: {e}")
            failed += 1
        await asyncio.sleep(0.05)  # تجنّب flood limit
    return sent, failed


# ─── Callback handler ───────────────────────────────────────────────────────

async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    data: str = q.data or ""
    uid, uname = _uid(update)

    # التحقق من صلاحية الأدمن
    if not is_admin(update):
        await q.answer("⛔ ليس لديك صلاحية.", show_alert=True)
        return

    if not data.startswith("adm:"):
        return

    part = data[4:]

    # ── الرئيسية ──
    if part in ("home", "refresh"):
        await q.edit_message_text(
            "🛠 <b>لوحة تحكم الأدمن</b>\nاختر ما تريد:",
            parse_mode=ParseMode.HTML,
            reply_markup=admin_home_inline(),
        )
        return

    # ── الإحصائيات ──
    if part == "stats":
        stats = await get_stats()
        users_count = await get_user_count()
        await q.edit_message_text(
            _format_stats(stats, users_count),
            parse_mode=ParseMode.HTML,
            reply_markup=back_inline(),
        )
        return

    # ── آخر الطلبات (مع pagination) ──
    if part.startswith("recent"):
        parts_split = part.split(":")
        page = int(parts_split[1]) if len(parts_split) > 1 else 0
        reqs = await get_recent_requests(50)
        msg = _format_recent(reqs, page)
        has_next = len(reqs) > (page + 1) * PAGE_SIZE
        await q.edit_message_text(
            msg, parse_mode=ParseMode.HTML,
            reply_markup=requests_nav_inline(page, has_next),
        )
        return

    # ── المستخدمون ──
    if part == "users":
        users = await get_all_users()
        lines = [f"👥 <b>المستخدمون ({len(users)})</b>\n"]
        for u in users[:30]:
            uname_str = f"@{u.get('username')}" if u.get("username") else "بدون معرّف"
            lines.append(f"• <code>{u.get('userId')}</code> {uname_str} — {u.get('fullName','')[:20]}")
        if len(users) > 30:
            lines.append(f"\n  … و{len(users)-30} آخرون")
        await q.edit_message_text(
            "\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=back_inline()
        )
        return

    # ── حسب النوع ──
    if part == "types":
        reqs = await get_recent_requests(500)
        types: dict = {}
        for r in reqs:
            t = r.get("fileType", "غير معروف")
            types[t] = types.get(t, 0) + 1
        lines = ["📂 <b>الطلبات حسب النوع</b>\n"]
        for t, cnt in sorted(types.items(), key=lambda x: -x[1]):
            lines.append(f"  • {t}: <b>{cnt}</b>")
        await q.edit_message_text(
            "\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=back_inline()
        )
        return

    # ── حالة Convex ──
    if part == "sync_convex":
        try:
            from db.convex_client import get_stats, get_user_count
            stats = await get_stats()
            users = await get_user_count()
            await q.edit_message_text(
                f"☁️ <b>Convex — قاعدة البيانات الأساسية</b>\n\n"
                f"👥 المستخدمون: <b>{users}</b>\n"
                f"📋 الطلبات الكلية: <b>{stats.get('total', 0)}</b>\n"
                f"✅ ناجحة: <b>{stats.get('success', 0)}</b>  |  ❌ أخطاء: <b>{stats.get('error', 0)}</b>\n"
                f"📄 الصفحات: <b>{stats.get('totalPages', 0)}</b>\n\n"
                f"<i>كل طلب جديد يُحفظ مباشرةً في Convex</i>",
                parse_mode=ParseMode.HTML,
                reply_markup=back_inline(),
            )
        except Exception as e:
            await q.edit_message_text(
                f"❌ <b>تعذّر الاتصال بـ Convex:</b> {e}",
                parse_mode=ParseMode.HTML,
                reply_markup=back_inline(),
            )
        return

    # ── طلب إذاعة ──
    if part == "broadcast_prompt":
        context.user_data["awaiting_broadcast"] = True
        await q.edit_message_text(
            "📢 <b>إذاعة للجميع</b>\n\n"
            "أرسل النص الذي تريد إرساله لجميع المستخدمين المسجّلين.\n"
            "/cancel للإلغاء.",
            parse_mode=ParseMode.HTML,
        )
        return

    # ── تأكيد الإذاعة وتنفيذها ──
    if part == "broadcast_send":
        text = context.user_data.pop("broadcast_text", None)
        if not text:
            await q.answer("❌ لا يوجد نص محفوظ.", show_alert=True)
            return
        await q.edit_message_text("⏳ جارٍ إرسال الإذاعة…", parse_mode=ParseMode.HTML)
        sent, failed = await execute_broadcast(q.get_bot(), text)
        await q.edit_message_text(
            f"📢 <b>اكتملت الإذاعة</b>\n\n"
            f"✅ أُرسلت لـ <b>{sent}</b> مستخدم\n"
            f"❌ فشلت لـ <b>{failed}</b> مستخدم",
            parse_mode=ParseMode.HTML,
            reply_markup=back_inline(),
        )
        return


# ─── تنسيق النصوص ───────────────────────────────────────────────────────────

def _format_stats(stats: dict, users_count: int = 0) -> str:
    if not stats:
        return "📊 <b>الإحصائيات</b>\n\nلا توجد بيانات بعد."
    return (
        "📊 <b>إحصائيات البوت</b>\n\n"
        f"📦 إجمالي الطلبات: <b>{stats.get('total', 0)}</b>\n"
        f"✅ ناجحة:          <b>{stats.get('success', 0)}</b>\n"
        f"❌ فاشلة:          <b>{stats.get('error', 0)}</b>\n"
        f"👥 مستخدمون (طلبات): <b>{stats.get('uniqueUsers', 0)}</b>\n"
        f"👤 مسجّلون في DB:  <b>{users_count}</b>\n"
        f"📄 إجمالي الصفحات: <b>{stats.get('totalPages', 0)}</b>\n"
        f"📝 إجمالي الفقرات: <b>{stats.get('totalLines', 0)}</b>"
    )


def _format_recent(reqs: list, page: int) -> str:
    start = page * PAGE_SIZE
    chunk = reqs[start: start + PAGE_SIZE]
    if not chunk:
        return "📋 لا توجد طلبات."
    total = len(reqs)
    lines = [f"📋 <b>آخر الطلبات</b> (صفحة {page+1}/{-(-total//PAGE_SIZE)})\n"]
    for r in chunk:
        icon = "✅" if r.get("status") == "success" else "❌"
        lines.append(
            f"{icon} <code>{r.get('userId','?')}</code> @{r.get('username','?')} — "
            f"{r.get('fileType','?')} ({r.get('pages',0)}ص/{r.get('lines',0)}ف)\n"
            f"   🕐 {r.get('createdAt','')[:16]}"
        )
    return "\n".join(lines)
