"""
Convex database client — HTTP API
يستخدم Authorization: Convex <deploy_key> للمصادقة
"""
import logging
import os
import httpx
from typing import Any, Dict, List, Tuple
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_TIMEOUT     = 8.0
_CONVEX_URL  = os.getenv("CONVEX_URL", "").rstrip("/")
_DEPLOY_KEY  = os.getenv("CONVEX_DEPLOY_KEY", "")


def _is_valid_url(url: str) -> bool:
    return bool(url) and "convex.cloud" in url


def _headers() -> dict:
    h = {"Content-Type": "application/json"}
    if _DEPLOY_KEY:
        h["Authorization"] = f"Convex {_DEPLOY_KEY}"
    return h


async def _q(path: str, args: dict = {}) -> Any:
    if not _is_valid_url(_CONVEX_URL):
        return None
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.post(
                f"{_CONVEX_URL}/api/query",
                json={"path": path, "args": args, "format": "json"},
                headers=_headers(),
            )
            if r.status_code != 200:
                logger.warning(f"Convex query {path} → {r.status_code}: {r.text[:120]}")
                return None
            body = r.json()
            return body.get("value", body)
    except httpx.TimeoutException:
        logger.warning(f"Convex query timeout: {path}")
        return None
    except Exception as e:
        logger.warning(f"Convex query error ({path}): {e}")
        return None


async def _m(path: str, args: dict = {}) -> Any:
    if not _is_valid_url(_CONVEX_URL):
        return None
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.post(
                f"{_CONVEX_URL}/api/mutation",
                json={"path": path, "args": args, "format": "json"},
                headers=_headers(),
            )
            if r.status_code != 200:
                logger.warning(f"Convex mutation {path} → {r.status_code}: {r.text[:120]}")
                return None
            body = r.json()
            return body.get("value", body)
    except httpx.TimeoutException:
        logger.warning(f"Convex mutation timeout: {path}")
        return None
    except Exception as e:
        logger.warning(f"Convex mutation error ({path}): {e}")
        return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── مستخدمون ──────────────────────────────────────────────────────────────────

async def register_user(user_id: int, username: str, full_name: str) -> bool:
    result = await _m("users:upsert", {
        "userId":   str(user_id),
        "username": username or "",
        "fullName": full_name or "",
        "now":      _now(),
    })
    if result and isinstance(result, dict):
        return bool(result.get("isNew", False))
    return False


async def update_activity(user_id: int) -> None:
    await _m("users:updateActivity", {"userId": str(user_id), "now": _now()})


async def get_all_users() -> List[Dict]:
    r = await _q("users:list", {})
    return r if isinstance(r, list) else []


async def get_active_users(limit: int = 20) -> List[Dict]:
    r = await _q("users:listActive", {"limit": limit})
    return r if isinstance(r, list) else []


async def get_user_count() -> int:
    r = await _q("users:count", {})
    if r is not None:
        try:
            return int(r)
        except (TypeError, ValueError):
            pass
    return 0


# ─── حظر المستخدمين ────────────────────────────────────────────────────────────

async def ban_user(user_id: int, reason: str = "") -> bool:
    r = await _m("users:ban", {"userId": str(user_id), "reason": reason})
    return r is not None


async def unban_user(user_id: int) -> bool:
    r = await _m("users:unban", {"userId": str(user_id)})
    return r is not None


async def is_user_banned(user_id: int) -> Tuple[bool, str]:
    r = await _q("users:isBanned", {"userId": str(user_id)})
    if r and isinstance(r, dict):
        return bool(r.get("banned", False)), r.get("reason", "")
    return False, ""


async def get_banned_users() -> List[Dict]:
    r = await _q("users:listBanned", {})
    return r if isinstance(r, list) else []


# ─── طلبات ────────────────────────────────────────────────────────────────────

async def log_request(
    user_id: int, username: str, file_type: str,
    pages: int, lines: int, status: str, error: str = "",
) -> None:
    await _m("requests:create", {
        "userId":    str(user_id),
        "username":  username or "",
        "fileType":  file_type,
        "pages":     pages,
        "lines":     lines,
        "status":    status,
        "error":     error or "",
        "createdAt": _now(),
    })


async def get_stats() -> Dict[str, Any]:
    r = await _q("requests:stats", {})
    if r and isinstance(r, dict):
        return r
    return {"total": 0, "success": 0, "error": 0, "uniqueUsers": 0, "totalPages": 0, "totalLines": 0}


async def get_recent_requests(limit: int = 50) -> List[Dict]:
    r = await _q("requests:list", {"limit": limit})
    return r if isinstance(r, list) else []


async def get_user_stats(user_id: int) -> Dict[str, Any]:
    r = await _q("requests:userStats", {"userId": str(user_id)})
    if r and isinstance(r, dict):
        return r
    return {"total": 0, "today": 0, "month": 0, "year": 0}


async def get_daily_count(user_id: int) -> int:
    r = await _q("requests:dailyCount", {"userId": str(user_id)})
    if r is not None:
        try:
            return int(r)
        except (TypeError, ValueError):
            pass
    return 0


# ─── الإعدادات ─────────────────────────────────────────────────────────────────

async def get_setting(key: str, default: str = "") -> str:
    r = await _q("settings:get", {"key": key})
    if r and isinstance(r, dict):
        return r.get("value", default)
    return default


async def set_setting(key: str, value: str) -> bool:
    r = await _m("settings:set", {"key": key, "value": value})
    return r is not None


async def get_all_settings() -> List[Dict]:
    r = await _q("settings:getAll", {})
    return r if isinstance(r, list) else []


# ─── الأدمنية ──────────────────────────────────────────────────────────────────

async def add_admin(user_id: int) -> bool:
    r = await _m("admins:add", {"userId": str(user_id), "addedAt": _now()})
    return r is not None


async def remove_admin(user_id: int) -> bool:
    r = await _m("admins:remove", {"userId": str(user_id)})
    return r is not None


async def get_admins() -> List[Dict]:
    r = await _q("admins:list", {})
    return r if isinstance(r, list) else []


async def is_convex_admin(user_id: int) -> bool:
    r = await _q("admins:isAdmin", {"userId": str(user_id)})
    if r and isinstance(r, dict):
        return bool(r.get("isAdmin", False))
    return False
