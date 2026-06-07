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
TEST_CONFIG = " موجود نیست ❌  "

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
        f"شماره کارت: `{CARD_NUMBER}`\n"
        f"به نام: {CARD_OWNER}\n\n"
        "بعد از واریز، عکس رسید رو اینجا بفرست 👇",
        parse_mode="Markdown"
    )
    return WAIT_RECEIPT

async def pay_wallet_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    price = context.user_data.get("selected_price", 0)
    plan_key = context.user_data.get("selected_plan", "custom")
    user_id = query.from_user.id
    wallet = get_wallet(user_id)

    if wallet < price:
        await query.answer("موجودی کافی نیست!", show_alert=True)
        return

    discount_code = context.user_data.get("discount_code")
    if discount_code:
        use_discount_code(user_id, discount_code)

    update_wallet(user_id, -price)
    oid = create_order(user_id, plan_key, price, "wallet")
    row = approve_order(oid)

    # پاداش رفرال
    referrer = get_referred_by(user_id)
    if referrer and row:
        reward = add_referral_reward(referrer, price)
        try:
            await context.bot.send_message(
                referrer,
                f"🎉 یکی از دعوت‌شدگان شما خرید کرد!\n"
                f"💰 {reward:,} تومان به کیف پول شما اضافه شد."
            )
        except:
            pass

    await context.bot.send_message(
        ADMIN_ID,
        f"✅ خرید از کیف پول\n"
        f"کاربر: {user_id} (@{query.from_user.username})\n"
        f"پلن: {plan_key}\n"
        f"مبلغ: {price:,} تومان\n"
        f"سفارش #{oid}\n\n"
        f"تأیید: /approve_{oid}"
    )
    await query.edit_message_text(
        f"✅ خرید موفق! 🎉\n\n"
        f"سفارش #{oid} ثبت شد.\n"
        f"کانفیگ شما به زودی ارسال می‌شه.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 منوی اصلی", callback_data="back_main")]])
    )

async def receive_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    pending_type = context.user_data.get("pending_type", "buy")

    if pending_type == "buy":
        plan_key = context.user_data.get("pending_plan", "")
        price = context.user_data.get("pending_price", 0)
        discount_code = context.user_data.get("discount_code", "")
        oid = create_order(user.id, plan_key, price, "receipt_sent")
        if discount_code:
            use_discount_code(user.id, discount_code)
        caption = (
            f"🧾 رسید جدید — سفارش #{oid}\n"
            f"کاربر: {user.id} (@{user.username})\n"
            f"پلن: {plan_key}\n"
            f"مبلغ: {price:,} تومان\n"
        )
        if discount_code:
            caption += f"کد تخفیف: {discount_code}\n"
        caption += f"\n✅ تأیید: /approve_{oid}\n❌ رد: /reject_{oid}"
    else:
        amount = context.user_data.get("topup_amount", 0)
        oid = create_order(user.id, "topup", amount, "receipt_sent")
        caption = (
            f"💰 شارژ کیف پول — #{oid}\n"
            f"کاربر: {user.id} (@{user.username})\n"
            f"مبلغ: {amount:,} تومان\n\n"
            f"✅ تأیید: /topup_approve_{oid}_{user.id}_{amount}\n"
            f"❌ رد: /reject_{oid}"
        )

    if update.message.photo:
        await context.bot.send_photo(ADMIN_ID, update.message.photo[-1].file_id, caption=caption)
    else:
        await context.bot.send_message(ADMIN_ID, "⚠️ رسید بدون عکس\n" + caption)

    await update.message.reply_text(
        "✅ رسیدت دریافت شد!\nبعد از بررسی (زیر ۳۰ دقیقه) کانفیگت ارسال می‌شه. 🙏",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 منوی اصلی", callback_data="back_main")]])
    )
    return ConversationHandler.END

# ═══════════════════════════════════════════
#  تست رایگان
# ═══════════════════════════════════════════
async def test_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await check_membership(update, context):
        return
    user_id = query.from_user.id
    if test_used(user_id):
        await query.edit_message_text(
            "❌ قبلاً از تست رایگان استفاده کردی!\n\nبرای خرید از منو اقدام کن 👇",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🛒 خرید VPN", callback_data="buy"),
                InlineKeyboardButton("🏠 منو", callback_data="back_main")
            ]])
        )
        return
    mark_test_used(user_id, TEST_CONFIG)
    await query.edit_message_text(
        f"🎁 کانفیگ تست 1 ساعته:\n\n`{TEST_CONFIG}`\n\n"
        "⚠️ این کانفیگ فقط 1 ساعت اعتبار دارد.\n\nبرای خرید پلن کامل 👇",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🛒 خرید VPN", callback_data="buy"),
            InlineKeyboardButton("🏠 منو", callback_data="back_main")
        ]])
    )

# ═══════════════════════════════════════════
#  افزایش موجودی
# ═══════════════════════════════════════════
async def topup_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await check_membership(update, context):
        return
    amounts = [50_000, 100_000, 200_000, 500_000]
    keyboard = [
        [InlineKeyboardButton(f"{a:,} تومان", callback_data=f"topup_amount_{a}")]
        for a in amounts
    ]
    keyboard.append([InlineKeyboardButton("🔙 برگشت", callback_data="back_main")])
    await query.edit_message_text(
        "💰 افزایش موجودی کیف پول\n\nمبلغ مورد نظر رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def topup_amount_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    amount = int(query.data.split("_")[2])
    context.user_data["topup_amount"] = amount
    context.user_data["pending_type"] = "topup"
    await query.edit_message_text(
        f"💳 شارژ کیف پول\n\n"
        f"مبلغ: {amount:,} تومان\n"
        f"شماره کارت: `{CARD_NUMBER}`\n"
        f"به نام: {CARD_OWNER}\n\n"
        "بعد از واریز، عکس رسید رو اینجا بفرست 👇",
        parse_mode="Markdown"
    )
    return WAIT_TOPUP_RECEIPT

# ═══════════════════════════════════════════
#  حساب کاربری
# ═══════════════════════════════════════════
async def account_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    wallet = get_wallet(user_id)
    used_test = "✅ استفاده شده" if test_used(user_id) else "🎁 استفاده نشده"
    orders = get_order_count(user_id)
    ref_count = get_referral_count(user_id)
    ref_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"

    await query.edit_message_text(
        f"👤 حساب کاربری\n\n"
        f"🆔 آیدی: {user_id}\n"
        f"💰 موجودی: {wallet:,} تومان\n"
        f"🛒 تعداد خرید: {orders}\n"
        f"🎁 تست رایگان: {used_test}\n"
        f"👥 دعوت‌شدگان: {ref_count} نفر\n\n"
        f"🔗 لینک دعوت:\n`{ref_link}`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💰 افزایش موجودی", callback_data="topup")],
            [InlineKeyboardButton("🏠 منوی اصلی",     callback_data="back_main")]
        ])
    )

# ═══════════════════════════════════════════
#  پشتیبانی
# ═══════════════════════════════════════════
async def support_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📞 پشتیبانی\n\nبرای ارتباط با پشتیبانی:\n👤 @Ali2011Ali2011_Ali",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 منوی اصلی", callback_data="back_main")]])
    )

async def back_main_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "یه گزینه انتخاب کن 👇",
        reply_markup=main_menu_keyboard()
    )

# ═══════════════════════════════════════════
#  پنل ادمین
# ═══════════════════════════════════════════
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    total_users, total_orders, total_income, pending_orders = get_stats()
    keyboard = [
        [InlineKeyboardButton("📊 آمار کامل",          callback_data="admin_stats")],
        [InlineKeyboardButton("📨 ارسال پیام همگانی",  callback_data="admin_broadcast")],
        [InlineKeyboardButton("💰 تغییر موجودی کاربر", callback_data="admin_wallet")],
        [InlineKeyboardButton("⏳ سفارشات در انتظار",  callback_data="admin_pending")],
    ]
    await update.message.reply_text(
        f"👑 پنل ادمین\n\n"
        f"👤 کل کاربران: {total_users}\n"
        f"🛒 کل سفارشات: {total_orders}\n"
        f"💰 کل درآمد: {total_income:,} تومان\n"
        f"⏳ سفارشات در انتظار: {pending_orders}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def admin_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        return
    total_users, total_orders, total_income, pending_orders = get_stats()
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM users WHERE test_used=1")
    test_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM referrals")
    ref_count = cur.fetchone()[0]
    con.close()

    await query.edit_message_text(
        f"📊 آمار کامل\n\n"
        f"👤 کل کاربران: {total_users}\n"
        f"🛒 سفارشات تأیید شده: {total_orders}\n"
        f"⏳ سفارشات در انتظار: {pending_orders}\n"
        f"💰 کل درآمد: {total_income:,} تومان\n"
        f"🎁 استفاده از تست: {test_count}\n"
        f"👥 کل رفرال‌ها: {ref_count}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="admin_back")]])
    )

async def admin_broadcast_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        return
    context.user_data["admin_action"] = "broadcast"
    await query.edit_message_text(
        "📨 پیام همگانی\n\nمتن پیام رو بفرست:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ انصراف", callback_data="admin_back")]])
    )
    return WAIT_BROADCAST

async def receive_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    text = update.message.text
    users = get_all_users()
    success = 0
    fail = 0
    for uid in users:
        try:
            await context.bot.send_message(uid, f"📢 پیام از طرف مدیریت:\n\n{text}")
            success += 1
        except:
            fail += 1
    await update.message.reply_text(
        f"✅ پیام همگانی ارسال شد!\n\n"
        f"موفق: {success}\nناموفق: {fail}"
    )
    return ConversationHandler.END

async def admin_wallet_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        return
    await query.edit_message_text(
        "💰 تغییر موجودی کاربر\n\nآیدی عددی کاربر رو بفرست:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ انصراف", callback_data="admin_back")]])
    )
    return WAIT_ADMIN_WALLET

async def receive_admin_wallet_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    try:
        uid = int(update.message.text.strip())
        context.user_data["admin_target_user"] = uid
        wallet = get_wallet(uid)
        await update.message.reply_text(
            f"کاربر {uid}\n💰 موجودی فعلی: {wallet:,} تومان\n\nمبلغ رو وارد کن (منفی برای کسر):"
        )
        return WAIT_ADMIN_WALLET_AMOUNT
    except:
        await update.message.reply_text("❌ آیدی نامعتبر!")
        return ConversationHandler.END

async def receive_admin_wallet_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    try:
        amount = int(update.message.text.strip())
        uid = context.user_data["admin_target_user"]
        update_wallet(uid, amount)
        new_wallet = get_wallet(uid)
        action = "اضافه" if amount > 0 else "کسر"
        await context.bot.send_message(
            uid,
            f"💰 موجودی کیف پول شما {action} شد.\nموجودی جدید: {new_wallet:,} تومان"
        )
        await update.message.reply_text(
            f"✅ {abs(amount):,} تومان {action} شد.\nموجودی جدید کاربر {uid}: {new_wallet:,} تومان"
        )
    except:
        await update.message.reply_text("❌ مبلغ نامعتبر!")
    return ConversationHandler.END

async def admin_pending_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        return
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT id, user_id, plan, amount FROM orders WHERE status='pending' ORDER BY id DESC LIMIT 10")
    rows = cur.fetchall()
    con.close()

    if not rows:
        await query.edit_message_text(
            "✅ هیچ سفارش در انتظاری نداری!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="admin_back")]])
        )
        return

    text = "⏳ سفارشات در انتظار:\n\n"
    for oid, uid, plan, amount in rows:
        text += f"#{oid} — کاربر {uid} — {plan} — {amount:,} تومان\n"
        text += f"✅ /approve_{oid}  ❌ /reject_{oid}\n\n"

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="admin_back")]])
    )

async def admin_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        return
    total_users, total_orders, total_income, pending_orders = get_stats()
    keyboard = [
        [InlineKeyboardButton("📊 آمار کامل",          callback_data="admin_stats")],
        [InlineKeyboardButton("📨 ارسال پیام همگانی",  callback_data="admin_broadcast")],
        [InlineKeyboardButton("💰 تغییر موجودی کاربر", callback_data="admin_wallet")],
        [InlineKeyboardButton("⏳ سفارشات در انتظار",  callback_data="admin_pending")],
    ]
    await query.edit_message_text(
        f"👑 پنل ادمین\n\n"
        f"👤 کل کاربران: {total_users}\n"
        f"🛒 کل سفارشات: {total_orders}\n"
        f"💰 کل درآمد: {total_income:,} تومان\n"
        f"⏳ سفارشات در انتظار: {pending_orders}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ═══════════════════════════════════════════
#  دستورات ادمین
# ═══════════════════════════════════════════
async def admin_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    oid = int(update.message.text.split("_")[1])
    row = approve_order(oid)

    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT user_id, plan, amount FROM orders WHERE id=?", (oid,))
    row = cur.fetchone()
    con.close()

    if row:
        user_id, plan_key, amount = row
        referrer = get_referred_by(user_id)
        if referrer:
            reward = add_referral_reward(referrer, amount)
            try:
                await context.bot.send_message(
                    referrer,
                    f"🎉 یکی از دعوت‌شدگان شما خرید کرد!\n"
                    f"💰 {reward:,} تومان به کیف پول شما اضافه شد."
                )
            except:
                pass

        await context.bot.send_message(
            user_id,
            f"✅ پرداخت تأیید شد! 🎉\n\n"
            f"پلن: {plan_key}\n"
            f"مبلغ: {amount:,} تومان\n\n"
            f"کانفیگ شما:\n`اینجا کانفیگ رو قرار بده`\n\n"
            f"شماره سفارش: #{oid}",
            parse_mode="Markdown"
        )
        await update.message.reply_text(f"✅ سفارش #{oid} تأیید شد.")

async def admin_topup_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    parts = update.message.text.split("_")
    oid, user_id, amount = int(parts[2]), int(parts[3]), int(parts[4])
    approve_order(oid)
    update_wallet(user_id, amount)
    await context.bot.send_message(
        user_id,
        f"✅ {amount:,} تومان به کیف پول شما اضافه شد 💰\nموجودی جدید: {get_wallet(user_id):,} تومان"
    )
    await update.message.reply_text(f"✅ {amount:,} تومان به کاربر {user_id} اضافه شد.")

async def admin_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    oid = int(update.message.text.split("_")[1])
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("UPDATE orders SET status='rejected' WHERE id=?", (oid,))
    cur.execute("SELECT user_id FROM orders WHERE id=?", (oid,))
    row = cur.fetchone()
    con.commit()
    con.close()
    if row:
        await context.bot.send_message(row[0], f"❌ رسید سفارش #{oid} تأیید نشد.\nبا پشتیبانی تماس بگیر.")
    await update.message.reply_text(f"❌ سفارش #{oid} رد شد.")

# ═══════════════════════════════════════════
#  راه‌اندازی
# ═══════════════════════════════════════════
def main():
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(pay_card_callback,        pattern="^pay_card_"),
            CallbackQueryHandler(topup_amount_callback,    pattern="^topup_amount_"),
            CallbackQueryHandler(discount_custom_callback, pattern="^discount_custom$"),
            CallbackQueryHandler(admin_broadcast_callback, pattern="^admin_broadcast$"),
            CallbackQueryHandler(admin_wallet_callback,    pattern="^admin_wallet$"),
        ],
        states={
            WAIT_RECEIPT:            [MessageHandler(filters.PHOTO | filters.TEXT & ~filters.COMMAND, receive_receipt)],
            WAIT_TOPUP_RECEIPT:      [MessageHandler(filters.PHOTO | filters.TEXT & ~filters.COMMAND, receive_receipt)],
            WAIT_DISCOUNT_CODE:      [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_discount_code)],
            WAIT_BROADCAST:          [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_broadcast)],
            WAIT_ADMIN_WALLET:       [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_admin_wallet_user)],
            WAIT_ADMIN_WALLET_AMOUNT:[MessageHandler(filters.TEXT & ~filters.COMMAND, receive_admin_wallet_amount)],
        },
        fallbacks=[CommandHandler("start", start)],
        per_message=False,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(check_join_callback,      pattern="^check_join$"))
    app.add_handler(CallbackQueryHandler(buy_callback,             pattern="^buy$"))
    app.add_handler(CallbackQueryHandler(custom_duration_callback, pattern="^custom_dur_"))
    app.add_handler(CallbackQueryHandler(custom_volume_callback,   pattern="^custom_vol_"))
    app.add_handler(CallbackQueryHandler(custom_server_callback,   pattern="^custom_srv_"))
    app.add_handler(CallbackQueryHandler(pay_wallet_callback,      pattern="^pay_wallet_"))
    app.add_handler(CallbackQueryHandler(test_callback,            pattern="^test$"))
    app.add_handler(CallbackQueryHandler(topup_callback,           pattern="^topup$"))
    app.add_handler(CallbackQueryHandler(referral_callback,        pattern="^referral$"))
    app.add_handler(CallbackQueryHandler(account_callback,         pattern="^account$"))
    app.add_handler(CallbackQueryHandler(support_callback,         pattern="^support$"))
    app.add_handler(CallbackQueryHandler(back_main_callback,       pattern="^back_main$"))
    app.add_handler(CallbackQueryHandler(admin_stats_callback,     pattern="^admin_stats$"))
    app.add_handler(CallbackQueryHandler(admin_pending_callback,   pattern="^admin_pending$"))
    app.add_handler(CallbackQueryHandler(admin_back_callback,      pattern="^admin_back$"))

    app.add_handler(MessageHandler(filters.Regex(r"^/approve_\d+$"),               admin_approve))
    app.add_handler(MessageHandler(filters.Regex(r"^/topup_approve_\d+_\d+_\d+$"), admin_topup_approve))
    app.add_handler(MessageHandler(filters.Regex(r"^/reject_\d+$"),                admin_reject))

    print("✅ بات در حال اجراست...")
    app.run_polling()

if __name__ == "__main__":
    main()
