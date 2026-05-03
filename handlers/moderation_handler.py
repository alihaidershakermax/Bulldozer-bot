"""
نظام الإشراف والإدارة
======================
- حظر / رفع حظر المستخدمين
- إدارة الأدمنية (إضافة / حذف)
- إعدادات البوت (الحد اليومي للطلبات)
- نشاط المستخدمين
"""
import logging
import os
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db.convex_client import (
    ban_user, unban_user, get_banned_users,
    add_admin, remove_admin, get_admins,
    get_setting, set_setting, get_all_settings,
    get_active_users,
)
from keyboards import back_inline

logger = logging.getLogger(__name__)

_SUPER_ADMIN = int(os.getenv("ADMIN_IDS", "960173511").split(",")[0].strip())


# ─── لوحات المفاتيح ──────────────────────────────────────────────────────────

def banned_list_inline(banned: list) -> InlineKeyboardMarkup:
    rows = []
    for u in banned[:10]:
        uid  = u.get("userId", "?")
        name = (u.get("fullName") or u.get("username") or uid)[:18]
        rows.append([InlineKeyboardButton(
            f"🔓 رفع حظر {name}",
            callback_data=f"mod:unban:{uid}",
        )])
    rows.append([
        InlineKeyboardButton("🚫 حظر مستخدم جديد", callback_data="mod:ban_prompt"),
        InlineKeyboardButton("🔙 رجوع", callback_data="adm:home"),
    ])
    return InlineKeyboardMarkup(rows)


def admins_list_inline(admins: list) -> InlineKeyboardMarkup:
    rows = []
    for a in admins:
        uid = a.get("userId", "?")
        rows.append([InlineKeyboardButton(
            f"❌ إزالة {uid}",
            callback_data=f"mod:del_admin:{uid}",
        )])
    rows.append([
        InlineKeyboardButton("➕ إضافة أدمن", callback_data="mod:add_admin_prompt"),
        InlineKeyboardButton("🔙 رجوع",        callback_data="adm:home"),
    ])
    return InlineKeyboardMarkup(rows)


def settings_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ تغيير الحد اليومي للطلبات", callback_data="mod:set_limit_prompt")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="adm:home")],
    ])


def activity_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 رجوع", callback_data="adm:home"),
    ]])


# ─── معالج الـ Callbacks ─────────────────────────────────────────────────────

async def handle_moderation_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    q    = update.callback_query
    await q.answer()
    data = q.data or ""

    if not data.startswith("mod:"):
        return

    part = data[4:]

    # ── قائمة المحظورين ──────────────────────────────────────────────────
    if part == "ban_list":
        banned = await get_banned_users()
        if not banned:
            await q.edit_message_text(
                "🚫 <b>المحظورون</b>\n\nلا يوجد أي مستخدم محظور حالياً.",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🚫 حظر مستخدم", callback_data="mod:ban_prompt"),
                    InlineKeyboardButton("🔙 رجوع",        callback_data="adm:home"),
                ]]),
            )
        else:
            lines = [f"🚫 <b>المحظورون ({len(banned)})</b>\n"]
            for u in banned[:15]:
                uid    = u.get("userId", "?")
                name   = u.get("fullName") or u.get("username") or "—"
                reason = u.get("banReason") or "—"
                lines.append(f"• <code>{uid}</code> {name}\n  السبب: {reason}")
            await q.edit_message_text(
                "\n".join(lines),
                parse_mode=ParseMode.HTML,
                reply_markup=banned_list_inline(banned),
            )
        return

    # ── طلب حظر مستخدم ──────────────────────────────────────────────────
    if part == "ban_prompt":
        context.user_data["awaiting_ban"] = True
        await q.edit_message_text(
            "🚫 <b>حظر مستخدم</b>\n\n"
            "أرسل رسالة بالصيغة:\n"
            "<code>USER_ID سبب الحظر</code>\n\n"
            "مثال: <code>123456789 إساءة استخدام</code>\n\n"
            "/cancel للإلغاء.",
            parse_mode=ParseMode.HTML,
        )
        return

    # ── رفع حظر مباشر ───────────────────────────────────────────────────
    if part.startswith("unban:"):
        uid_str = part[6:]
        try:
            uid = int(uid_str)
            ok  = await unban_user(uid)
            msg = f"✅ تم رفع الحظر عن <code>{uid}</code>" if ok else f"⚠️ المستخدم <code>{uid}</code> غير موجود"
        except Exception as e:
            msg = f"❌ خطأ: {e}"
        await q.edit_message_text(msg, parse_mode=ParseMode.HTML, reply_markup=back_inline())
        return

    # ── قائمة الأدمنية ───────────────────────────────────────────────────
    if part == "admins_list":
        admins = await get_admins()
        lines  = [f"👮 <b>الأدمنية ({len(admins)} + الأدمن الرئيسي)</b>\n"]
        lines.append(f"⭐ <b>الرئيسي:</b> <code>{_SUPER_ADMIN}</code>\n")
        for a in admins:
            uid  = a.get("userId", "?")
            date = a.get("addedAt", "")[:10]
            lines.append(f"• <code>{uid}</code> — أُضيف {date}")
        await q.edit_message_text(
            "\n".join(lines),
            parse_mode=ParseMode.HTML,
            reply_markup=admins_list_inline(admins),
        )
        return

    # ── طلب إضافة أدمن ──────────────────────────────────────────────────
    if part == "add_admin_prompt":
        context.user_data["awaiting_add_admin"] = True
        await q.edit_message_text(
            "👮 <b>إضافة أدمن جديد</b>\n\n"
            "أرسل الـ ID الخاص بالمستخدم الذي تريد تعيينه أدمناً.\n\n"
            "/cancel للإلغاء.",
            parse_mode=ParseMode.HTML,
        )
        return

    # ── حذف أدمن مباشر ──────────────────────────────────────────────────
    if part.startswith("del_admin:"):
        uid_str = part[10:]
        try:
            uid = int(uid_str)
            if uid == _SUPER_ADMIN:
                await q.edit_message_text(
                    "⛔ لا يمكن حذف الأدمن الرئيسي.",
                    parse_mode=ParseMode.HTML,
                    reply_markup=back_inline(),
                )
                return
            ok  = await remove_admin(uid)
            # إزالة من الكاش المحلي
            from handlers.admin_handler import _extra_admin_ids
            _extra_admin_ids.discard(uid)
            msg = f"✅ تم إزالة <code>{uid}</code> من الأدمنية" if ok else f"⚠️ <code>{uid}</code> غير موجود"
        except Exception as e:
            msg = f"❌ خطأ: {e}"
        await q.edit_message_text(msg, parse_mode=ParseMode.HTML, reply_markup=back_inline())
        return

    # ── الإعدادات ────────────────────────────────────────────────────────
    if part == "settings":
        daily_limit = await get_setting("daily_limit", "5")
        await q.edit_message_text(
            f"⚙️ <b>إعدادات البوت</b>\n\n"
            f"📊 الحد اليومي للطلبات: <b>{daily_limit}</b> طلب/مستخدم\n\n"
            "<i>يمكنك تغيير الإعدادات من الأزرار أدناه.</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=settings_inline(),
        )
        return

    # ── طلب تغيير الحد اليومي ────────────────────────────────────────────
    if part == "set_limit_prompt":
        context.user_data["awaiting_set_limit"] = True
        current = await get_setting("daily_limit", "5")
        await q.edit_message_text(
            f"✏️ <b>تغيير الحد اليومي</b>\n\n"
            f"الحد الحالي: <b>{current}</b> طلب/يوم\n\n"
            "أرسل الرقم الجديد (مثال: <code>10</code>)\n"
            "أرسل <code>0</code> لرفع الحد نهائياً.\n\n"
            "/cancel للإلغاء.",
            parse_mode=ParseMode.HTML,
        )
        return

    # ── نشاط المستخدمين ──────────────────────────────────────────────────
    if part == "activity":
        users = await get_active_users(limit=20)
        if not users:
            await q.edit_message_text(
                "📊 لا يوجد بيانات نشاط بعد.",
                parse_mode=ParseMode.HTML,
                reply_markup=back_inline(),
            )
            return
        lines = [f"📊 <b>نشاط المستخدمين (آخر {len(users)})</b>\n"]
        for u in users:
            uid   = u.get("userId", "?")
            name  = (u.get("fullName") or u.get("username") or "—")[:20]
            uname = f"@{u['username']}" if u.get("username") else "—"
            last  = u.get("lastActive", "")[:16].replace("T", " ")
            ban   = " 🚫" if u.get("isBanned") else ""
            lines.append(f"• <code>{uid}</code> {name} {uname}{ban}\n  ⏰ {last}")
        await q.edit_message_text(
            "\n".join(lines),
            parse_mode=ParseMode.HTML,
            reply_markup=activity_inline(),
        )
        return


# ─── دوال عرض مباشرة (من الكيبورد) ──────────────────────────────────────────

async def show_banned_list(update: Update) -> None:
    """يعرض قائمة المحظورين من زر الكيبورد مباشرة."""
    from keyboards import ADMIN_KEYBOARD
    banned = await get_banned_users()
    if not banned:
        await update.message.reply_text(
            "🚫 <b>المحظورون</b>\n\nلا يوجد أي مستخدم محظور حالياً.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🚫 حظر مستخدم", callback_data="mod:ban_prompt"),
            ]]),
        )
        return
    lines = [f"🚫 <b>المحظورون ({len(banned)})</b>\n"]
    for u in banned[:15]:
        uid    = u.get("userId", "?")
        name   = u.get("fullName") or u.get("username") or "—"
        reason = u.get("banReason") or "—"
        lines.append(f"• <code>{uid}</code> {name}\n  السبب: {reason}")
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.HTML,
        reply_markup=banned_list_inline(banned),
    )


async def show_admins_list(update: Update) -> None:
    """يعرض قائمة الأدمنية من زر الكيبورد مباشرة."""
    admins = await get_admins()
    lines  = [f"👮 <b>الأدمنية ({len(admins)} + الأدمن الرئيسي)</b>\n"]
    lines.append(f"⭐ <b>الرئيسي:</b> <code>{_SUPER_ADMIN}</code>\n")
    for a in admins:
        uid  = a.get("userId", "?")
        date = a.get("addedAt", "")[:10]
        lines.append(f"• <code>{uid}</code> — أُضيف {date}")
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.HTML,
        reply_markup=admins_list_inline(admins),
    )


async def show_settings(update: Update) -> None:
    """يعرض إعدادات البوت من زر الكيبورد مباشرة."""
    daily_limit = await get_setting("daily_limit", "5")
    await update.message.reply_text(
        f"⚙️ <b>إعدادات البوت</b>\n\n"
        f"📊 الحد اليومي للطلبات: <b>{daily_limit}</b> طلب/مستخدم\n\n"
        "<i>اختر الإعداد الذي تريد تغييره:</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=settings_inline(),
    )


async def show_activity(update: Update) -> None:
    """يعرض نشاط المستخدمين من زر الكيبورد مباشرة."""
    users = await get_active_users(limit=20)
    if not users:
        await update.message.reply_text(
            "📈 لا يوجد بيانات نشاط بعد.",
            parse_mode=ParseMode.HTML,
        )
        return
    lines = [f"📈 <b>نشاط المستخدمين (آخر {len(users)})</b>\n"]
    for u in users:
        uid   = u.get("userId", "?")
        name  = (u.get("fullName") or u.get("username") or "—")[:20]
        uname = f"@{u['username']}" if u.get("username") else "—"
        last  = u.get("lastActive", "")[:16].replace("T", " ")
        ban   = " 🚫" if u.get("isBanned") else ""
        lines.append(f"• <code>{uid}</code> {name} {uname}{ban}\n  ⏰ {last}")
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.HTML,
        reply_markup=activity_inline(),
    )


# ─── معالجة الرسائل النصية (ردود الانتظار) ───────────────────────────────────

async def handle_moderation_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    """
    يعالج نصوص الانتظار (حظر، أدمن، إعدادات).
    يُعيد True إذا عالج الرسالة.
    """
    text  = (update.message.text or "").strip()
    admin = context.user_data

    from handlers.admin_handler import is_admin
    if not is_admin(update):
        return False

    from keyboards import ADMIN_KEYBOARD

    # ── انتظار ID للحظر ──────────────────────────────────────────────────
    if admin.get("awaiting_ban"):
        admin.pop("awaiting_ban", None)
        parts = text.split(maxsplit=1)
        if not parts or not parts[0].lstrip("-").isdigit():
            await update.message.reply_text(
                "❌ صيغة غير صحيحة. أرسل: <code>USER_ID سبب</code>",
                parse_mode=ParseMode.HTML, reply_markup=ADMIN_KEYBOARD,
            )
            return True
        uid    = int(parts[0])
        reason = parts[1] if len(parts) > 1 else ""
        ok     = await ban_user(uid, reason)
        msg    = (f"✅ تم حظر <code>{uid}</code>"
                  + (f"\nالسبب: {reason}" if reason else "")) if ok else f"❌ فشل الحظر"
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML, reply_markup=ADMIN_KEYBOARD)
        return True

    # ── انتظار ID لإضافة أدمن ────────────────────────────────────────────
    if admin.get("awaiting_add_admin"):
        admin.pop("awaiting_add_admin", None)
        if not text.lstrip("-").isdigit():
            await update.message.reply_text(
                "❌ أرسل ID رقمي فقط.", parse_mode=ParseMode.HTML, reply_markup=ADMIN_KEYBOARD
            )
            return True
        uid = int(text)
        ok  = await add_admin(uid)
        if ok:
            from handlers.admin_handler import _extra_admin_ids
            _extra_admin_ids.add(uid)
        msg = f"✅ تم إضافة <code>{uid}</code> كأدمن" if ok else f"❌ فشل الإضافة"
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML, reply_markup=ADMIN_KEYBOARD)
        return True

    # ── انتظار رقم الحد اليومي ───────────────────────────────────────────
    if admin.get("awaiting_set_limit"):
        admin.pop("awaiting_set_limit", None)
        if not text.isdigit():
            await update.message.reply_text(
                "❌ أرسل رقماً صحيحاً فقط.", parse_mode=ParseMode.HTML, reply_markup=ADMIN_KEYBOARD
            )
            return True
        limit = int(text)
        ok    = await set_setting("daily_limit", str(limit))
        if limit == 0:
            msg = "✅ تم <b>رفع الحد اليومي</b> — المستخدمون يقدرون يرسلون بلا حدود."
        else:
            msg = f"✅ تم تغيير الحد اليومي إلى <b>{limit}</b> طلب/يوم."
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML, reply_markup=ADMIN_KEYBOARD)
        return True

    return False
