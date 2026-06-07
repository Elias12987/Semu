import logging
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

# ─────────────────────────────────────────
#  تنظیمات
# ─────────────────────────────────────────
BOT_TOKEN   = "8925445808:AAGkJU3BX7f82SVG4YyvYHJALKro5xrZAhM"
CHANNEL_ID  = "@VPN_IRONMAN"
ADMIN_ID    = 8471252047
CARD_NUMBER = "6219-8619-2847-2389"
CARD_OWNER  = "ایران بوصیدی"
BOT_USERNAME = "MARDAN_VPN_BOT"  # بدون @

# ─────────────────────────────────────────
#  پلن انتخابی
# ─────────────────────────────────────────
DURATIONS = {
    "1m": {"name": "۱ ماهه", "months": 1},
    "3m": {"name": "۳ ماهه", "months": 3},
}

VOLUMES = {
    "1gb":       {"name": "1GB",     "price_1m": 10_000,  "price_3m": 15_000},
    "5gb":       {"name": "5GB",     "price_1m": 50_000,  "price_3m": 75_000},
    "100gb":     {"name": "100GB",   "price_1m": 100_000, "price_3m": 150_000},
    "200gb":     {"name": "200GB",   "price_1m": 200_000, "price_3m": 300_000},
    "unlimited": {"name": "نامحدود", "price_1m": 500_000, "price_3m": 750_000},
}

SERVERS = {
    "de": {"name": "🇩🇪 آلمان"},
}

# ─────────────────────────────────────────
#  کدهای تخفیف
# ─────────────────────────────────────────
DISCOUNT_CODES = {
    "INYAS":  {"percent": 25, "first_only": False},
    "MARDAN": {"percent": 50, "first_only": True},
}

# ─────────────────────────────────────────
#  کانفیگ تست
# ─────────────────────────────────────────
TEST_CONFIG = "موجود نیست ❌"

# States
WAIT_RECEIPT       = 1
WAIT_TOPUP_RECEIPT = 2
WAIT_DISCOUNT_CODE = 3
WAIT_BROADCAST     = 4
WAIT_ADMIN_WALLET  = 5
WAIT_ADMIN_WALLET_AMOUNT = 6

logging.basicConfig(level=logging.INFO)

# ═══════════════════════════════════════════
#  دیتابیس
# ═══════════════════════════════════════════
def init_db():
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id     INTEGER PRIMARY KEY,
            username    TEXT,
            wallet      INTEGER DEFAULT 0,
            test_used   INTEGER DEFAULT 0,
            order_count INTEGER DEFAULT 0,
            referred_by INTEGER DEFAULT NULL,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS orders (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            plan        TEXT,
            amount      INTEGER,
            status      TEXT DEFAULT 'pending',
            receipt     TEXT,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS test_accounts (
            user_id     INTEGER PRIMARY KEY,
            config      TEXT,
            expire_at   TEXT
        );
        CREATE TABLE IF NOT EXISTS discount_usage (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            code        TEXT,
            used_at     TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS referrals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER,
            referred_id INTEGER,
            reward      INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    con.commit()
    con.close()

def ensure_user(user_id, username, referred_by=None):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    exists = cur.fetchone()
    if not exists:
        cur.execute(
            "INSERT INTO users (user_id, username, referred_by) VALUES (?,?,?)",
            (user_id, username, referred_by)
        )
        if referred_by:
            cur.execute(
                "INSERT INTO referrals (referrer_id, referred_id) VALUES (?,?)",
                (referred_by, user_id)
            )
    con.commit()
    con.close()
    return not exists

def get_wallet(user_id):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT wallet FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    con.close()
    return row[0] if row else 0

def get_order_count(user_id):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT order_count FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    con.close()
    return row[0] if row else 0

def update_wallet(user_id, amount):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("UPDATE users SET wallet = wallet + ? WHERE user_id=?", (amount, user_id))
    con.commit()
    con.close()

def get_referred_by(user_id):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT referred_by FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    con.close()
    return row[0] if row else None

def get_referral_count(user_id):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=?", (user_id,))
    row = cur.fetchone()
    con.close()
    return row[0] if row else 0

def get_referral_earnings(user_id):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT SUM(reward) FROM referrals WHERE referrer_id=?", (user_id,))
    row = cur.fetchone()
    con.close()
    return row[0] or 0

def add_referral_reward(referrer_id, amount):
    reward = int(amount * 0.10)
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("UPDATE users SET wallet = wallet + ? WHERE user_id=?", (reward, referrer_id))
    cur.execute(
        "UPDATE referrals SET reward = reward + ? WHERE referrer_id=? ORDER BY id DESC LIMIT 1",
        (reward, referrer_id)
    )
    con.commit()
    con.close()
    return reward

def create_order(user_id, plan, amount, receipt):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute(
        "INSERT INTO orders (user_id, plan, amount, receipt) VALUES (?,?,?,?)",
        (user_id, plan, amount, receipt)
    )
    oid = cur.lastrowid
    con.commit()
    con.close()
    return oid

def approve_order(order_id):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("UPDATE orders SET status='approved' WHERE id=?", (order_id,))
    cur.execute("SELECT user_id, amount FROM orders WHERE id=?", (order_id,))
    row = cur.fetchone()
    if row:
        cur.execute("UPDATE users SET order_count = order_count + 1 WHERE user_id=?", (row[0],))
    con.commit()
    con.close()
    return row

def test_used(user_id):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT test_used FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    con.close()
    return row[0] == 1 if row else False

def mark_test_used(user_id, config):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    expire = (datetime.now() + timedelta(days=1)).isoformat()
    cur.execute("UPDATE users SET test_used=1 WHERE user_id=?", (user_id,))
    cur.execute(
        "INSERT OR REPLACE INTO test_accounts (user_id, config, expire_at) VALUES (?,?,?)",
        (user_id, config, expire)
    )
    con.commit()
    con.close()

def check_discount_code(user_id, code):
    code = code.upper().strip()
    if code not in DISCOUNT_CODES:
        return None, "❌ کد تخفیف نامعتبر است!"
    dc = DISCOUNT_CODES[code]
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT id FROM discount_usage WHERE user_id=? AND code=?", (user_id, code))
    used = cur.fetchone()
    con.close()
    if used:
        return None, "❌ این کد قبلاً استفاده شده!"
    if dc["first_only"] and get_order_count(user_id) > 0:
        return None, "❌ این کد فقط برای اولین خرید است!"
    return dc["percent"], f"✅ کد تخفیف {dc['percent']}% اعمال شد!"

def use_discount_code(user_id, code):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("INSERT INTO discount_usage (user_id, code) VALUES (?,?)", (user_id, code.upper()))
    con.commit()
    con.close()

def get_all_users():
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT user_id FROM users")
    rows = cur.fetchall()
    con.close()
    return [r[0] for r in rows]

def get_stats():
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    total_users = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM orders WHERE status='approved'")
    total_orders = cur.fetchone()[0]
    cur.execute("SELECT SUM(amount) FROM orders WHERE status='approved'")
    total_income = cur.fetchone()[0] or 0
    cur.execute("SELECT COUNT(*) FROM orders WHERE status='pending'")
    pending_orders = cur.fetchone()[0]
    con.close()
    return total_users, total_orders, total_income, pending_orders

# ═══════════════════════════════════════════
#  بررسی عضویت کانال
# ═══════════════════════════════════════════
async def is_member(bot, user_id) -> bool:
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return False

async def check_membership(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    if not await is_member(context.bot, user_id):
        keyboard = [
            [InlineKeyboardButton("📢 عضویت در کانال", url=f"https://t.me/{CHANNEL_ID.lstrip('@')}")],
            [InlineKeyboardButton("✅ عضو شدم", callback_data="check_join")],
        ]
        msg = (
            "⚠️ برای استفاده از بات باید عضو کانال ما بشی!\n\n"
            f"کانال: {CHANNEL_ID}\n\n"
            "بعد از عضویت روی «عضو شدم» بزن."
        )
        if update.message:
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.callback_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        return False
    return True

# ═══════════════════════════════════════════
#  منوی اصلی
# ═══════════════════════════════════════════
def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 خرید VPN",        callback_data="buy")],
        [InlineKeyboardButton("🎁 تست رایگان",       callback_data="test")],
        [InlineKeyboardButton("💰 افزایش موجودی",    callback_data="topup")],
        [InlineKeyboardButton("👥 دعوت از دوستان",   callback_data="referral")],
        [InlineKeyboardButton("👤 حساب من",          callback_data="account")],
        [InlineKeyboardButton("📞 پشتیبانی",         callback_data="support")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # بررسی رفرال
    referred_by = None
    if context.args:
        try:
            referred_by = int(context.args[0])
            if referred_by == user.id:
                referred_by = None
        except:
            referred_by = None

    is_new = ensure_user(user.id, user.username, referred_by)

    if not await check_membership(update, context):
        return

    # پیام خوشامدگویی به دعوت‌کننده
    if is_new and referred_by:
        try:
            await context.bot.send_message(
                referred_by,
                f"🎉 یه نفر با لینک دعوت شما وارد شد!\n"
                f"وقتی اولین خریدش رو انجام بده، ۱۰٪ به کیف پول شما اضافه میشه."
            )
        except:
            pass

    welcome = "🌟 کاربر جدید!" if is_new else f"سلام {user.first_name} 👋"
    await update.message.reply_text(
        f"{welcome}\n\nبه بات فروش VPN خوش اومدی 🔒\nیه گزینه انتخاب کن:",
        reply_markup=main_menu_keyboard()
    )

async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    if await is_member(context.bot, user.id):
        ensure_user(user.id, user.username)
        await query.edit_message_text(
            f"✅ عضویتت تأیید شد!\n\nسلام {user.first_name} 👋\nیه گزینه انتخاب کن:",
            reply_markup=main_menu_keyboard()
        )
    else:
        await query.answer("هنوز عضو نشدی! 😕", show_alert=True)

# ═══════════════════════════════════════════
#  سیستم رفرال
# ═══════════════════════════════════════════
async def referral_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    ref_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
    count = get_referral_count(user_id)
    earnings = get_referral_earnings(user_id)

    await query.edit_message_text(
        f"👥 سیستم دعوت از دوستان\n\n"
        f"🔗 لینک دعوت شما:\n`{ref_link}`\n\n"
        f"👤 تعداد دعوت‌شدگان: {count} نفر\n"
        f"💰 درآمد از رفرال: {earnings:,} تومان\n\n"
        f"📌 قوانین:\n"
        f"• دعوت‌شونده ۱۵٪ تخفیف اولین خرید\n"
        f"• شما ۱۰٪ از هر خرید دعوت‌شونده",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 منوی اصلی", callback_data="back_main")]])
    )

# ═══════════════════════════════════════════
#  خرید VPN
# ═══════════════════════════════════════════
async def buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await check_membership(update, context):
        return
    context.user_data["custom"] = {}

    keyboard = [
        [InlineKeyboardButton(d["name"], callback_data=f"custom_dur_{k}")]
        for k, d in DURATIONS.items()
    ]
    keyboard.append([InlineKeyboardButton("🔙 برگشت", callback_data="back_main")])
    await query.edit_message_text(
        "🛒 خرید VPN\n\n📅 مدت زمان رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def custom_duration_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    dur_key = query.data.split("_")[2]
    if "custom" not in context.user_data:
        context.user_data["custom"] = {}
    context.user_data["custom"]["duration"] = dur_key

    keyboard = [
        [InlineKeyboardButton(
            f"{v['name']} — {v['price_1m'] if dur_key == '1m' else v['price_3m']:,} تومان",
            callback_data=f"custom_vol_{k}"
        )]
        for k, v in VOLUMES.items()
    ]
    keyboard.append([InlineKeyboardButton("🔙 برگشت", callback_data="buy")])
    dur = DURATIONS[dur_key]
    await query.edit_message_text(
        f"📅 مدت: {dur['name']}\n\n📊 حجم رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def custom_volume_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    vol_key = query.data.split("_")[2]
    context.user_data["custom"]["volume"] = vol_key

    keyboard = [
        [InlineKeyboardButton(s["name"], callback_data=f"custom_srv_{k}")]
        for k, s in SERVERS.items()
    ]
    dur_key = context.user_data["custom"]["duration"]
    keyboard.append([InlineKeyboardButton("🔙 برگشت", callback_data=f"custom_dur_{dur_key}")])
    await query.edit_message_text(
        "🌍 سرور رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def custom_server_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    srv_key = query.data.split("_")[2]
    custom = context.user_data["custom"]
    custom["server"] = srv_key

    dur = DURATIONS[custom["duration"]]
    vol = VOLUMES[custom["volume"]]
    srv = SERVERS[srv_key]
    total = vol["price_1m"] if custom["duration"] == "1m" else vol["price_3m"]
    wallet = get_wallet(query.from_user.id)
    user_id = query.from_user.id

    # بررسی تخفیف رفرال (اولین خرید)
    referral_discount = 0
    if get_order_count(user_id) == 0 and get_referred_by(user_id):
        referral_discount = 15
        total = int(total * 0.85)

    context.user_data["selected_plan"] = f"{custom['duration']}_{custom['volume']}_{srv_key}"
    context.user_data["selected_price"] = total
    context.user_data["discount_percent"] = referral_discount
    context.user_data["discount_code"] = None

    keyboard = []
    if wallet >= total:
        keyboard.append([InlineKeyboardButton("💳 پرداخت از کیف پول", callback_data="pay_wallet_custom")])
    keyboard.append([InlineKeyboardButton("💵 پرداخت کارت به کارت", callback_data="pay_card_custom")])
    keyboard.append([InlineKeyboardButton("🏷️ کد تخفیف دارم", callback_data="discount_custom")])
    keyboard.append([InlineKeyboardButton("🔙 برگشت", callback_data=f"custom_vol_{custom['volume']}")])

    ref_text = f"\n🎁 تخفیف دعوت: {referral_discount}% اعمال شد!" if referral_discount else ""
    await query.edit_message_text(
        f"📋 خلاصه سفارش:\n\n"
        f"📅 مدت: {dur['name']}\n"
        f"📊 حجم: {vol['name']}\n"
        f"🌍 سرور: {srv['name']}\n"
        f"💰 قیمت نهایی: {total:,} تومان"
        f"{ref_text}\n"
        f"👛 موجودی: {wallet:,} تومان\n\n"
        "روش پرداخت رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ─────────────────────────────────────────
#  کد تخفیف
# ─────────────────────────────────────────
async def discount_custom_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🏷️ کد تخفیف خودت رو وارد کن:")
    return WAIT_DISCOUNT_CODE

async def receive_discount_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip().upper()
    user_id = update.effective_user.id
    percent, msg = check_discount_code(user_id, code)

    if percent is None:
        await update.message.reply_text(
            f"{msg}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت به خرید", callback_data="buy")]])
        )
        return ConversationHandler.END

    original_price = context.user_data.get("selected_price", 0)
    discounted_price = int(original_price * (1 - percent / 100))
    context.user_data["discount_percent"] = percent
    context.user_data["discount_code"] = code
    context.user_data["selected_price"] = discounted_price
    wallet = get_wallet(user_id)
    plan_key = context.user_data.get("selected_plan", "custom")

    keyboard = []
    if wallet >= discounted_price:
        keyboard.append([InlineKeyboardButton("💳 پرداخت از کیف پول", callback_data=f"pay_wallet_{plan_key}")])
    keyboard.append([InlineKeyboardButton("💵 پرداخت کارت به کارت", callback_data=f"pay_card_{plan_key}")])
    keyboard.append([InlineKeyboardButton("🔙 برگشت", callback_data="buy")])

    await update.message.reply_text(
        f"{msg}\n\n"
        f"💰 قیمت اصلی: {original_price:,} تومان\n"
        f"🏷️ تخفیف: {percent}%\n"
        f"✅ قیمت نهایی: {discounted_price:,} تومان\n\n"
        "روش پرداخت رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END

# ─────────────────────────────────────────
#  پرداخت
# ─────────────────────────────────────────
async def pay_card_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    price = context.user_data.get("selected_price", 0)
    plan_key = context.user_data.get("selected_plan", "custom")
    context.user_data["pending_plan"] = plan_key
    context.user_data["pending_type"] = "buy"
    context.user_data["pending_price"] = price

    await query.edit_message_text(
        f"💳 پرداخت کارت به کارت\n\n"
        f"مبلغ: {price:,} تومان\n"
        f"شماره کارت: `{CA