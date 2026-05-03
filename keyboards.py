"""
تعريف جميع لوحات المفاتيح المستخدمة في البوت.
"""
from telegram import (
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    KeyboardButton,
)

# ─── لوحة المستخدم العادي ───────────────────────────────────────────────────
USER_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton("🛠 الدعم الفني"),  KeyboardButton("👨‍💻 المطور")],
        [KeyboardButton("❓ مساعدة"),        KeyboardButton("📊 إحصائياتي")],
    ],
    resize_keyboard=True,
    input_field_placeholder="أرسل ملفاً أو اضغط زراً…",
)

# ─── لوحة الأدمن ───────────────────────────────────────────────────────────
ADMIN_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[
        # ── الإحصائيات والمتابعة ──────────────────────────────────────
        [KeyboardButton("📊 إحصائيات"),     KeyboardButton("📋 آخر الطلبات"),  KeyboardButton("📈 النشاط")],
        # ── إدارة المستخدمين ─────────────────────────────────────────
        [KeyboardButton("👥 المستخدمون"),   KeyboardButton("🚫 المحظورون"),    KeyboardButton("👮 الأدمنية")],
        # ── أدوات البوت ──────────────────────────────────────────────
        [KeyboardButton("⚙️ الإعدادات"),    KeyboardButton("📢 إذاعة"),        KeyboardButton("☁️ Convex")],
        # ── للمالك والمستخدمين ───────────────────────────────────────
        [KeyboardButton("🛠 الدعم الفني"),  KeyboardButton("📊 إحصائياتي"),   KeyboardButton("❓ مساعدة")],
        # ── معلومات ──────────────────────────────────────────────────
        [KeyboardButton("👨‍💻 المطور")],
    ],
    resize_keyboard=True,
    input_field_placeholder="اختر أمراً أو أرسل ملفاً…",
)

# ─── Inline: تسجيل المستخدم ─────────────────────────────────────────────────
def user_register_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ تسجيل الآن", callback_data="reg:confirm"),
    ]])


# ─── Inline: إحصائيات المستخدم ──────────────────────────────────────────────
def user_stats_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📅 اليوم",       callback_data="stats:today"),
            InlineKeyboardButton("📆 هذا الشهر",   callback_data="stats:month"),
            InlineKeyboardButton("🗓 هذه السنة",   callback_data="stats:year"),
        ],
        [InlineKeyboardButton("❌ إغلاق", callback_data="stats:close")],
    ])


# ─── Inline: لوحة الأدمن الرئيسية ──────────────────────────────────────────
def admin_home_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 الإحصائيات",     callback_data="adm:stats"),
            InlineKeyboardButton("📋 آخر الطلبات",    callback_data="adm:recent:0"),
        ],
        [
            InlineKeyboardButton("👥 المستخدمون",     callback_data="adm:users"),
            InlineKeyboardButton("📈 نشاط المستخدمين", callback_data="mod:activity"),
        ],
        [
            InlineKeyboardButton("🚫 المحظورون",      callback_data="mod:ban_list"),
            InlineKeyboardButton("👮 الأدمنية",       callback_data="mod:admins_list"),
        ],
        [
            InlineKeyboardButton("⚙️ الإعدادات",      callback_data="mod:settings"),
            InlineKeyboardButton("📂 حسب النوع",      callback_data="adm:types"),
        ],
        [
            InlineKeyboardButton("📢 إذاعة للجميع",   callback_data="adm:broadcast_prompt"),
            InlineKeyboardButton("🔄 تحديث",           callback_data="adm:refresh"),
        ],
        [
            InlineKeyboardButton("☁️ Convex DB",      callback_data="adm:sync_convex"),
        ],
    ])


def developer_contact_inline() -> InlineKeyboardMarkup:
    from config import DEVELOPER_WEBSITE, DEVELOPER_USERNAME, DEVELOPER_INSTAGRAM
    rows = []

    # صف 1: تلغرام + انستغرام
    row1 = []
    if DEVELOPER_USERNAME:
        row1.append(InlineKeyboardButton(
            "💬 تلغرام",
            url=f"https://t.me/{DEVELOPER_USERNAME.lstrip('@')}",
        ))
    if DEVELOPER_INSTAGRAM:
        row1.append(InlineKeyboardButton(
            "📸 انستغرام",
            url=DEVELOPER_INSTAGRAM,
        ))
    if row1:
        rows.append(row1)

    # صف 2: الموقع الشخصي
    if DEVELOPER_WEBSITE:
        rows.append([InlineKeyboardButton(
            "🌐 موقع شخصي",
            url=DEVELOPER_WEBSITE,
        )])

    # صف 3: التواصل عبر البوت (دائماً)
    rows.append([InlineKeyboardButton("📩 راسل المطور عبر البوت", callback_data="support:dev")])
    return InlineKeyboardMarkup(rows)


def back_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 رجوع", callback_data="adm:home"),
    ]])


def requests_nav_inline(page: int, has_next: bool) -> InlineKeyboardMarkup:
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ السابق", callback_data=f"adm:recent:{page-1}"))
    if has_next:
        nav.append(InlineKeyboardButton("التالي ▶️", callback_data=f"adm:recent:{page+1}"))
    rows = []
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="adm:home")])
    return InlineKeyboardMarkup(rows)


def broadcast_confirm_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ إرسال", callback_data="adm:broadcast_send"),
        InlineKeyboardButton("❌ إلغاء",  callback_data="adm:home"),
    ]])
