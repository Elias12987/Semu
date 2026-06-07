import logging
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

# ─────────────────────────────────────────
#  تنظیمات
# ─────────────────────────────────────────
BOT_TOKEN   = "8925445808:AAGkJU3BX7f82SVG4YyvYHJALKro5xrZAhM"
CHANNEL_ID  = "@VPN_IRONMAN"
ADMIN_IDS   = [8471252047, 8523539535]  # آیدی دوم رو جایگزین کن
CARD_NUMBER = "6219-8619-2847-2389"
CARD_OWNER  = "ایران بوصیدی"
BOT_USERNAME = "your_bot_username"  # بدون @
SUPPORT_USERS = ["@Ali2011Ali2011_Ali", "@MARDAN_CORE"]

# ─────────────────────────────────────────
#  پلن‌ها
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

DISCOUNT_CODES = {
    "INYAS":  {"percent": 25, "first_only": False},
    "MARDAN": {"percent": 50, "first_only": True},
}

# States
WAIT_RECEIPT            = 1
WAIT_TOPUP_RECEIPT      = 2
WAIT_DISCOUNT_CODE      = 3
WAIT_BROADCAST          = 4
WAIT_ADMIN_WALLET       = 5
WAIT_ADMIN_WALLET_AMOUNT= 6
WAIT_PRIVATE_MSG_USER   = 7
WAIT_PRIVATE_MSG_TEXT   = 8

logging.basicConfig(level=logging.INFO)

def is_admin(user_id):
    return user_id in ADMIN_IDS

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
            cur.execute("INSERT INTO referrals (referrer_id, referred_id) VALUES (?,?)", (referred_by, user_id))
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
    cur.execute("UPDATE referrals SET reward = reward + ? WHERE referrer_id=? ORDER BY id DESC LIMIT 1", (reward, referrer_id))
    con.commit()
    con.close()
    return reward

def create_order(user_id, plan, amount, receipt):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("INSERT INTO orders (user_id, plan, amount, receipt) VALUES (?,?,?,?)", (user_id, plan, amount, receipt))
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
    return dc["percent"], "✅ کد تخفیف " + str(dc["percent"]) + "% اعمال شد!"

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

def get_user_orders(user_id):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT id, plan, amount, status, created_at FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10", (user_id,))
    rows = cur.fetchall()
    con.close()
    return rows

# ═══════════════════════════════════════════
#  بررسی عضویت کانال
# ═══════════════════════════════════════════
async def is_member(bot, user_id):
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ("member", "administrator", "creator")
    except:
        return False

async def check_membership(update, context):
    user_id = update.effective_user.id
    if not await is_member(context.bot, user_id):
        keyboard = [
            [InlineKeyboardButton("📢 عضویت در کانال", url="https://t.me/" + CHANNEL_ID.lstrip('@'))],
            [InlineKeyboardButton("✅ عضو شدم", callback_data="check_join")],
        ]
        msg = "⚠️ برای استفاده از بات باید عضو کانال ما بشی!\n\nکانال: " + CHANNEL_ID + "\n\nبعد از عضویت روی «عضو شدم» بزن."
        if update.message:
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.callback_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        return False
    return True

# ═══════════════════════════════════════════
#  منوی اصلی
# ═══════════════════════════════════════════
def main_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🛒 خرید VPN"), KeyboardButton("💰 افزایش موجودی")],
        [KeyboardButton("👥 دعوت از دوستان"), KeyboardButton("👤 حساب من")],
        [KeyboardButton("📋 اشتراک‌های من"), KeyboardButton("📞 پشتیبانی")],
    ], resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    referred_by = None
    if context.args:
        try:
            referred_by = int(context.args[0])
            if referred_by == user.id:
                referred_by = None
        except:
            pass

    is_new = ensure_user(user.id, user.username, referred_by)

    if not await check_membership(update, context):
        return

    if is_new and referred_by:
        try:
            await context.bot.send_message(referred_by,
                "🎉 یه نفر با لینک دعوت شما وارد شد!\nوقتی اولین خریدش رو انجام بده، ۱۰٪ به کیف پول شما اضافه میشه.")
        except:
            pass

    await update.message.reply_text(
        "سلام " + user.first_name + " 👋\n\nبه بات فروش VPN خوش اومدی 🔒\nیه گزینه انتخاب کن:",
        reply_markup=main_menu()
    )

async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    if await is_member(context.bot, user.id):
        ensure_user(user.id, user.username)
        await query.edit_message_text(
            "✅ عضویتت تأیید شد!\n\nسلام " + user.first_name + " 👋\nیه گزینه انتخاب کن:"
        )
        await context.bot.send_message(user.id, "منوی اصلی 👇", reply_markup=main_menu())
    else:
        await query.answer("هنوز عضو نشدی! 😕", show_alert=True)

# ═══════════════════════════════════════════
#  هندلر دکمه‌های کیبورد
# ═══════════════════════════════════════════
async def keyboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if text == "🛒 خرید VPN":
        if not await check_membership(update, context):
            return
        context.user_data["custom"] = {}
        keyboard = [[InlineKeyboardButton(d["name"], callback_data="custom_dur_" + k)] for k, d in DURATIONS.items()]
        await update.message.reply_text("🛒 خرید VPN\n\n📅 مدت زمان رو انتخاب کن:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif text == "💰 افزایش موجودی":
        if not await check_membership(update, context):
            return
        amounts = [50_000, 100_000, 200_000, 500_000]
        keyboard = [[InlineKeyboardButton(str(a // 1000) + "،۰۰۰ تومان", callback_data="topup_amount_" + str(a))] for a in amounts]
        await update.message.reply_text("💰 افزایش موجودی\n\nمبلغ رو انتخاب کن:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif text == "👥 دعوت از دوستان":
        ref_link = "https://t.me/" + BOT_USERNAME + "?start=" + str(user_id)
        count = get_referral_count(user_id)
        earnings = get_referral_earnings(user_id)
        await update.message.reply_text(
            "👥 سیستم دعوت از دوستان\n\n"
            "🔗 لینک دعوت شما:\n`" + ref_link + "`\n\n"
            "👤 تعداد دعوت‌شدگان: " + str(count) + " نفر\n"
            "💰 درآمد از رفرال: " + str(earnings) + " تومان\n\n"
            "📌 قوانین:\n• دعوت‌شونده ۱۵٪ تخفیف اولین خرید\n• شما ۱۰٪ از هر خرید دعوت‌شونده",
            parse_mode="Markdown"
        )

    elif text == "👤 حساب من":
        wallet = get_wallet(user_id)
        orders = get_order_count(user_id)
        ref_count = get_referral_count(user_id)
        ref_link = "https://t.me/" + BOT_USERNAME + "?start=" + str(user_id)
        await update.message.reply_text(
            "👤 حساب کاربری\n\n"
            "🆔 آیدی: " + str(user_id) + "\n"
            "💰 موجودی: " + str(wallet) + " تومان\n"
            "🛒 تعداد خرید: " + str(orders) + "\n"
            "👥 دعوت‌شدگان: " + str(ref_count) + " نفر\n\n"
            "🔗 لینک دعوت:\n`" + ref_link + "`",
            parse_mode="Markdown"
        )

    elif text == "📋 اشتراک‌های من":
        rows = get_user_orders(user_id)
        if not rows:
            await update.message.reply_text("❌ هیچ اشتراکی نداری!\n\nبرای خرید از منو اقدام کن 👇")
            return
        msg = "📋 اشتراک‌های شما:\n\n"
        status_map = {"approved": "✅ فعال", "pending": "⏳ در انتظار", "rejected": "❌ رد شده"}
        for oid, plan, amount, status, created in rows:
            msg += "سفارش #" + str(oid) + "\n"
            msg += "📦 پلن: " + str(plan) + "\n"
            msg += "💰 مبلغ: " + str(amount) + " تومان\n"
            msg += "وضعیت: " + status_map.get(status, status) + "\n"
            msg += "📅 تاریخ: " + created[:10] + "\n\n"
        await update.message.reply_text(msg)

    elif text == "📞 پشتیبانی":
        support_text = "📞 پشتیبانی\n\nبرای ارتباط با پشتیبانی:\n"
        for s in SUPPORT_USERS:
            support_text += "👤 " + s + "\n"
        await update.message.reply_text(support_text)

# ═══════════════════════════════════════════
#  خرید VPN
# ═══════════════════════════════════════════
async def custom_duration_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    dur_key = query.data.split("_")[2]
    if "custom" not in context.user_data:
        context.user_data["custom"] = {}
    context.user_data["custom"]["duration"] = dur_key
    keyboard = []
    for k, v in VOLUMES.items():
        price = v["price_1m"] if dur_key == "1m" else v["price_3m"]
        keyboard.append([InlineKeyboardButton(v["name"] + " — " + str(price) + " تومان", callback_data="custom_vol_" + k)])
    keyboard.append([InlineKeyboardButton("🔙 برگشت", callback_data="back_main")])
    await query.edit_message_text("📅 مدت: " + DURATIONS[dur_key]["name"] + "\n\n📊 حجم رو انتخاب کن:", reply_markup=InlineKeyboardMarkup(keyboard))

async def custom_volume_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    vol_key = query.data.split("_")[2]
    context.user_data["custom"]["volume"] = vol_key
    keyboard = [[InlineKeyboardButton(s["name"], callback_data="custom_srv_" + k)] for k, s in SERVERS.items()]
    keyboard.append([InlineKeyboardButton("🔙 برگشت", callback_data="back_buy")])
    await query.edit_message_text("🌍 سرور رو انتخاب کن:", reply_markup=InlineKeyboardMarkup(keyboard))

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

    referral_discount = 0
    if get_order_count(user_id) == 0 and get_referred_by(user_id):
        referral_discount = 15
        total = int(total * 0.85)

    context.user_data["selected_plan"] = custom["duration"] + "_" + custom["volume"] + "_" + srv_key
    context.user_data["selected_price"] = total
    context.user_data["discount_code"] = None

    keyboard = []
    if wallet >= total:
        keyboard.append([InlineKeyboardButton("💳 پرداخت از کیف پول", callback_data="pay_wallet")])
    keyboard.append([InlineKeyboardButton("💵 پرداخت کارت به کارت", callback_data="pay_card")])
    keyboard.append([InlineKeyboardButton("🏷️ کد تخفیف دارم", callback_data="discount_code")])
    keyboard.append([InlineKeyboardButton("🔙 برگشت", callback_data="back_main")])

    ref_text = "\n🎁 تخفیف دعوت ۱۵% اعمال شد!" if referral_discount else ""
    await query.edit_message_text(
        "📋 خلاصه سفارش:\n\n"
        "📅 مدت: " + dur["name"] + "\n"
        "📊 حجم: " + vol["name"] + "\n"
        "🌍 سرور: " + srv["name"] + "\n"
        "💰 قیمت نهایی: " + str(total) + " تومان" + ref_text + "\n"
        "👛 موجودی: " + str(wallet) + " تومان\n\n"
        "روش پرداخت رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def discount_code_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🏷️ کد تخفیف خودت رو وارد کن:")
    return WAIT_DISCOUNT_CODE

async def receive_discount_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip().upper()
    user_id = update.effective_user.id
    percent, msg = check_discount_code(user_id, code)
    if percent is None:
        await update.message.reply_text(msg, reply_markup=main_menu())
        return ConversationHandler.END
    original = context.user_data.get("selected_price", 0)
    discounted = int(original * (1 - percent / 100))
    context.user_data["discount_code"] = code
    context.user_data["selected_price"] = discounted
    wallet = get_wallet(user_id)
    keyboard = []
    if wallet >= discounted:
        keyboard.append([InlineKeyboardButton("💳 پرداخت از کیف پول", callback_data="pay_wallet")])
    keyboard.append([InlineKeyboardButton("💵 پرداخت کارت به کارت", callback_data="pay_card")])
    await update.message.reply_text(
        msg + "\n\n"
        "💰 قیمت اصلی: " + str(original) + " تومان\n"
        "✅ قیمت نهایی: " + str(discounted) + " تومان\n\n"
        "روش پرداخت:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END

async def pay_card_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    price = context.user_data.get("selected_price", 0)
    context.user_data["pending_type"] = "buy"
    context.user_data["pending_price"] = price
    await query.edit_message_text(
        "💳 پرداخت کارت به کارت\n\n"
        "مبلغ: " + str(price) + " تومان\n"
        "شماره کارت: `" + CARD_NUMBER + "`\n"
        "به نام: " + CARD_OWNER + "\n\n"
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
    approve_order(oid)
    referrer = get_referred_by(user_id)
    if referrer:
        reward = add_referral_reward(referrer, price)
        try:
            await context.bot.send_message(referrer, "🎉 یکی از دعوت‌شدگان شما خرید کرد!\n💰 " + str(reward) + " تومان به کیف پول شما اضافه شد.")
        except:
            pass
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(admin_id,
                "✅ خرید از کیف پول\nکاربر: " + str(user_id) + " (@" + str(query.from_user.username) + ")\n"
                "پلن: " + plan_key + "\nمبلغ: " + str(price) + " تومان\nسفارش #" + str(oid))
        except:
            pass
    await query.edit_message_text(
        "✅ خرید موفق! 🎉\n\nسفارش #" + str(oid) + " ثبت شد.\nکانفیگ شما به زودی ارسال می‌شه."
    )

async def receive_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    pending_type = context.user_data.get("pending_type", "buy")
    if pending_type == "buy":
        plan_key = context.user_data.get("selected_plan", "")
        price = context.user_data.get("pending_price", 0)
        discount_code = context.user_data.get("discount_code", "")
        oid = create_order(user.id, plan_key, price, "receipt_sent")
        if discount_code:
            use_discount_code(user.id, discount_code)
        caption = (
            "🧾 رسید جدید — سفارش #" + str(oid) + "\n"
            "کاربر: " + str(user.id) + " (@" + str(user.username) + ")\n"
            "پلن: " + plan_key + "\n"
            "مبلغ: " + str(price) + " تومان\n"
        )
        if discount_code:
            caption += "کد تخفیف: " + discount_code + "\n"
        caption += "\n✅ تأیید: /approve_" + str(oid) + "\n❌ رد: /reject_" + str(oid)
    else:
        amount = context.user_data.get("topup_amount", 0)
        oid = create_order(user.id, "topup", amount, "receipt_sent")
        caption = (
            "💰 شارژ کیف پول — #" + str(oid) + "\n"
            "کاربر: " + str(user.id) + " (@" + str(user.username) + ")\n"
            "مبلغ: " + str(amount) + " تومان\n\n"
            "✅ تأیید: /topup_approve_" + str(oid) + "_" + str(user.id) + "_" + str(amount) + "\n"
            "❌ رد: /reject_" + str(oid)
        )

    for admin_id in ADMIN_IDS:
        try:
            if update.message.photo:
                await context.bot.send_photo(admin_id, update.message.photo[-1].file_id, caption=caption)
            else:
                await context.bot.send_message(admin_id, "⚠️ رسید بدون عکس\n" + caption)
        except:
            pass

    await update.message.reply_text(
        "✅ رسیدت دریافت شد!\nبعد از بررسی (زیر ۳۰ دقیقه) کانفیگت ارسال می‌شه. 🙏",
        reply_markup=main_menu()
    )
    return ConversationHandler.END

# ═══════════════════════════════════════════
#  افزایش موجودی
# ═══════════════════════════════════════════
async def topup_amount_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    amount = int(query.data.split("_")[2])
    context.user_data["topup_amount"] = amount
    context.user_data["pending_type"] = "topup"
    await query.edit_message_text(
        "💳 شارژ کیف پول\n\n"
        "مبلغ: " + str(amount) + " تومان\n"
        "شماره کارت: `" + CARD_NUMBER + "`\n"
        "به نام: " + CARD_OWNER + "\n\n"
        "بعد از واریز، عکس رسید رو اینجا بفرست 👇",
        parse_mode="Markdown"
    )
    return WAIT_TOPUP_RECEIPT

# ═══════════════════════════════════════════
#  برگشت به منو
# ═══════════════════════════════════════════
async def back_main_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✅")
    await context.bot.send_message(query.from_user.id, "منوی اصلی 👇", reply_markup=main_menu())

async def back_buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    dur_key = context.user_data.get("custom", {}).get("duration", "1m")
    keyboard = []
    for k, v in VOLUMES.items():
        price = v["price_1m"] if dur_key == "1m" else v["price_3m"]
        keyboard.append([InlineKeyboardButton(v["name"] + " — " + str(price) + " تومان", callback_data="custom_vol_" + k)])
    keyboard.append([InlineKeyboardButton("🔙 برگشت", callback_data="back_main")])
    await query.edit_message_text("📊 حجم رو انتخاب کن:", reply_markup=InlineKeyboardMarkup(keyboard))

# ═══════════════════════════════════════════
#  پنل ادمین
# ═══════════════════════════════════════════
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    total_users, total_orders, total_income, pending_orders = get_stats()
    keyboard = [
        [InlineKeyboardButton("📊 آمار کامل", callback_data="admin_stats")],
        [InlineKeyboardButton("📨 پیام همگانی", callback_data="admin_broadcast")],
        [InlineKeyboardButton("💬 پیام شخصی", callback_data="admin_private_msg")],
        [InlineKeyboardButton("💰 تغییر موجودی", callback_data="admin_wallet")],
        [InlineKeyboardButton("⏳ سفارشات در انتظار", callback_data="admin_pending")],
    ]
    await update.message.reply_text(
        "👑 پنل ادمین\n\n"
        "👤 کل کاربران: " + str(total_users) + "\n"
        "🛒 کل سفارشات: " + str(total_orders) + "\n"
        "💰 کل درآمد: " + str(total_income) + " تومان\n"
        "⏳ در انتظار: " + str(pending_orders),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def admin_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
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
        "📊 آمار کامل\n\n"
        "👤 کل کاربران: " + str(total_users) + "\n"
        "🛒 سفارشات تأیید شده: " + str(total_orders) + "\n"
        "⏳ سفارشات در انتظار: " + str(pending_orders) + "\n"
        "💰 کل درآمد: " + str(total_income) + " تومان\n"
        "🎁 استفاده از تست: " + str(test_count) + "\n"
        "👥 کل رفرال‌ها: " + str(ref_count),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="admin_back")]])
    )

async def admin_broadcast_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    await query.edit_message_text(
        "📨 پیام همگانی\n\nمتن پیام رو بفرست:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ انصراف", callback_data="admin_back")]])
    )
    return WAIT_BROADCAST

async def receive_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    text = update.message.text
    users = get_all_users()
    success = 0
    fail = 0
    for uid in users:
        try:
            await context.bot.send_message(uid, "📢 پیام از طرف مدیریت:\n\n" + text)
            success += 1
        except:
            fail += 1
    await update.message.reply_text("✅ پیام همگانی ارسال شد!\n\nموفق: " + str(success) + "\nناموفق: " + str(fail))
    return ConversationHandler.END

async def admin_private_msg_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    await query.edit_message_text(
        "💬 پیام شخصی\n\nآیدی عددی کاربر رو بفرست:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ انصراف", callback_data="admin_back")]])
    )
    return WAIT_PRIVATE_MSG_USER

async def receive_private_msg_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    try:
        uid = int(update.message.text.strip())
        context.user_data["private_msg_target"] = uid
        await update.message.reply_text("متن پیام رو بفرست:")
        return WAIT_PRIVATE_MSG_TEXT
    except:
        await update.message.reply_text("❌ آیدی نامعتبر!")
        return ConversationHandler.END

async def receive_private_msg_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    uid = context.user_data.get("private_msg_target")
    text = update.message.text
    try:
        await context.bot.send_message(uid, "📩 پیام از طرف مدیریت:\n\n" + text)
        await update.message.reply_text("✅ پیام به کاربر " + str(uid) + " ارسال شد.")
    except:
        await update.message.reply_text("❌ ارسال پیام ناموفق! کاربر بات رو بلاک کرده.")
    return ConversationHandler.END

async def admin_wallet_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    await query.edit_message_text(
        "💰 تغییر موجودی\n\nآیدی عددی کاربر رو بفرست:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ انصراف", callback_data="admin_back")]])
    )
    return WAIT_ADMIN_WALLET

async def receive_admin_wallet_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    try:
        uid = int(update.message.text.strip())
        context.user_data["admin_target_user"] = uid
        wallet = get_wallet(uid)
        await update.message.reply_text("کاربر " + str(uid) + "\n💰 موجودی فعلی: " + str(wallet) + " تومان\n\nمبلغ رو وارد کن (منفی برای کسر):")
        return WAIT_ADMIN_WALLET_AMOUNT
    except:
        await update.message.reply_text("❌ آیدی نامعتبر!")
        return ConversationHandler.END

async def receive_admin_wallet_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    try:
        amount = int(update.message.text.strip())
        uid = context.user_data["admin_target_user"]
        update_wallet(uid, amount)
        new_wallet = get_wallet(uid)
        action = "اضافه" if amount > 0 else "کسر"
        try:
            await context.bot.send_message(uid, "💰 موجودی کیف پول شما " + action + " شد.\nموجودی جدید: " + str(new_wallet) + " تومان")
        except:
            pass
        await update.message.reply_text("✅ " + str(abs(amount)) + " تومان " + action + " شد.\nموجودی جدید کاربر " + str(uid) + ": " + str(new_wallet) + " تومان")
    except:
        await update.message.reply_text("❌ مبلغ نامعتبر!")
    return ConversationHandler.END

async def admin_pending_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT id, user_id, plan, amount FROM orders WHERE status='pending' ORDER BY id DESC LIMIT 10")
    rows = cur.fetchall()
    con.close()
    if not rows:
        await query.edit_message_text("✅ هیچ سفارش در انتظاری نداری!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="admin_back")]]))
        return
    text = "⏳ سفارشات در انتظار:\n\n"
    for oid, uid, plan, amount in rows:
        text += "#" + str(oid) + " — کاربر " + str(uid) + " — " + str(plan) + " — " + str(amount) + " تومان\n"
        text += "✅ /approve_" + str(oid) + "  ❌ /reject_" + str(oid) + "\n\n"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="admin_back")]]))

async def admin_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    total_users, total_orders, total_income, pending_orders = get_stats()
    keyboard = [
        [InlineKeyboardButton("📊 آمار کامل", callback_data="admin_stats")],
        [InlineKeyboardButton("📨 پیام همگانی", callback_data="admin_broadcast")],
        [InlineKeyboardButton("💬 پیام شخصی", callback_data="admin_private_msg")],
        [InlineKeyboardButton("💰 تغییر موجودی", callback_data="admin_wallet")],
        [InlineKeyboardButton("⏳ سفارشات در انتظار", callback_data="admin_pending")],
    ]
    await query.edit_message_text(
        "👑 پنل ادمین\n\n"
        "👤 کل کاربران: " + str(total_users) + "\n"
        "🛒 کل سفارشات: " + str(total_orders) + "\n"
        "💰 کل درآمد: " + str(total_income) + " تومان\n"
        "⏳ در انتظار: " + str(pending_orders),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ═══════════════════════════════════════════
#  دستورات ادمین
# ═══════════════════════════════════════════
async def admin_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
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
                await context.bot.send_message(referrer, "🎉 یکی از دعوت‌شدگان شما خرید کرد!\n💰 " + str(reward) + " تومان به کیف پول شما اضافه شد.")
            except:
                pass
        try:
            await context.bot.send_message(user_id,
                "✅ پرداخت تأیید شد! 🎉\n\n"
                "پلن: " + str(plan_key) + "\n"
                "مبلغ: " + str(amount) + " تومان\n\n"
                "کانفیگ شما:\n`اینجا کانفیگ رو قرار بده`\n\n"
                "شماره سفارش: #" + str(oid),
                parse_mode="Markdown"
            )
        except:
            pass
        await update.message.reply_text("✅ سفارش #" + str(oid) + " تأیید شد و کاربر " + str(user_id) + " مطلع شد.")

async def admin_topup_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    parts = update.message.text.split("_")
    oid, user_id, amount = int(parts[2]), int(parts[3]), int(parts[4])
    approve_order(oid)
    update_wallet(user_id, amount)
    try:
        await context.bot.send_message(user_id, "✅ " + str(amount) + " تومان به کیف پول شما اضافه شد 💰\nموجودی جدید: " + str(get_wallet(user_id)) + " تومان")
    except:
        pass
    await update.message.reply_text("✅ " + str(amount) + " تومان به کاربر " + str(user_id) + " اضافه شد.")

async def admin_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
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
        try:
            await context.bot.send_message(row[0], "❌ رسید سفارش #" + str(oid) + " تأیید نشد.\nبا پشتیبانی تماس بگیر.")
        except:
            pass
    await update.message.reply_text("❌ سفارش #" + str(oid) + " رد شد.")

# ═══════════════════════════════════════════
#  راه‌اندازی
# ═══════════════════════════════════════════
def main():
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(pay_card_callback,             pattern="^pay_card$"),
            CallbackQueryHandler(topup_amount_callback,         pattern="^topup_amount_"),
            CallbackQueryHandler(discount_code_callback,        pattern="^discount_code$"),
            CallbackQueryHandler(admin_broadcast_callback,      pattern="^admin_broadcast$"),
            CallbackQueryHandler(admin_wallet_callback,         pattern="^admin_wallet$"),
            CallbackQueryHandler(admin_private_msg_callback,    pattern="^admin_private_msg$"),
        ],
        states={
            WAIT_RECEIPT:             [MessageHandler(filters.PHOTO | filters.TEXT & ~filters.COMMAND, receive_receipt)],
            WAIT_TOPUP_RECEIPT:       [MessageHandler(filters.PHOTO | filters.TEXT & ~filters.COMMAND, receive_receipt)],
            WAIT_DISCOUNT_CODE:       [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_discount_code)],
            WAIT_BROADCAST:           [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_broadcast)],
            WAIT_ADMIN_WALLET:        [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_admin_wallet_user)],
            WAIT_ADMIN_WALLET_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_admin_wallet_amount)],
            WAIT_PRIVATE_MSG_USER:    [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_private_msg_user)],
            WAIT_PRIVATE_MSG_TEXT:    [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_private_msg_text)],
        },
        fallbacks=[CommandHandler("start", start)],
        per_message=False,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(check_join_callback,       pattern="^check_join$"))
    app.add_handler(CallbackQueryHandler(custom_duration_callback,  pattern="^custom_dur_"))
    app.add_handler(CallbackQueryHandler(custom_volume_callback,    pattern="^custom_vol_"))
    app.add_handler(CallbackQueryHandler(custom_server_callback,    pattern="^custom_srv_"))
    app.add_handler(CallbackQueryHandler(pay_wallet_callback,       pattern="^pay_wallet$"))
    app.add_handler(CallbackQueryHandler(back_main_callback,        pattern="^back_main$"))
    app.add_handler(CallbackQueryHandler(back_buy_callback,         pattern="^back_buy$"))
    app.add_handler(CallbackQueryHandler(admin_stats_callback,      pattern="^admin_stats$"))
    app.add_handler(CallbackQueryHandler(admin_pending_callback,    pattern="^admin_pending$"))
    app.add_handler(CallbackQueryHandler(admin_back_callback,       pattern="^admin_back$"))

    KEYBOARD_BUTTONS = "^(🛒 خرید VPN|💰 افزایش موجودی|👥 دعوت از دوستان|👤 حساب من|📋 اشتراک‌های من|📞 پشتیبانی)$"
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(KEYBOARD_BUTTONS), keyboard_handler))
    app.add_handler(MessageHandler(filters.Regex(r"^/approve_\d+$"),               admin_approve))
    app.add_handler(MessageHandler(filters.Regex(r"^/topup_approve_\d+_\d+_\d+$"), admin_topup_approve))
    app.add_handler(MessageHandler(filters.Regex(r"^/reject_\d+$"),                admin_reject))

    print("✅ بات در حال اجراست...")
    app.run_polling()

if __name__ == "__main__":
    main()
