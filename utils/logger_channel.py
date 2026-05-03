"""
إرسال رسائل السجل إلى قناة Telegram.
يُرسَل حدثان فقط:
  • مستخدم جديد (log_new_user)
  • ملف تُرجم بنجاح (log_success)
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from telegram import Bot
from telegram.constants import ParseMode
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_LOG_CHANNEL

logger = logging.getLogger(__name__)

_bot: Optional[Bot] = None


def _get_bot() -> Optional[Bot]:
    global _bot
    if not TELEGRAM_LOG_CHANNEL:
        return None
    if _bot is None:
        _bot = Bot(token=TELEGRAM_BOT_TOKEN)
    return _bot


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


async def _send(text: str) -> None:
    bot = _get_bot()
    if not bot or not TELEGRAM_LOG_CHANNEL:
        return
    try:
        await bot.send_message(
            chat_id=TELEGRAM_LOG_CHANNEL,
            text=text,
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logger.warning(f"تعذّر إرسال اللوق للقناة: {e}")


async def log_new_user(user_id: int, username: str, full_name: str) -> None:
    await _send(
        f"👤 <b>مستخدم جديد</b>\n"
        f"🆔 <code>{user_id}</code>\n"
        f"📛 {full_name}\n"
        f"🔗 @{username or 'بدون معرّف'}\n"
        f"🕐 {_now()}"
    )


async def log_success(
    user_id: int,
    username: str,
    file_type: str,
    pages: int,
    paragraphs: int,
) -> None:
    await _send(
        f"✅ <b>ترجمة مكتملة — {file_type}</b>\n"
        f"🆔 <code>{user_id}</code> | @{username or 'مجهول'}\n"
        f"📄 {pages} صفحة | 📝 {paragraphs} فقرة\n"
        f"🕐 {_now()}"
    )
