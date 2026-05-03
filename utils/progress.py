"""
شريط تقدم مرئي — يُعدَّل في نفس الرسالة لحظةً بلحظة.
"""
import logging
from telegram import Message
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

_BAR_LEN = 14
_FILLED  = "█"
_EMPTY   = "░"


def _bar(pct: float) -> str:
    filled = round(_BAR_LEN * pct / 100)
    return f"[{_FILLED * filled}{_EMPTY * (_BAR_LEN - filled)}]"


def _build_text(step: str, pct: float, detail: str = "") -> str:
    bar  = _bar(pct)
    line = f"⏳ <b>{step}</b>\n{bar} <b>{int(pct)}%</b>"
    if detail:
        line += f"\n<i>{detail}</i>"
    return line


class ProgressMessage:

    def __init__(self, msg: Message) -> None:
        self._msg       = msg
        self._last_text = ""

    @classmethod
    async def create(cls, parent: Message, title: str) -> "ProgressMessage":
        text = _build_text(title, 0, "بس لحظة، گاعد نبدأ…")
        msg  = await parent.reply_text(text, parse_mode=ParseMode.HTML)
        pm   = cls(msg)
        pm._last_text = text
        return pm

    async def update(self, pct: float, detail: str = "", step: str = "") -> None:
        title = step or "گاعد يشتغل…"
        text  = _build_text(title, min(pct, 99), detail)
        if text == self._last_text:
            return
        try:
            await self._msg.edit_text(text, parse_mode=ParseMode.HTML)
            self._last_text = text
        except Exception as e:
            logger.debug(f"ما قدر يحدّث شريط التقدم: {e}")

    async def done(self, final_text: str) -> None:
        try:
            await self._msg.edit_text(final_text, parse_mode=ParseMode.HTML)
        except Exception:
            pass

    async def error(self, err_text: str) -> None:
        try:
            await self._msg.edit_text(f"❌ {err_text}", parse_mode=ParseMode.HTML)
        except Exception:
            pass
