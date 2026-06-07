import logging
import sqlite3
import random
import string
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler,
    JobQueue
)

BOT_TOKEN    = "8925445808:AAGkJU3BX7f82SVG4YyvYHJALKro5xrZAhM"
CHANNEL_ID   = "@VPN_IRONMAN"
ADMIN_IDS    = [8471252047, 1111111111]
CARD_NUMBER  = "6219-8619-2847-2389"
CARD_OWNER   = "ایران بوصیدی"
BOT_USERNAME = "your_bot_username"
SUPPORT_USERS = ["@Ali2011Ali2011_Ali", "@MARDAN_CORE"]

DURATIONS = {
    "1m": {"name": "1 ماهه", "months": 1},
    "3m": {"name": "3 ماهه", "months": 3},
}

VOLUMES = {
    "1gb":       {"name": "1GB",       "gb": 1,   "price_1m": 10000,  "price_3m": 15000},
    "5gb":       {"name": "5GB",       "gb": 5,   "price_1m": 50000,  "price_3m": 75000},
    "100gb":     {"name": "100GB",     "gb": 100, "price_1m": 100000, "price_3m": 150000},
    "200gb":     {"name": "200GB",     "gb": 200, "price_1m": 200000, "price_3m": 300000},
    "unlimited": {"name": "Unlimited", "gb": -1,  "price_1m": 500000, "price_3m": 750000},
}

SERVERS = {"de": {"name": "Germany"}}

DISCOUNT_CODES = {
    "INYAS":  {"percent": 25, "first_only": False},
    "MARDAN": {"percent": 100, "first_only": True},
}

WHEEL1_PRIZES = [
    {"name": "20% تخفیف 🎉",  "type": "discount", "value": 20},
    {"name": "10% تخفیف 🎁",  "type": "discount", "value": 10},
    {"name": "50% تخفیف 🔥",  "type": "discount", "value": 50},
    {"name": "30% تخفیف ✨",  "type": "discount", "value": 30},
    {"name": "500MB یک روزه", "type": "config",   "value": "500mb_1d"},
    {"name": "پوچ 😅",        "type": "none",     "value": 0},
]

WHEEL2_PRIZES = [
    {"name": "1GB پنج روزه",   "type": "config", "value": "1gb_5d"},
    {"name": "500MB یک روزه",  "type": "config", "value": "500mb_1d"},
    {"name": "2GB دو ساعته",   "type": "config", "value": "2gb_2h"},
    {"name": "5GB پنج روزه",   "type": "config", "value": "5gb_5d"},
    {"name": "پوچ 😅",         "type": "none",   "value": 0},
]

WAIT_RECEIPT             = 1
WAIT_TOPUP_RECEIPT       = 2
WAIT_DISCOUNT_CODE       = 3
WAIT_BROADCAST           = 4
WAIT_ADMIN_WALLET        = 5
WAIT_ADMIN_WALLET_AMOUNT = 6
WAIT_PRIVATE_MSG_USER    = 7
WAIT_PRIVATE_MSG_TEXT    = 8
WAIT_TICKET              = 9
WAIT_TICKET_REPLY_ID     = 10
WAIT_TICKET_REPLY_TEXT   = 11

logging.basicConfig(level=logging.INFO)

def is_admin(user_id):
    return user_id in ADMIN_IDS

def back_btn():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="back_main")]])

def fmt(n):
    try:
        return "{:,}".format(int(n))
    except:
        return str(n)

def init_db():
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id      INTEGER PRIMARY KEY,
            username     TEXT,
            wallet       INTEGER DEFAULT 0,
            order_count  INTEGER DEFAULT 0,
            points       INTEGER DEFAULT 0,
            referred_by  INTEGER DEFAULT NULL,
            last_wheel1  TEXT DEFAULT NULL,
            created_at   TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS orders (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER,
            plan         TEXT,
            amount       INTEGER,
            volume_gb    REAL DEFAULT 0,
            used_gb      REAL DEFAULT 0,
            status       TEXT DEFAULT 'pending',
            receipt      TEXT,
            expire_at    TEXT DEFAULT NULL,
            created_at   TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS discount_usage (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id  INTEGER,
            code     TEXT,
            used_at  TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS referrals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER,
            referred_id INTEGER,
            reward      INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS tickets (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            subject     TEXT,
            message     TEXT,
            status      TEXT DEFAULT 'open',
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS wheel_codes (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            code      TEXT UNIQUE,
            prize     TEXT,
            used      INTEGER DEFAULT 0,
            user_id   INTEGER DEFAULT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS notifications (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            notif_5d INTEGER DEFAULT 0,
            notif_3d INTEGER DEFAULT 0,
            notif_1d INTEGER DEFAULT 0,
            notif_1h INTEGER DEFAULT 0,
            notif_exp INTEGER DEFAULT 0
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
        cur.execute("INSERT INTO users (user_id, username, referred_by) VALUES (?,?,?)", (user_id, username, referred_by))
        if referred_by:
            cur.execute("INSERT INTO referrals (referrer_id, referred_id) VALUES (?,?)", (referred_by, user_id))
    con.commit()
    con.close()
    return not exists

def get_user(user_id):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    con.close()
    return row

def get_wallet(user_id):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT wallet FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    con.close()
    return row[0] if row else 0

def get_points(user_id):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT points FROM users WHERE user_id=?", (user_id,))
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

def get_max_purchase_gb(user_id):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT MAX(volume_gb) FROM orders WHERE user_id=? AND status='approved'", (user_id,))
    row = cur.fetchone()
    con.close()
    return row[0] or 0

def update_wallet(user_id, amount):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("UPDATE users SET wallet = wallet + ? WHERE user_id=?", (amount, user_id))
    con.commit()
    con.close()

def add_points(user_id, amount):
    points = max(1, int(amount / 10000))
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("UPDATE users SET points = points + ? WHERE user_id=?", (points, user_id))
    con.commit()
    con.close()
    return points

def deduct_points(user_id, points):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("UPDATE users SET points = points - ? WHERE user_id=?", (points, user_id))
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

def create_order(user_id, plan, amount, receipt, volume_gb=0, expire_at=None):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute(
        "INSERT INTO orders (user_id, plan, amount, volume_gb, expire_at, receipt) VALUES (?,?,?,?,?,?)",
        (user_id, plan, amount, volume_gb, expire_at, receipt)
    )
    oid = cur.lastrowid
    cur.execute("INSERT INTO notifications (order_id) VALUES (?)", (oid,))
    con.commit()
    con.close()
    return oid

def approve_order(order_id, volume_gb=0, expire_at=None):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    if expire_at:
        cur.execute("UPDATE orders SET status='approved', volume_gb=?, expire_at=? WHERE id=?", (volume_gb, expire_at, order_id))
    else:
        cur.execute("UPDATE orders SET status='approved' WHERE id=?", (order_id,))
    cur.execute("SELECT user_id, amount FROM orders WHERE id=?", (order_id,))
    row = cur.fetchone()
    if row:
        cur.execute("UPDATE users SET order_count = order_count + 1 WHERE user_id=?", (row[0],))
    con.commit()
    con.close()
    return row

def get_user_orders(user_id):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT id, plan, amount, volume_gb, used_gb, status, expire_at, created_at FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10", (user_id,))
    rows = cur.fetchall()
    con.close()
    return rows

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

def check_discount_code(user_id, code):
    code = code.upper().strip()
    if code not in DISCOUNT_CODES:
        con = sqlite3.connect("vpn_bot.db")
        cur = con.cursor()
        cur.execute("SELECT prize, used FROM wheel_codes WHERE code=?", (code,))
        row = cur.fetchone()
        con.close()
        if row and row[1] == 0:
            return row[0], "✅ کد گردونه معتبر است!"
        return None, "❌ کد تخفیف نامعتبر است!"
    dc = DISCOUNT_CODES[code]
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT id FROM discount_usage WHERE user_id=? AND code=?", (user_id, code))
    used = cur.fetchone()
    con.close()
    if used:
        return None, "❌ این کد قبلا استفاده شده!"
    if dc["first_only"] and get_order_count(user_id) > 0:
        return None, "❌ این کد فقط برای اولین خرید است!"
    return dc["percent"], "✅ تخفیف " + str(dc["percent"]) + "% اعمال شد!"

def use_discount_code(user_id, code):
    code = code.upper()
    if code in DISCOUNT_CODES:
        con = sqlite3.connect("vpn_bot.db")
        cur = con.cursor()
        cur.execute("INSERT INTO discount_usage (user_id, code) VALUES (?,?)", (user_id, code))
        con.commit()
        con.close()
    else:
        con = sqlite3.connect("vpn_bot.db")
        cur = con.cursor()
        cur.execute("UPDATE wheel_codes SET used=1, user_id=? WHERE code=?", (user_id, code))
        con.commit()
        con.close()

def generate_wheel_code(prize_name):
    code = "WHEEL-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("INSERT INTO wheel_codes (code, prize) VALUES (?,?)", (code, prize_name))
    con.commit()
    con.close()
    return code

def can_spin_wheel1(user_id):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT last_wheel1 FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    con.close()
    if not row or not row[0]:
        return True
    last = datetime.fromisoformat(row[0])
    return datetime.now().date() > last.date()

def update_wheel1_time(user_id):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("UPDATE users SET last_wheel1=? WHERE user_id=?", (datetime.now().isoformat(), user_id))
    con.commit()
    con.close()

def create_ticket(user_id, subject, message):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("INSERT INTO tickets (user_id, subject, message) VALUES (?,?,?)", (user_id, subject, message))
    tid = cur.lastrowid
    con.commit()
    con.close()
    return tid

def get_open_tickets():
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT id, user_id, subject, message, created_at FROM tickets WHERE status='open' ORDER BY id DESC LIMIT 20")
    rows = cur.fetchall()
    con.close()
    return rows

def close_ticket(ticket_id):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("UPDATE tickets SET status='closed' WHERE id=?", (ticket_id,))
    con.commit()
    con.close()

def get_expiring_orders():
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT o.id, o.user_id, o.expire_at, n.notif_5d, n.notif_3d, n.notif_1d, n.notif_1h, n.notif_exp FROM orders o JOIN notifications n ON o.id=n.order_id WHERE o.status='approved' AND o.expire_at IS NOT NULL")
    rows = cur.fetchall()
    con.close()
    return rows

def mark_notif(order_id, field):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("UPDATE notifications SET " + field + "=1 WHERE order_id=?", (order_id,))
    con.commit()
    con.close()

def parse_plan(plan):
    parts = plan.split("_")
    if len(parts) >= 2:
        dur_key = parts[0]
        vol_key = parts[1]
        dur = DURATIONS.get(dur_key, {})
        vol = VOLUMES.get(vol_key, {})
        return dur, vol
    return {}, {}

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
        msg = "⚠️ برای استفاده از بات باید عضو کانال ما بشی!\n\nکانال: " + CHANNEL_ID + "\n\nبعد از عضویت روی عضو شدم بزن."
        if update.message:
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.callback_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        return False
    return True

def main_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🛒 خرید VPN")],
        [KeyboardButton("🎁 تست رایگان"), KeyboardButton("💰 افزایش موجودی")],
        [KeyboardButton("🎰 گردونه شانس"), KeyboardButton("👥 دعوت از دوستان")],
        [KeyboardButton("👤 حساب من"), KeyboardButton("📋 اشتراک های من")],
        [KeyboardButton("🎫 تیکت پشتیبانی"), KeyboardButton("📞 پشتیبانی")],
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
            await context.bot.send_message(referred_by, "🎉 یه نفر با لینک دعوت شما وارد شد!\nوقتی اولین خریدش رو انجام بده 10% به کیف پول شما اضافه میشه.")
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
        await query.edit_message_text("✅ عضویتت تایید شد!")
        await context.bot.send_message(user.id, "یه گزینه انتخاب کن:", reply_markup=main_menu())
    else:
        await query.answer("هنوز عضو نشدی!", show_alert=True)

async def keyboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if text == "🛒 خرید VPN":
        if not await check_membership(update, context):
            return
        context.user_data["custom"] = {}
        keyboard = [[InlineKeyboardButton(d["name"], callback_data="custom_dur_" + k)] for k, d in DURATIONS.items()]
        keyboard.append([InlineKeyboardButton("🔙 برگشت", callback_data="back_main")])
        await update.message.reply_text("🛒 خرید VPN\n\n📅 مدت زمان رو انتخاب کن:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif text == "🎁 تست رایگان":
        keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data="back_main")]]
        await update.message.reply_text(
            "🎁 تست رایگان\n\n❌ متاسفانه در حال حاضر تست رایگان موجود نیست!\n\n📞 برای اطلاعات بیشتر با پشتیبانی تماس بگیر.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif text == "💰 افزایش موجودی":
        if not await check_membership(update, context):
            return
        amounts = [50000, 100000, 200000, 500000]
        keyboard = [[InlineKeyboardButton(fmt(a) + " تومان", callback_data="topup_amount_" + str(a))] for a in amounts]
        keyboard.append([InlineKeyboardButton("🔙 برگشت", callback_data="back_main")])
        await update.message.reply_text("💰 افزایش موجودی\n\nمبلغ رو انتخاب کن:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif text == "🎰 گردونه شانس":
        if not await check_membership(update, context):
            return
        points = get_points(user_id)
        can_spin1 = can_spin_wheel1(user_id)
        can_spin2 = points >= 5
        keyboard = []
        if can_spin1:
            keyboard.append([InlineKeyboardButton("🎰 گردونه 1 (روزانه - رایگان)", callback_data="spin_wheel1")])
        else:
            keyboard.append([InlineKeyboardButton("⏳ گردونه 1 (فردا)", callback_data="wheel_info")])
        if can_spin2:
            keyboard.append([InlineKeyboardButton("🎰 گردونه 2 (5 امتیاز - کانفیگ)", callback_data="spin_wheel2")])
        else:
            keyboard.append([InlineKeyboardButton("🔒 گردونه 2 (" + str(points) + "/5 امتیاز)", callback_data="wheel_info")])
        keyboard.append([InlineKeyboardButton("🔙 برگشت", callback_data="back_main")])
        await update.message.reply_text(
            "🎰 گردونه شانس\n\n"
            "⭐ امتیاز شما: " + str(points) + "\n\n"
            "🎰 گردونه 1: هر روز یک بار - جوایز تخفیف\n"
            "🎰 گردونه 2: 5 امتیاز - جوایز کانفیگ\n\n"
            "💡 هر 10,000 تومان خرید = 1 امتیاز",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif text == "👥 دعوت از دوستان":
        ref_link = "https://t.me/" + BOT_USERNAME + "?start=" + str(user_id)
        count = get_referral_count(user_id)
        earnings = get_referral_earnings(user_id)
        keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data="back_main")]]
        await update.message.reply_text(
            "👥 سیستم دعوت از دوستان\n\n"
            "🔗 لینک دعوت شما:\n`" + ref_link + "`\n\n"
            "👤 تعداد دعوت شدگان: " + str(count) + " نفر\n"
            "💰 درآمد از دعوت: " + fmt(earnings) + " تومان\n\n"
            "📌 قوانین:\n"
            "- دعوت شونده 15% تخفیف اولین خرید\n"
            "- شما 10% از هر خرید دعوت شونده",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif text == "👤 حساب من":
        wallet = get_wallet(user_id)
        orders = get_order_count(user_id)
        points = get_points(user_id)
        ref_count = get_referral_count(user_id)
        ref_link = "https://t.me/" + BOT_USERNAME + "?start=" + str(user_id)
        keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data="back_main")]]
        await update.message.reply_text(
            "👤 حساب کاربری\n\n"
            "ID: " + str(user_id) + "\n"
            "💰 موجودی: " + fmt(wallet) + " تومان\n"
            "⭐ امتیاز: " + str(points) + "\n"
            "🛒 تعداد خرید: " + str(orders) + "\n"
            "👥 دعوت شدگان: " + str(ref_count) + " نفر\n\n"
            "🔗 لینک دعوت:\n`" + ref_link + "`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif text == "📋 اشتراک های من":
        rows = get_user_orders(user_id)
        keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data="back_main")]]
        if not rows:
            await update.message.reply_text("❌ هیچ اشتراکی نداری!\n\nبرای خرید از منو اقدام کن.", reply_markup=InlineKeyboardMarkup(keyboard))
            return
        status_map = {"approved": "✅ فعال", "pending": "⏳ در انتظار", "rejected": "❌ رد شده"}
        msg = "📋 اشتراک های شما:\n\n"
        for oid, plan, amount, volume_gb, used_gb, status, expire_at, created in rows:
            msg += "سفارش #" + str(oid) + "\n"
            msg += "📦 پلن: " + str(plan) + "\n"
            msg += "💰 مبلغ: " + fmt(amount) + " تومان\n"
            msg += "وضعیت: " + status_map.get(status, status) + "\n"
            if volume_gb and volume_gb > 0:
                remaining = max(0, volume_gb - (used_gb or 0))
                msg += "📊 حجم: " + str(volume_gb) + "GB | مونده: " + str(round(remaining, 2)) + "GB\n"
            if expire_at:
                try:
                    exp = datetime.fromisoformat(expire_at)
                    now = datetime.now()
                    if exp > now:
                        diff = exp - now
                        days = diff.days
                        hours = diff.seconds // 3600
                        msg += "⏰ انقضا: " + expire_at[:10] + " (" + str(days) + " روز و " + str(hours) + " ساعت مانده)\n"
                    else:
                        msg += "⏰ منقضی شده!\n"
                except:
                    msg += "⏰ انقضا: " + str(expire_at)[:10] + "\n"
            msg += "📅 تاریخ خرید: " + created[:10] + "\n\n"
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))

    elif text == "🎫 تیکت پشتیبانی":
        keyboard = [
            [InlineKeyboardButton("✏️ ارسال تیکت جدید", callback_data="new_ticket")],
            [InlineKeyboardButton("🔙 برگشت", callback_data="back_main")]
        ]
        await update.message.reply_text(
            "🎫 تیکت پشتیبانی\n\nمشکلت رو اینجا گزارش بده تا بررسی بشه.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif text == "📞 پشتیبانی":
        keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data="back_main")]]
        support_text = "📞 پشتیبانی\n\nبرای ارتباط با پشتیبانی:\n"
        for s in SUPPORT_USERS:
            support_text += "👤 " + s + "\n"
        await update.message.reply_text(support_text, reply_markup=InlineKeyboardMarkup(keyboard))

async def spin_wheel1_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not can_spin_wheel1(user_id):
        await query.answer("فردا میتونی بچرخونی!", show_alert=True)
        return
    update_wheel1_time(user_id)
    prize = random.choice(WHEEL1_PRIZES)
    anim = "🎰 در حال چرخش...\n\n"
    anim += "🎁 جایزه شما: " + prize["name"] + "\n\n"
    if prize["type"] == "none":
        anim += "😅 بدشانسی! دفعه بعد موفق باشی."
        keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data="back_main")]]
    elif prize["type"] == "discount":
        code = generate_wheel_code(str(prize["value"]) + "%")
        anim += "🏷️ کد تخفیف " + str(prize["value"]) + "%:\n`" + code + "`\n\nاین کد رو موقع خرید وارد کن!"
        keyboard = [[InlineKeyboardButton("🛒 خرید VPN", callback_data="go_buy"), InlineKeyboardButton("🔙 برگشت", callback_data="back_main")]]
    else:
        anim += "📩 ادمین به زودی کانفیگت رو میفرسته."
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(admin_id, "🎰 جایزه گردونه 1\nکاربر: " + str(user_id) + "\nجایزه: " + prize["name"])
            except:
                pass
        keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data="back_main")]]
    await query.edit_message_text(anim, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def spin_wheel2_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    points = get_points(user_id)
    if points < 5:
        await query.answer("امتیاز کافی نداری!", show_alert=True)
        return
    deduct_points(user_id, 5)
    prize = random.choice(WHEEL2_PRIZES)
    anim = "🎰 در حال چرخش...\n\n"
    anim += "🎁 جایزه شما: " + prize["name"] + "\n\n"
    if prize["type"] == "none":
        anim += "😅 بدشانسی! دفعه بعد موفق باشی."
    else:
        anim += "📩 ادمین به زودی کانفیگت رو میفرسته."
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(admin_id, "🎰 جایزه گردونه 2\nکاربر: " + str(user_id) + "\nجایزه: " + prize["name"])
            except:
                pass
    keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data="back_main")]]
    await query.edit_message_text(anim, reply_markup=InlineKeyboardMarkup(keyboard))

async def wheel_info_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("برای گردونه 1 فردا بیا، برای گردونه 2 امتیاز بیشتر جمع کن!", show_alert=True)

async def new_ticket_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🎫 تیکت جدید\n\nمشکل یا سوالت رو بنویس:")
    return WAIT_TICKET

async def receive_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.message.text
    tid = create_ticket(user.id, "تیکت جدید", message)
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(admin_id,
                "🎫 تیکت جدید #" + str(tid) + "\n"
                "کاربر: " + str(user.id) + " (@" + str(user.username) + ")\n"
                "پیام: " + message + "\n\n"
                "پاسخ: /ticket_reply_" + str(tid) + "_" + str(user.id)
            )
        except:
            pass
    await update.message.reply_text(
        "✅ تیکت #" + str(tid) + " ثبت شد!\nبه زودی پاسخ داده میشه.",
        reply_markup=back_btn()
    )
    return ConversationHandler.END

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
        keyboard.append([InlineKeyboardButton(v["name"] + " - " + fmt(price) + " تومان", callback_data="custom_vol_" + k)])
    keyboard.append([InlineKeyboardButton("🔙 برگشت", callback_data="back_main")])
    await query.edit_message_text("📅 مدت: " + DURATIONS[dur_key]["name"] + "\n\n📊 حجم رو انتخاب کن:", reply_markup=InlineKeyboardMarkup(keyboard))

async def custom_volume_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    vol_key = query.data.split("_")[2]
    context.user_data["custom"]["volume"] = vol_key
    keyboard = [[InlineKeyboardButton(s["name"], callback_data="custom_srv_" + k)] for k, s in SERVERS.items()]
    keyboard.append([InlineKeyboardButton("🔙 برگشت", callback_data="back_main")])
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
    context.user_data["selected_volume_gb"] = vol["gb"]
    context.user_data["selected_months"] = dur["months"]
    context.user_data["discount_code"] = None
    keyboard = []
    if wallet >= total:
        keyboard.append([InlineKeyboardButton("💳 پرداخت از کیف پول", callback_data="pay_wallet")])
    keyboard.append([InlineKeyboardButton("💵 پرداخت کارت به کارت", callback_data="pay_card")])
    keyboard.append([InlineKeyboardButton("🏷️ کد تخفیف دارم", callback_data="discount_code")])
    keyboard.append([InlineKeyboardButton("🔙 برگشت", callback_data="back_main")])
    ref_text = "\n🎁 تخفیف دعوت 15% اعمال شد!" if referral_discount else ""
    await query.edit_message_text(
        "📋 خلاصه سفارش:\n\n"
        "📅 مدت: " + dur["name"] + "\n"
        "📊 حجم: " + vol["name"] + "\n"
        "🌍 سرور: " + srv["name"] + "\n"
        "💰 قیمت نهایی: " + fmt(total) + " تومان" + ref_text + "\n"
        "👛 موجودی: " + fmt(wallet) + " تومان\n\n"
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
    if isinstance(percent, int):
        discounted = int(original * (1 - percent / 100))
    else:
        discounted = original
    context.user_data["discount_code"] = code
    context.user_data["selected_price"] = discounted
    wallet = get_wallet(user_id)
    keyboard = []
    if wallet >= discounted:
        keyboard.append([InlineKeyboardButton("💳 پرداخت از کیف پول", callback_data="pay_wallet")])
    keyboard.append([InlineKeyboardButton("💵 پرداخت کارت به کارت", callback_data="pay_card")])
    keyboard.append([InlineKeyboardButton("🔙 برگشت", callback_data="back_main")])
    await update.message.reply_text(
        msg + "\n\n"
        "💰 قیمت اصلی: " + fmt(original) + " تومان\n"
        "✅ قیمت نهایی: " + fmt(discounted) + " تومان\n\n"
        "روش پرداخت رو انتخاب کن:",
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
        "مبلغ: " + fmt(price) + " تومان\n"
        "شماره کارت: `" + CARD_NUMBER + "`\n"
        "به نام: " + CARD_OWNER + "\n\n"
        "بعد از واریز عکس رسید رو اینجا بفرست 👇",
        parse_mode="Markdown"
    )
    return WAIT_RECEIPT

async def pay_wallet_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    price = context.user_data.get("selected_price", 0)
    plan_key = context.user_data.get("selected_plan", "custom")
    volume_gb = context.user_data.get("selected_volume_gb", 0)
    months = context.user_data.get("selected_months", 1)
    user_id = query.from_user.id
    wallet = get_wallet(user_id)
    if wallet < price:
        await query.answer("موجودی کافی نیست!", show_alert=True)
        return
    discount_code = context.user_data.get("discount_code")
    if discount_code:
        use_discount_code(user_id, discount_code)
    update_wallet(user_id, -price)
    expire_at = (datetime.now() + timedelta(days=30 * months)).isoformat()
    oid = create_order(user_id, plan_key, price, "wallet", volume_gb, expire_at)
    approve_order(oid, volume_gb, expire_at)
    pts = add_points(user_id, price)
    referrer = get_referred_by(user_id)
    if referrer:
        reward = add_referral_reward(referrer, price)
        try:
            await context.bot.send_message(referrer, "🎉 یکی از دعوت شدگان شما خرید کرد!\n💰 " + fmt(reward) + " تومان به کیف پول شما اضافه شد.")
        except:
            pass
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(admin_id,
                "✅ خرید از کیف پول\nکاربر: " + str(user_id) + "\nپلن: " + plan_key + "\nمبلغ: " + fmt(price) + " تومان\nسفارش #" + str(oid))
        except:
            pass
    await query.edit_message_text(
        "✅ خرید موفق! 🎉\n\n"
        "سفارش #" + str(oid) + " ثبت شد.\n"
        "انقضا: " + expire_at[:10] + "\n"
        "⭐ " + str(pts) + " امتیاز اضافه شد.\n"
        "کانفیگ شما به زودی ارسال میشه.",
        reply_markup=back_btn()
    )

async def receive_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    pending_type = context.user_data.get("pending_type", "buy")
    if pending_type == "buy":
        plan_key = context.user_data.get("selected_plan", "")
        price = context.user_data.get("pending_price", 0)
        volume_gb = context.user_data.get("selected_volume_gb", 0)
        months = context.user_data.get("selected_months", 1)
        discount_code = context.user_data.get("discount_code", "")
        expire_at = (datetime.now() + timedelta(days=30 * months)).isoformat()
        oid = create_order(user.id, plan_key, price, "receipt_sent", volume_gb, expire_at)
        if discount_code:
            use_discount_code(user.id, discount_code)
        caption = (
            "🧾 رسید جدید - سفارش #" + str(oid) + "\n"
            "کاربر: " + str(user.id) + " (@" + str(user.username) + ")\n"
            "پلن: " + plan_key + "\n"
            "مبلغ: " + fmt(price) + " تومان\n"
            "حجم: " + str(volume_gb) + "GB\n"
            "انقضا: " + expire_at[:10] + "\n"
        )
        if discount_code:
            caption += "کد تخفیف: " + discount_code + "\n"
        caption += "\n✅ تایید: /approve_" + str(oid) + "\n❌ رد: /reject_" + str(oid)
    else:
        amount = context.user_data.get("topup_amount", 0)
        oid = create_order(user.id, "topup", amount, "receipt_sent")
        caption = (
            "💰 شارژ کیف پول - #" + str(oid) + "\n"
            "کاربر: " + str(user.id) + " (@" + str(user.username) + ")\n"
            "مبلغ: " + fmt(amount) + " تومان\n\n"
            "✅ تایید: /topup_approve_" + str(oid) + "_" + str(user.id) + "_" + str(amount) + "\n"
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
        "✅ رسیدت دریافت شد!\nبعد از بررسی (زیر 30 دقیقه) کانفیگت ارسال میشه. 🙏",
        reply_markup=main_menu()
    )
    return ConversationHandler.END

async def topup_amount_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    amount = int(query.data.split("_")[2])
    context.user_data["topup_amount"] = amount
    context.user_data["pending_type"] = "topup"
    await query.edit_message_text(
        "💳 شارژ کیف پول\n\n"
        "مبلغ: " + fmt(amount) + " تومان\n"
        "شماره کارت: `" + CARD_NUMBER + "`\n"
        "به نام: " + CARD_OWNER + "\n\n"
        "بعد از واریز عکس رسید رو اینجا بفرست 👇",
        parse_mode="Markdown"
    )
    return WAIT_TOPUP_RECEIPT

async def go_buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["custom"] = {}
    keyboard = [[InlineKeyboardButton(d["name"], callback_data="custom_dur_" + k)] for k, d in DURATIONS.items()]
    keyboard.append([InlineKeyboardButton("🔙 برگشت", callback_data="back_main")])
    await query.edit_message_text("🛒 خرید VPN\n\n📅 مدت زمان رو انتخاب کن:", reply_markup=InlineKeyboardMarkup(keyboard))

async def back_main_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✅")
    await context.bot.send_message(query.from_user.id, "یه گزینه انتخاب کن:", reply_markup=main_menu())

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
        [InlineKeyboardButton("🎫 تیکت های باز", callback_data="admin_tickets")],
    ]
    await update.message.reply_text(
        "👑 پنل ادمین\n\n"
        "👤 کل کاربران: " + str(total_users) + "\n"
        "🛒 کل سفارشات: " + str(total_orders) + "\n"
        "💰 کل درآمد: " + fmt(total_income) + " تومان\n"
        "⏳ در انتظار: " + str(pending_orders),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def admin_back_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="admin_back")]])

async def admin_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    total_users, total_orders, total_income, pending_orders = get_stats()
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM referrals")
    ref_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM tickets WHERE status='open'")
    open_tickets = cur.fetchone()[0]
    con.close()
    await query.edit_message_text(
        "📊 آمار کامل\n\n"
        "👤 کل کاربران: " + str(total_users) + "\n"
        "🛒 سفارشات تایید شده: " + str(total_orders) + "\n"
        "⏳ سفارشات در انتظار: " + str(pending_orders) + "\n"
        "💰 کل درآمد: " + fmt(total_income) + " تومان\n"
        "👥 کل رفرال ها: " + str(ref_count) + "\n"
        "🎫 تیکت های باز: " + str(open_tickets),
        reply_markup=admin_back_keyboard()
    )

async def admin_tickets_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    tickets = get_open_tickets()
    if not tickets:
        await query.edit_message_text("✅ هیچ تیکت بازی نداری!", reply_markup=admin_back_keyboard())
        return
    text = "🎫 تیکت های باز:\n\n"
    for tid, uid, subject, message, created in tickets:
        text += "#" + str(tid) + " - کاربر " + str(uid) + "\n"
        text += "پیام: " + message[:50] + "...\n"
        text += "پاسخ: /ticket_reply_" + str(tid) + "_" + str(uid) + "\n\n"
    await query.edit_message_text(text, reply_markup=admin_back_keyboard())

async def admin_broadcast_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    await query.edit_message_text("📨 پیام همگانی\n\nمتن پیام رو بفرست:", reply_markup=admin_back_keyboard())
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
    await query.edit_message_text("💬 پیام شخصی\n\nآیدی عددی کاربر رو بفرست:", reply_markup=admin_back_keyboard())
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
        await update.message.reply_text("❌ ارسال ناموفق! کاربر بات رو بلاک کرده.")
    return ConversationHandler.END

async def admin_wallet_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    await query.edit_message_text("💰 تغییر موجودی\n\nآیدی عددی کاربر رو بفرست:", reply_markup=admin_back_keyboard())
    return WAIT_ADMIN_WALLET

async def receive_admin_wallet_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    try:
        uid = int(update.message.text.strip())
        context.user_data["admin_target_user"] = uid
        wallet = get_wallet(uid)
        await update.message.reply_text("کاربر " + str(uid) + "\n💰 موجودی فعلی: " + fmt(wallet) + " تومان\n\nمبلغ رو وارد کن (منفی برای کسر):")
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
            await context.bot.send_message(uid, "💰 موجودی کیف پول شما " + action + " شد.\nموجودی جدید: " + fmt(new_wallet) + " تومان")
        except:
            pass
        await update.message.reply_text("✅ " + fmt(abs(amount)) + " تومان " + action + " شد.\nموجودی جدید: " + fmt(new_wallet) + " تومان")
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
        await query.edit_message_text("✅ هیچ سفارش در انتظاری نداری!", reply_markup=admin_back_keyboard())
        return
    text = "⏳ سفارشات در انتظار:\n\n"
    for oid, uid, plan, amount in rows:
        text += "#" + str(oid) + " - کاربر " + str(uid) + " - " + str(plan) + " - " + fmt(amount) + " تومان\n"
        text += "✅ /approve_" + str(oid) + "  ❌ /reject_" + str(oid) + "\n\n"
    await query.edit_message_text(text, reply_markup=admin_back_keyboard())

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
        [InlineKeyboardButton("🎫 تیکت های باز", callback_data="admin_tickets")],
    ]
    await query.edit_message_text(
        "👑 پنل ادمین\n\n"
        "👤 کل کاربران: " + str(total_users) + "\n"
        "🛒 کل سفارشات: " + str(total_orders) + "\n"
        "💰 کل درآمد: " + fmt(total_income) + " تومان\n"
        "⏳ در انتظار: " + str(pending_orders),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def admin_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    oid = int(update.message.text.split("_")[1])
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT user_id, plan, amount, volume_gb, expire_at FROM orders WHERE id=?", (oid,))
    row = cur.fetchone()
    con.close()
    if not row:
        await update.message.reply_text("❌ سفارش پیدا نشد!")
        return
    user_id, plan_key, amount, volume_gb, expire_at = row
    approve_order(oid, volume_gb, expire_at)
    pts = add_points(user_id, amount)
    referrer = get_referred_by(user_id)
    if referrer:
        reward = add_referral_reward(referrer, amount)
        try:
            await context.bot.send_message(referrer, "🎉 یکی از دعوت شدگان شما خرید کرد!\n💰 " + fmt(reward) + " تومان به کیف پول شما اضافه شد.")
        except:
            pass
    try:
        await context.bot.send_message(user_id,
            "✅ پرداخت تایید شد! 🎉\n\n"
            "پلن: " + str(plan_key) + "\n"
            "مبلغ: " + fmt(amount) + " تومان\n"
            "انقضا: " + (expire_at[:10] if expire_at else "نامشخص") + "\n"
            "⭐ " + str(pts) + " امتیاز اضافه شد.\n\n"
            "کانفیگ شما:\n`اینجا کانفیگ رو قرار بده`\n\n"
            "سفارش #" + str(oid),
            parse_mode="Markdown"
        )
    except:
        pass
    await update.message.reply_text("✅ سفارش #" + str(oid) + " تایید شد.")

async def admin_topup_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    parts = update.message.text.split("_")
    oid, user_id, amount = int(parts[2]), int(parts[3]), int(parts[4])
    approve_order(oid)
    update_wallet(user_id, amount)
    try:
        await context.bot.send_message(user_id, "✅ " + fmt(amount) + " تومان به کیف پول شما اضافه شد 💰\nموجودی جدید: " + fmt(get_wallet(user_id)) + " تومان")
    except:
        pass
    await update.message.reply_text("✅ " + fmt(amount) + " تومان به کاربر " + str(user_id) + " اضافه شد.")

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
            await context.bot.send_message(row[0], "❌ رسید سفارش #" + str(oid) + " تایید نشد.\nبا پشتیبانی تماس بگیر.")
        except:
            pass
    await update.message.reply_text("❌ سفارش #" + str(oid) + " رد شد.")

async def ticket_reply_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    parts = update.message.text.split("_")
    if len(parts) < 4:
        return
    tid = int(parts[2])
    uid = int(parts[3])
    context.user_data["ticket_reply_id"] = tid
    context.user_data["ticket_reply_user"] = uid
    await update.message.reply_text("متن پاسخ رو بفرست:")
    return WAIT_TICKET_REPLY_TEXT

async def receive_ticket_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    tid = context.user_data.get("ticket_reply_id")
    uid = context.user_data.get("ticket_reply_user")
    text = update.message.text
    close_ticket(tid)
    try:
        await context.bot.send_message(uid, "📩 پاسخ تیکت #" + str(tid) + ":\n\n" + text)
        await update.message.reply_text("✅ پاسخ ارسال و تیکت بسته شد.")
    except:
        await update.message.reply_text("❌ ارسال ناموفق!")
    return ConversationHandler.END

async def check_expiry_job(context: ContextTypes.DEFAULT_TYPE):
    orders = get_expiring_orders()
    now = datetime.now()
    for oid, uid, expire_at, n5d, n3d, n1d, n1h, nexp in orders:
        try:
            exp = datetime.fromisoformat(expire_at)
            diff = exp - now
            total_seconds = diff.total_seconds()
            if total_seconds < 0 and not nexp:
                mark_notif(oid, "notif_exp")
                try:
                    await context.bot.send_message(uid, "❌ اشتراک شما منقضی شد!\n\nسفارش #" + str(oid) + "\n\nبرای تمدید از منو اقدام کن.")
                except:
                    pass
                for admin_id in ADMIN_IDS:
                    try:
                        await context.bot.send_message(admin_id, "⚠️ اشتراک کاربر " + str(uid) + " (سفارش #" + str(oid) + ") منقضی شد.")
                    except:
                        pass
            elif 0 < total_seconds <= 3600 and not n1h:
                mark_notif(oid, "notif_1h")
                try:
                    await context.bot.send_message(uid, "⚠️ اشتراک شما ظرف 1 ساعت منقضی میشه!\n\nسفارش #" + str(oid))
                except:
                    pass
            elif 0 < total_seconds <= 86400 and not n1d:
                mark_notif(oid, "notif_1d")
                try:
                    await context.bot.send_message(uid, "⚠️ اشتراک شما فردا منقضی میشه!\n\nسفارش #" + str(oid))
                except:
                    pass
            elif 0 < total_seconds <= 259200 and not n3d:
                mark_notif(oid, "notif_3d")
                try:
                    await context.bot.send_message(uid, "⏰ 3 روز تا انقضای اشتراک شما مانده.\n\nسفارش #" + str(oid))
                except:
                    pass
            elif 0 < total_seconds <= 432000 and not n5d:
                mark_notif(oid, "notif_5d")
                try:
                    await context.bot.send_message(uid, "⏰ 5 روز تا انقضای اشتراک شما مانده.\n\nسفارش #" + str(oid))
                except:
                    pass
        except:
            pass

def main():
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(pay_card_callback,          pattern="^pay_card$"),
            CallbackQueryHandler(topup_amount_callback,      pattern="^topup_amount_"),
            CallbackQueryHandler(discount_code_callback,     pattern="^discount_code$"),
            CallbackQueryHandler(admin_broadcast_callback,   pattern="^admin_broadcast$"),
            CallbackQueryHandler(admin_wallet_callback,      pattern="^admin_wallet$"),
            CallbackQueryHandler(admin_private_msg_callback, pattern="^admin_private_msg$"),
            CallbackQueryHandler(new_ticket_callback,        pattern="^new_ticket$"),
            MessageHandler(filters.Regex(r"^/ticket_reply_\d+_\d+$"), ticket_reply_cmd),
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
            WAIT_TICKET:              [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_ticket)],
            WAIT_TICKET_REPLY_TEXT:   [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_ticket_reply)],
        },
        fallbacks=[CommandHandler("start", start)],
        per_message=False,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(check_join_callback,      pattern="^check_join$"))
    app.add_handler(CallbackQueryHandler(custom_duration_callback, pattern="^custom_dur_"))
    app.add_handler(CallbackQueryHandler(custom_volume_callback,   pattern="^custom_vol_"))
    app.add_handler(CallbackQueryHandler(custom_server_callback,   pattern="^custom_srv_"))
    app.add_handler(CallbackQueryHandler(pay_wallet_callback,      pattern="^pay_wallet$"))
    app.add_handler(CallbackQueryHandler(spin_wheel1_callback,     pattern="^spin_wheel1$"))
    app.add_handler(CallbackQueryHandler(spin_wheel2_callback,     pattern="^spin_wheel2$"))
    app.add_handler(CallbackQueryHandler(wheel_info_callback,      pattern="^wheel_info$"))
    app.add_handler(CallbackQueryHandler(go_buy_callback,          pattern="^go_buy$"))
    app.add_handler(CallbackQueryHandler(back_main_callback,       pattern="^back_main$"))
    app.add_handler(CallbackQueryHandler(admin_stats_callback,     pattern="^admin_stats$"))
    app.add_handler(CallbackQueryHandler(admin_pending_callback,   pattern="^admin_pending$"))
    app.add_handler(CallbackQueryHandler(admin_tickets_callback,   pattern="^admin_tickets$"))
    app.add_handler(CallbackQueryHandler(admin_back_callback,      pattern="^admin_back$"))

    KEYBOARD_BUTTONS = "^(🛒 خرید VPN|🎁 تست رایگان|💰 افزایش موجودی|🎰 گردونه شانس|👥 دعوت از دوستان|👤 حساب من|📋 اشتراک های من|🎫 تیکت پشتیبانی|📞 پشتیبانی)$"
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(KEYBOARD_BUTTONS), keyboard_handler))
    app.add_handler(MessageHandler(filters.Regex(r"^/approve_\d+$"),               admin_approve))
    app.add_handler(MessageHandler(filters.Regex(r"^/topup_approve_\d+_\d+_\d+$"), admin_topup_approve))
    app.add_handler(MessageHandler(filters.Regex(r"^/reject_\d+$"),                admin_reject))

    app.job_queue.run_repeating(check_expiry_job, interval=3600, first=60)

    print("✅ بات در حال اجراست...")
    app.run_polling()

if __name__ == "__main__":
    main()
