"""
مساعد لتشغيل مهام الخلفية بأمان — أي خطأ يُسجَّل فقط ولا يُوقف البوت.
"""
import asyncio
import logging

logger = logging.getLogger(__name__)


def fire(coro) -> asyncio.Task:
    """شغّل coroutine في الخلفية بشكل آمن — لا ينتظر ولا يُوقف البوت."""
    async def _run():
        try:
            await coro
        except Exception as e:
            logger.warning(f"[background] {type(e).__name__}: {e}")

    return asyncio.ensure_future(_run())
