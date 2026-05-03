"""
الدعم الفني + التواصل مع المطور + رد الأدمن
=============================================
🛠 الدعم الفني    → المستخدم يكتب مشكلته → تُرسل للأدمن مع زر "↩️ رد"
👨‍💻 راسل المطور  → نفس الآلية لكن مميّزة بـ "للمطور"
↩️ رد الأدمن     → الأدمن يضغط الزر ← يكتب الرد ← يصل للمستخدم مباشرة
"""
import logging
import os
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

_ADMIN_ID = int(os.getenv("ADMIN_IDS", "960173511").split(",")[0].strip())


# ─── أزرار ───────────────────────────────────────────────────────────────────

def _cancel_inline(cb: str = "support:cancel") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("❌ إلغاء", callback_data=cb),
    ]])


def _admin_reply_inline(user_id: int) -> InlineKeyboardMarkup:
    """زر رد الأدمن على المستخدم."""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("↩️ رد على المستخدم", callback_data=f"support:reply:{user_id}"),
    ]])


# ─── بدء جلسة الدعم الفني ────────────────────────────────────────────────────

async def cmd_support(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """يبدأ جلسة الدعم الفني العادية."""
    context.user_data["awaiting_support"] = "support"
    await update.message.reply_text(
        "🛠 <b>الدعم الفني</b>\n\n"
        "اكتب مشكلتك أو سؤالك بالتفصيل وسيصلك رد من الأدمن قريباً.\n\n"
        "<i>اضغط إلغاء للخروج بدون إرسال.</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=_cancel_inline("support:cancel"),
    )


# ─── معالج رسائل الدعم / المطور (من المستخدم) ────────────────────────────────

async def handle_support_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    يعالج رسالة الدعم أو رسالة المطور إذا كان المستخدم في وضع الانتظار.
    يُعيد True إذا تمّت المعالجة.
    """
    mode = context.user_data.get("awaiting_support")
    if not mode:
        return False

    context.user_data.pop("awaiting_support", None)
    user  = update.message.from_user
    text  = update.message.text or ""
    name  = user.full_name or user.first_name or "—"
    uname = f"@{user.username}" if user.username else "بدون معرّف"

    is_dev = (mode == "developer")
    label  = "رسالة للمطور 👨‍💻" if is_dev else "رسالة دعم فني 🛠"
    icon   = "👨‍💻" if is_dev else "🛠"

    msg_to_admin = (
        f"{icon} <b>{label}</b>\n\n"
        f"👤 المستخدم: {name} ({uname})\n"
        f"🆔 ID: <code>{user.id}</code>\n\n"
        f"📩 <b>الرسالة:</b>\n{text}"
    )
    try:
        await update.get_bot().send_message(
            chat_id=_ADMIN_ID,
            text=msg_to_admin,
            parse_mode=ParseMode.HTML,
            reply_markup=_admin_reply_inline(user.id),   # ← زر الرد
        )
    except Exception as e:
        logger.warning(f"فشل إرسال {label} للأدمن: {e}")

    from keyboards import USER_KEYBOARD, ADMIN_KEYBOARD
    from handlers.admin_handler import is_admin
    markup = ADMIN_KEYBOARD if is_admin(update) else USER_KEYBOARD

    confirm = (
        "✅ <b>تم إرسال رسالتك للمطور!</b>\n\nسيتواصل معك قريباً. 🙏"
        if is_dev else
        "✅ <b>تم إرسال رسالتك!</b>\n\nسيتواصل معك الأدمن قريباً. 🙏"
    )
    await update.message.reply_text(
        confirm,
        parse_mode=ParseMode.HTML,
        reply_markup=markup,
    )
    return True


# ─── معالج رد الأدمن (نص) ────────────────────────────────────────────────────

async def handle_admin_reply_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    يُرسل رد الأدمن للمستخدم المحدد.
    يُعيد True إذا عالج الرسالة.
    """
    target_id = context.user_data.get("awaiting_reply_to")
    if not target_id:
        return False

    context.user_data.pop("awaiting_reply_to", None)
    reply_text = update.message.text or ""

    if not reply_text.strip():
        await update.message.reply_text("⚠️ الرسالة فارغة، ما تم الإرسال.")
        return True

    # أرسل رد الأدمن للمستخدم
    admin = update.message.from_user
    admin_name = admin.full_name or admin.first_name or "الأدمن"
    try:
        await update.get_bot().send_message(
            chat_id=target_id,
            text=(
                f"📬 <b>رد من الأدمن</b>\n\n"
                f"{reply_text}"
            ),
            parse_mode=ParseMode.HTML,
        )
        logger.info(f"أرسل الأدمن {admin.id} رداً للمستخدم {target_id}")
        await update.message.reply_text(
            f"✅ تم إرسال ردّك للمستخدم <code>{target_id}</code> بنجاح.",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logger.warning(f"فشل إرسال رد الأدمن للمستخدم {target_id}: {e}")
        await update.message.reply_text(
            f"❌ فشل إرسال الرد: {e}",
            parse_mode=ParseMode.HTML,
        )
    return True


# ─── معالج callback buttons ──────────────────────────────────────────────────

async def handle_support_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """يعالج: support:cancel، support:dev، support:reply:{id}"""
    q = update.callback_query
    await q.answer()
    data = q.data or ""

    from keyboards import USER_KEYBOARD, ADMIN_KEYBOARD
    from handlers.admin_handler import is_admin
    markup = ADMIN_KEYBOARD if is_admin(update) else USER_KEYBOARD

    # ── إلغاء ────────────────────────────────────────────────────────────────
    if data == "support:cancel":
        context.user_data.pop("awaiting_support",   None)
        context.user_data.pop("awaiting_reply_to",  None)
        try:
            await q.edit_message_text("✅ تم الإلغاء.", parse_mode=ParseMode.HTML)
        except Exception:
            pass
        await q.message.reply_text(
            "📎 أرسل ملفاً أو صورة، أو اختر من الأزرار أدناه.",
            reply_markup=markup,
        )
        return

    # ── بدء تواصل مع المطور ──────────────────────────────────────────────────
    if data == "support:dev":
        context.user_data["awaiting_support"] = "developer"
        dev_text = (
            "📩 <b>راسل المطور</b>\n\n"
            "اكتب رسالتك وسيصلك رد من المطور قريباً.\n\n"
            "<i>اضغط إلغاء للخروج.</i>"
        )
        cancel_kb = _cancel_inline("support:cancel")
        try:
            if q.message.photo:
                await q.edit_message_caption(
                    caption=dev_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=cancel_kb,
                )
            else:
                await q.edit_message_text(
                    dev_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=cancel_kb,
                )
        except Exception:
            await q.message.reply_text(
                dev_text,
                parse_mode=ParseMode.HTML,
                reply_markup=cancel_kb,
            )
        return

    # ── رد الأدمن على مستخدم ─────────────────────────────────────────────────
    if data.startswith("support:reply:"):
        try:
            target_id = int(data.split(":")[-1])
        except ValueError:
            await q.answer("❌ معرّف غير صالح", show_alert=True)
            return

        context.user_data["awaiting_reply_to"] = target_id

        try:
            # أضف زر إلغاء للرسالة الأصلية
            await q.edit_message_reply_markup(
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        "↩️ جاري الرد…", callback_data="support:noop"
                    ),
                    InlineKeyboardButton(
                        "❌ إلغاء الرد", callback_data="support:cancel"
                    ),
                ]])
            )
        except Exception:
            pass

        await q.message.reply_text(
            f"✏️ <b>اكتب ردّك على المستخدم</b> <code>{target_id}</code>\n\n"
            "<i>اكتب الرسالة الآن وسترسل مباشرة، أو /cancel للإلغاء.</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=_cancel_inline("support:cancel"),
        )
        return

    # ── noop (زر جاري الرد) ───────────────────────────────────────────────────
    if data == "support:noop":
        await q.answer("الرد قيد الكتابة…")
        return
