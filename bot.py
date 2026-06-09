import logging
import sqlite3
import random
import string
import requests
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

BOT_TOKEN    = "8925445808:AAGkJU3BX7f82SVG4YyvYHJALKro5xrZAhM"
CHANNEL_ID   = "@VPN_IRONMAN"
ADMIN_IDS    = [8471252047, 1111111111]
CARD_NUMBER  = "6219-8619-2847-2389"
CARD_OWNER   = "ایران بوصیدی"
BOT_USERNAME = "your_bot_username"
SUPPORT_USERS = ["@Ali2011Ali2011_Ali", "@MARDAN_CORE"]

RANK_REWARDS = [500000, 300000, 250000, 150000, 100000, 50000, 40000, 30000, 20000, 10000]

PANELS = {
    "eco": {
        "name": "💚 پنل اقتصادی",
        "desc": "تک کاربره - سرورهای متوسط رو به بالا",
        "plans": {
            "50gb":      {"name": "50GB",            "gb": 50,   "price": 75000},
            "100gb":     {"name": "100GB",           "gb": 100,  "price": 150000},
            "150gb":     {"name": "150GB",           "gb": 150,  "price": 225000},
            "200gb":     {"name": "200GB",           "gb": 200,  "price": 300000},
            "unlimited": {"name": "نامحدود (1.5TB)", "gb": -1,   "price": 800000},
        },
        "custom_min_gb": 20, "custom_price_per_gb": 1500,
    },
    "pro": {
        "name": "💙 پنل قوی",
        "desc": "دو کاربره - سرورهای قدرتمندتر",
        "plans": {
            "50gb":      {"name": "50GB",          "gb": 50,   "price": 100000},
            "100gb":     {"name": "100GB",         "gb": 100,  "price": 200000},
            "150gb":     {"name": "150GB",         "gb": 150,  "price": 300000},
            "200gb":     {"name": "200GB",         "gb": 200,  "price": 350000},
            "unlimited": {"name": "نامحدود (2TB)", "gb": -1,   "price": 1000000},
        },
        "custom_min_gb": 10, "custom_price_per_gb": 2000,
    },
    "trade": {
        "name": "🟡 پنل ترید",
        "desc": "آی‌پی ثابت - پینگ پایین",
        "plans": {
            "50gb":      {"name": "50GB",          "gb": 50,   "price": 150000},
            "100gb":     {"name": "100GB",         "gb": 100,  "price": 300000},
            "150gb":     {"name": "150GB",         "gb": 150,  "price": 450000},
            "200gb":     {"name": "200GB",         "gb": 200,  "price": 600000},
            "unlimited": {"name": "نامحدود (1TB)", "gb": -1,   "price": 1500000},
        },
        "custom_min_gb": 8, "custom_price_per_gb": 5000,
    },
    "game": {
        "name": "🔴 پنل گیمینگ",
        "desc": "مخصوص گیم - پینگ 50 تا 100 تضمینی",
        "plans": {
            "50gb":      {"name": "50GB",          "gb": 50,   "price": 250000},
            "100gb":     {"name": "100GB",         "gb": 100,  "price": 500000},
            "150gb":     {"name": "150GB",         "gb": 150,  "price": 750000},
            "200gb":     {"name": "200GB",         "gb": 200,  "price": 1000000},
            "unlimited": {"name": "نامحدود (1TB)", "gb": -1,   "price": 2500000},
        },
        "custom_min_gb": 5, "custom_price_per_gb": 8000,
    },
}

DISCOUNT_CODES = {
    "INYAS":  {"percent": 25, "first_only": False},
    "MARDAN": {"percent": 100, "first_only": True},
}

WHEEL1_PRIZES = [
    {"name": "20% تخفیف 🎉", "type": "discount", "value": 20},
    {"name": "10% تخفیف 🎁", "type": "discount", "value": 10},
    {"name": "50% تخفیف 🔥", "type": "discount", "value": 50},
    {"name": "30% تخفیف ✨", "type": "discount", "value": 30},
    {"name": "500MB یک روزه 📦", "type": "config", "value": "500mb_1d"},
    {"name": "پوچ 😅", "type": "none", "value": 0},
]

WHEEL2_PRIZES = [
    {"name": "10,000 تومان اعتبار 💰", "type": "wallet", "value": 10000},
    {"name": "15,000 تومان اعتبار 💰", "type": "wallet", "value": 15000},
    {"name": "20,000 تومان اعتبار 💰", "type": "wallet", "value": 20000},
    {"name": "30,000 تومان اعتبار 💰", "type": "wallet", "value": 30000},
    {"name": "50,000 تومان اعتبار 💰", "type": "wallet", "value": 50000},
    {"name": "پوچ 😅", "type": "none", "value": 0},
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
WAIT_TICKET_REPLY_TEXT   = 10
WAIT_CUSTOM_GB           = 11
WAIT_CONFIG_TEXT         = 12
WAIT_ADMIN_POINTS        = 13
WAIT_ADMIN_POINTS_AMOUNT = 14
WAIT_RATE_SERVER         = 15

logging.basicConfig(level=logging.INFO)

def is_admin(uid): return uid in ADMIN_IDS
def fmt(n):
    try: return "{:,}".format(int(n))
    except: return str(n)
def back_btn():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="back_main")]])

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
            total_gb     REAL DEFAULT 0,
            referred_by  INTEGER DEFAULT NULL,
            last_wheel1  TEXT DEFAULT NULL,
            last_wheel2  TEXT DEFAULT NULL,
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
            config       TEXT DEFAULT NULL,
            expire_at    TEXT DEFAULT NULL,
            rated        INTEGER DEFAULT 0,
            created_at   TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS server_ratings (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id   INTEGER,
            user_id    INTEGER,
            panel      TEXT,
            rating     INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
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
            message     TEXT,
            status      TEXT DEFAULT 'open',
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS wheel_codes (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            code       TEXT UNIQUE,
            prize      TEXT,
            used       INTEGER DEFAULT 0,
            user_id    INTEGER DEFAULT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS notifications (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id  INTEGER,
            notif_5d  INTEGER DEFAULT 0,
            notif_3d  INTEGER DEFAULT 0,
            notif_1d  INTEGER DEFAULT 0,
            notif_1h  INTEGER DEFAULT 0,
            notif_exp INTEGER DEFAULT 0
        );
    """)
    con.commit()
    con.close()

def ensure_user(uid, username, referred_by=None):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT user_id FROM users WHERE user_id=?", (uid,))
    exists = cur.fetchone()
    if not exists:
        cur.execute("INSERT INTO users (user_id, username, referred_by) VALUES (?,?,?)", (uid, username, referred_by))
        if referred_by:
            cur.execute("INSERT INTO referrals (referrer_id, referred_id) VALUES (?,?)", (referred_by, uid))
    con.commit()
    con.close()
    return not exists

def get_wallet(uid):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT wallet FROM users WHERE user_id=?", (uid,))
    row = cur.fetchone()
    con.close()
    return row[0] if row else 0

def get_points(uid):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT points FROM users WHERE user_id=?", (uid,))
    row = cur.fetchone()
    con.close()
    return row[0] if row else 0

def get_order_count(uid):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT order_count FROM users WHERE user_id=?", (uid,))
    row = cur.fetchone()
    con.close()
    return row[0] if row else 0

def update_wallet(uid, amount):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("UPDATE users SET wallet = wallet + ? WHERE user_id=?", (amount, uid))
    con.commit()
    con.close()

def update_points(uid, amount):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("UPDATE users SET points = points + ? WHERE user_id=?", (amount, uid))
    con.commit()
    con.close()

def get_referred_by(uid):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT referred_by FROM users WHERE user_id=?", (uid,))
    row = cur.fetchone()
    con.close()
    return row[0] if row else None

def get_referral_count(uid):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=?", (uid,))
    row = cur.fetchone()
    con.close()
    return row[0] if row else 0

def get_referral_earnings(uid):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT SUM(reward) FROM referrals WHERE referrer_id=?", (uid,))
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

def create_order(uid, plan, amount, receipt, volume_gb=0, expire_at=None):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("INSERT INTO orders (user_id, plan, amount, volume_gb, expire_at, receipt) VALUES (?,?,?,?,?,?)",
                (uid, plan, amount, volume_gb, expire_at, receipt))
    oid = cur.lastrowid
    cur.execute("INSERT INTO notifications (order_id) VALUES (?)", (oid,))
    con.commit()
    con.close()
    return oid

def approve_order(oid, volume_gb=0, expire_at=None):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    if expire_at:
        cur.execute("UPDATE orders SET status='approved', volume_gb=?, expire_at=? WHERE id=?", (volume_gb, expire_at, oid))
    else:
        cur.execute("UPDATE orders SET status='approved' WHERE id=?", (oid,))
    cur.execute("SELECT user_id, amount, volume_gb FROM orders WHERE id=?", (oid,))
    row = cur.fetchone()
    if row:
        cur.execute("UPDATE users SET order_count = order_count + 1, points = points + 1, total_gb = total_gb + ? WHERE user_id=?",
                    (row[2] if row[2] and row[2] > 0 else 0, row[0]))
    con.commit()
    con.close()
    return row

def get_user_orders(uid):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT id, plan, amount, volume_gb, used_gb, status, expire_at, config, rated, created_at FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10", (uid,))
    rows = cur.fetchall()
    con.close()
    return rows

def get_last_approved_order(uid):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT id, plan, volume_gb, expire_at FROM orders WHERE user_id=? AND status='approved' ORDER BY id DESC LIMIT 1", (uid,))
    row = cur.fetchone()
    con.close()
    return row

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
    tu = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM orders WHERE status='approved'")
    to_ = cur.fetchone()[0]
    cur.execute("SELECT SUM(amount) FROM orders WHERE status='approved'")
    ti = cur.fetchone()[0] or 0
    cur.execute("SELECT COUNT(*) FROM orders WHERE status='pending'")
    po = cur.fetchone()[0]
    con.close()
    return tu, to_, ti, po

def get_top_buyers():
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT user_id, username, total_gb, order_count FROM users ORDER BY total_gb DESC LIMIT 10")
    rows = cur.fetchall()
    con.close()
    return rows

def get_sales_stats():
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT SUM(amount), COUNT(*) FROM orders WHERE status='approved' AND created_at >= date('now', '-1 day')")
    today = cur.fetchone()
    cur.execute("SELECT SUM(amount), COUNT(*) FROM orders WHERE status='approved' AND created_at >= date('now', '-7 days')")
    week = cur.fetchone()
    cur.execute("SELECT SUM(amount), COUNT(*) FROM orders WHERE status='approved' AND created_at >= date('now', '-30 days')")
    month = cur.fetchone()
    cur.execute("SELECT SUM(amount), COUNT(*) FROM orders WHERE status='approved'")
    total = cur.fetchone()
    cur.execute("SELECT plan, COUNT(*), SUM(amount) FROM orders WHERE status='approved' GROUP BY plan ORDER BY COUNT(*) DESC LIMIT 5")
    top_plans = cur.fetchall()
    con.close()
    return today, week, month, total, top_plans

def get_server_rating(panel):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT AVG(rating), COUNT(*) FROM server_ratings WHERE panel=?", (panel,))
    row = cur.fetchone()
    con.close()
    return row[0] or 0, row[1] or 0

def can_spin_wheel1(uid):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT last_wheel1 FROM users WHERE user_id=?", (uid,))
    row = cur.fetchone()
    con.close()
    if not row or not row[0]: return True
    return datetime.now().date() > datetime.fromisoformat(row[0]).date()

def update_wheel1_time(uid):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("UPDATE users SET last_wheel1=? WHERE user_id=?", (datetime.now().isoformat(), uid))
    con.commit()
    con.close()

def generate_wheel_code(prize):
    code = "W-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("INSERT INTO wheel_codes (code, prize) VALUES (?,?)", (code, prize))
    con.commit()
    con.close()
    return code

def check_discount_code(uid, code):
    code = code.upper().strip()
    if code in DISCOUNT_CODES:
        dc = DISCOUNT_CODES[code]
        con = sqlite3.connect("vpn_bot.db")
        cur = con.cursor()
        cur.execute("SELECT id FROM discount_usage WHERE user_id=? AND code=?", (uid, code))
        used = cur.fetchone()
        con.close()
        if used: return None, "❌ این کد قبلا استفاده شده!"
        if dc["first_only"] and get_order_count(uid) > 0: return None, "❌ این کد فقط برای اولین خرید است!"
        return dc["percent"], "✅ تخفیف " + str(dc["percent"]) + "% اعمال شد!"
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT prize, used FROM wheel_codes WHERE code=?", (code,))
    row = cur.fetchone()
    con.close()
    if row and row[1] == 0:
        # prize format: "20%_discount"
        prize = row[0]
        if "_discount" in prize:
            try:
                percent = int(prize.replace("%_discount", ""))
                return percent, "✅ تخفیف " + str(percent) + "% اعمال شد!"
            except:
                pass
        return prize, "✅ کد گردونه معتبر است!"
    return None, "❌ کد تخفیف نامعتبر است!"

def use_discount_code(uid, code):
    code = code.upper()
    if code in DISCOUNT_CODES:
        con = sqlite3.connect("vpn_bot.db")
        cur = con.cursor()
        cur.execute("INSERT INTO discount_usage (user_id, code) VALUES (?,?)", (uid, code))
        con.commit()
        con.close()
    else:
        con = sqlite3.connect("vpn_bot.db")
        cur = con.cursor()
        cur.execute("UPDATE wheel_codes SET used=1, user_id=? WHERE code=?", (uid, code))
        con.commit()
        con.close()

def create_ticket(uid, message):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("INSERT INTO tickets (user_id, message) VALUES (?,?)", (uid, message))
    tid = cur.lastrowid
    con.commit()
    con.close()
    return tid

def get_open_tickets():
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT id, user_id, message, created_at FROM tickets WHERE status='open' ORDER BY id DESC LIMIT 20")
    rows = cur.fetchall()
    con.close()
    return rows

def close_ticket(tid):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("UPDATE tickets SET status='closed' WHERE id=?", (tid,))
    con.commit()
    con.close()

def get_expiring_orders():
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("""SELECT o.id, o.user_id, o.expire_at, o.plan, o.rated,
                   n.notif_5d, n.notif_3d, n.notif_1d, n.notif_1h, n.notif_exp
                   FROM orders o JOIN notifications n ON o.id=n.order_id
                   WHERE o.status='approved' AND o.expire_at IS NOT NULL""")
    rows = cur.fetchall()
    con.close()
    return rows

def mark_notif(oid, field):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("UPDATE notifications SET " + field + "=1 WHERE order_id=?", (oid,))
    con.commit()
    con.close()

def mark_order_rated(oid):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("UPDATE orders SET rated=1 WHERE id=?", (oid,))
    con.commit()
    con.close()

async def is_member(bot, uid):
    try:
        m = await bot.get_chat_member(CHANNEL_ID, uid)
        return m.status in ("member", "administrator", "creator")
    except: return False

async def check_membership(update, context):
    uid = update.effective_user.id
    if not await is_member(context.bot, uid):
        kb = [
            [InlineKeyboardButton("📢 عضویت در کانال", url="https://t.me/" + CHANNEL_ID.lstrip('@'))],
            [InlineKeyboardButton("✅ عضو شدم", callback_data="check_join")],
        ]
        msg = "⚠️ برای استفاده از بات باید عضو کانال ما بشی!\n\nکانال: " + CHANNEL_ID + "\n\nبعد از عضویت روی عضو شدم بزن."
        if update.message:
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb))
        else:
            await update.callback_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb))
        return False
    return True

def main_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🛒 خرید VPN")],
        [KeyboardButton("🎁 تست رایگان"), KeyboardButton("💰 افزایش موجودی")],
        [KeyboardButton("🎰 گردونه شانس"), KeyboardButton("🎲 تاس شانس")],
        [KeyboardButton("👥 دعوت از دوستان"), KeyboardButton("👤 حساب من")],
        [KeyboardButton("📋 اشتراک های من"), KeyboardButton("🏆 برترین خریداران")],
        [KeyboardButton("🎫 تیکت پشتیبانی"), KeyboardButton("📞 پشتیبانی")],
    ], resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    referred_by = None
    if context.args:
        try:
            referred_by = int(context.args[0])
            if referred_by == user.id: referred_by = None
        except: pass
    is_new = ensure_user(user.id, user.username, referred_by)
    if not await check_membership(update, context): return
    if is_new and referred_by:
        try:
            await context.bot.send_message(referred_by, "🎉 یه نفر با لینک دعوت شما وارد شد!\nوقتی اولین خریدش رو انجام بده 10% به کیف پول شما اضافه میشه.")
        except: pass
    await update.message.reply_text("سلام " + user.first_name + " 👋\n\nبه بات فروش VPN خوش اومدی 🔒\nیه گزینه انتخاب کن:", reply_markup=main_menu())

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
    uid = update.effective_user.id

    if text == "🛒 خرید VPN":
        if not await check_membership(update, context): return
        kb = []
        for k, p in PANELS.items():
            avg, cnt = get_server_rating(k)
            stars = "⭐" * round(avg) if avg > 0 else ""
            kb.append([InlineKeyboardButton(p["name"] + " " + stars, callback_data="panel_" + k)])
        kb.append([InlineKeyboardButton("🔙 برگشت", callback_data="back_main")])
        await update.message.reply_text("🛒 خرید VPN\n\nپنل مورد نظرت رو انتخاب کن:", reply_markup=InlineKeyboardMarkup(kb))

    elif text == "🎁 تست رایگان":
        await update.message.reply_text("🎁 تست رایگان\n\n❌ متاسفانه در حال حاضر تست رایگان موجود نیست!\n\n📞 برای اطلاعات بیشتر با پشتیبانی تماس بگیر.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="back_main")]]))

    elif text == "💰 افزایش موجودی":
        if not await check_membership(update, context): return
        amounts = [50000, 100000, 200000, 500000]
        kb = [[InlineKeyboardButton(fmt(a) + " تومان", callback_data="topup_amount_" + str(a))] for a in amounts]
        kb.append([InlineKeyboardButton("🔙 برگشت", callback_data="back_main")])
        await update.message.reply_text("💰 افزایش موجودی\n\nمبلغ رو انتخاب کن:", reply_markup=InlineKeyboardMarkup(kb))

    elif text == "🎰 گردونه شانس":
        if not await check_membership(update, context): return
        points = get_points(uid)
        can1 = can_spin_wheel1(uid)
        can2 = points >= 3
        kb = []
        w1_prizes = " | ".join([p["name"] for p in WHEEL1_PRIZES])
        w2_prizes = " | ".join([p["name"] for p in WHEEL2_PRIZES])
        kb.append([InlineKeyboardButton("🎰 گردونه 1 - رایگان" + (" ✅" if can1 else " ⏳"), callback_data="spin_wheel1" if can1 else "wheel_locked")])
        kb.append([InlineKeyboardButton("🎰 گردونه 2 - 3 امتیاز" + (" ✅" if can2 else " 🔒" + str(points) + "/3"), callback_data="spin_wheel2" if can2 else "wheel_locked")])
        kb.append([InlineKeyboardButton("🔙 برگشت", callback_data="back_main")])
        await update.message.reply_text(
            "🎰 گردونه شانس\n\n⭐ امتیاز شما: " + str(points) + "\n\n"
            "🎰 گردونه 1 (روزانه رایگان):\n" + w1_prizes + "\n\n"
            "🎰 گردونه 2 (3 امتیاز - اعتبار):\n" + w2_prizes,
            reply_markup=InlineKeyboardMarkup(kb))

    elif text == "🎲 تاس شانس":
        if not await check_membership(update, context): return
        points = get_points(uid)
        kb = []
        if points >= 5:
            kb.append([InlineKeyboardButton("🎲 بینداز تاس! (5 امتیاز)", callback_data="roll_dice")])
        else:
            kb.append([InlineKeyboardButton("🔒 تاس نیاز به 5 امتیاز داره (" + str(points) + "/5)", callback_data="wheel_locked")])
        kb.append([InlineKeyboardButton("🔙 برگشت", callback_data="back_main")])
        await update.message.reply_text(
            "🎲 تاس شانس\n\n⭐ امتیاز شما: " + str(points) + "\n\n"
            "🎲 با انداختن تاس:\n"
            "عدد × 10,000 تومان اعتبار میگیری!\n"
            "مثلاً: 4 = 40,000 تومان اعتبار\n\nهزینه: 5 امتیاز",
            reply_markup=InlineKeyboardMarkup(kb))

    elif text == "👥 دعوت از دوستان":
        ref_link = "https://t.me/" + BOT_USERNAME + "?start=" + str(uid)
        count = get_referral_count(uid)
        earnings = get_referral_earnings(uid)
        kb = [[InlineKeyboardButton("🔙 برگشت", callback_data="back_main")]]
        await update.message.reply_text(
            "👥 سیستم دعوت از دوستان\n\n🔗 لینک دعوت شما:\n`" + ref_link + "`\n\n"
            "👤 تعداد دعوت شدگان: " + str(count) + " نفر\n"
            "💰 درآمد از دعوت: " + fmt(earnings) + " تومان\n\n"
            "📌 قوانین:\n- دعوت شونده 15% تخفیف اولین خرید\n- شما 10% از هر خرید دعوت شونده",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

    elif text == "👤 حساب من":
        wallet = get_wallet(uid)
        orders = get_order_count(uid)
        points = get_points(uid)
        ref_count = get_referral_count(uid)
        ref_link = "https://t.me/" + BOT_USERNAME + "?start=" + str(uid)
        kb = [[InlineKeyboardButton("🔙 برگشت", callback_data="back_main")]]
        await update.message.reply_text(
            "👤 حساب کاربری\n\nID: " + str(uid) + "\n💰 موجودی: " + fmt(wallet) + " تومان\n"
            "⭐ امتیاز: " + str(points) + "\n🛒 تعداد خرید: " + str(orders) + "\n"
            "👥 دعوت شدگان: " + str(ref_count) + " نفر\n\n🔗 لینک دعوت:\n`" + ref_link + "`",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

    elif text == "📋 اشتراک های من":
        rows = get_user_orders(uid)
        kb = [[InlineKeyboardButton("🔙 برگشت", callback_data="back_main")]]
        if not rows:
            await update.message.reply_text("❌ هیچ اشتراکی نداری!\n\nبرای خرید از منو اقدام کن.", reply_markup=InlineKeyboardMarkup(kb))
            return
        status_map = {"approved": "✅ فعال", "pending": "⏳ در انتظار", "rejected": "❌ رد شده"}
        msg = "📋 اشتراک های شما:\n\n"
        renew_kb = []
        for oid, plan, amount, volume_gb, used_gb, status, expire_at, config, rated, created in rows:
            msg += "سفارش #" + str(oid) + "\n📦 پلن: " + str(plan) + "\n💰 مبلغ: " + fmt(amount) + " تومان\n"
            msg += "وضعیت: " + status_map.get(status, status) + "\n"
            if volume_gb and volume_gb > 0:
                remaining = max(0, volume_gb - (used_gb or 0))
                msg += "📊 حجم: " + str(volume_gb) + "GB | مونده: " + str(round(remaining, 2)) + "GB\n"
            if expire_at:
                try:
                    exp = datetime.fromisoformat(expire_at)
                    diff = exp - datetime.now()
                    if diff.total_seconds() > 0:
                        days = diff.days
                        hours = diff.seconds // 3600
                        mins = (diff.seconds % 3600) // 60
                        msg += "⏰ انقضا: " + expire_at[:10] + "\n"
                        msg += "⏳ زمان باقیمانده: " + str(days) + " روز " + str(hours) + " ساعت " + str(mins) + " دقیقه\n"
                    else:
                        msg += "⏰ منقضی شده!\n"
                except:
                    msg += "⏰ انقضا: " + str(expire_at)[:10] + "\n"
            if status == "approved":
                renew_kb.append([InlineKeyboardButton("🔄 تمدید سفارش #" + str(oid), callback_data="renew_" + str(oid))])
            msg += "📅 خرید: " + created[:10] + "\n\n"
        kb = renew_kb + kb
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb))

    elif text == "🏆 برترین خریداران":
        top = get_top_buyers()
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        msg = "🏆 برترین خریداران\n\n"
        for i, (tid, username, total_gb, order_count) in enumerate(top):
            reward = RANK_REWARDS[i] if i < len(RANK_REWARDS) else 0
            name = "@" + str(username) if username else "کاربر " + str(tid)
            msg += medals[i] + " " + name + "\n📊 " + str(round(total_gb, 1)) + "GB | 🛒 " + str(order_count) + " خرید | 🎁 " + fmt(reward) + " تومان جایزه\n\n"
        kb = [[InlineKeyboardButton("🔙 برگشت", callback_data="back_main")]]
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb))

    elif text == "🎫 تیکت پشتیبانی":
        kb = [
            [InlineKeyboardButton("✏️ ارسال تیکت جدید", callback_data="new_ticket")],
            [InlineKeyboardButton("🔙 برگشت", callback_data="back_main")]
        ]
        await update.message.reply_text("🎫 تیکت پشتیبانی\n\nمشکلت رو اینجا گزارش بده.", reply_markup=InlineKeyboardMarkup(kb))

    elif text == "📞 پشتیبانی":
        support_text = "📞 پشتیبانی\n\nبرای ارتباط با پشتیبانی:\n"
        for s in SUPPORT_USERS:
            support_text += "👤 " + s + "\n"
        await update.message.reply_text(support_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="back_main")]]))

async def renew_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    oid = int(query.data.split("_")[1])
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT plan, amount, volume_gb FROM orders WHERE id=? AND user_id=?", (oid, uid))
    row = cur.fetchone()
    con.close()
    if not row:
        await query.answer("سفارش پیدا نشد!", show_alert=True)
        return
    plan, amount, volume_gb = row
    wallet = get_wallet(uid)
    context.user_data["selected_plan"] = plan
    context.user_data["selected_price"] = amount
    context.user_data["selected_volume_gb"] = volume_gb
    context.user_data["discount_code"] = None
    kb = []
    if wallet >= amount:
        kb.append([InlineKeyboardButton("💳 پرداخت از کیف پول", callback_data="pay_wallet")])
    kb.append([InlineKeyboardButton("💵 پرداخت کارت به کارت", callback_data="pay_card")])
    kb.append([InlineKeyboardButton("🔙 برگشت", callback_data="back_main")])
    await query.edit_message_text(
        "🔄 تمدید اشتراک\n\nپلن: " + str(plan) + "\nحجم: " + str(volume_gb) + "GB\nمبلغ: " + fmt(amount) + " تومان\n👛 موجودی: " + fmt(wallet) + " تومان\n\nروش پرداخت رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(kb))

async def panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    panel_key = query.data.split("_")[1]
    panel = PANELS[panel_key]
    context.user_data["selected_panel"] = panel_key
    avg, cnt = get_server_rating(panel_key)
    stars = "⭐" * round(avg) if avg > 0 else "بدون امتیاز"
    kb = []
    for k, p in panel["plans"].items():
        kb.append([InlineKeyboardButton(p["name"] + " - " + fmt(p["price"]) + " تومان", callback_data="plan_" + panel_key + "_" + k)])
    kb.append([InlineKeyboardButton("⚙️ انتخابی (حجم دلخواه)", callback_data="custom_plan_" + panel_key)])
    kb.append([InlineKeyboardButton("🔙 برگشت", callback_data="back_main")])
    await query.edit_message_text(
        panel["name"] + "\n" + panel["desc"] + "\n\n⭐ امتیاز سرور: " + stars + " (" + str(cnt) + " نظر)\n\n📦 پلن مورد نظرت رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(kb))

async def plan_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    panel_key = parts[1]
    plan_key = parts[2]
    panel = PANELS[panel_key]
    plan = panel["plans"][plan_key]
    uid = query.from_user.id
    wallet = get_wallet(uid)
    total = plan["price"]
    context.user_data["selected_plan"] = panel_key + "_" + plan_key
    context.user_data["selected_price"] = total
    context.user_data["selected_volume_gb"] = plan["gb"]
    context.user_data["discount_code"] = None
    ref_text = ""
    if get_order_count(uid) == 0 and get_referred_by(uid):
        total = int(total * 0.85)
        context.user_data["selected_price"] = total
        ref_text = "\n🎁 تخفیف دعوت 15% اعمال شد!"
    kb = []
    if wallet >= total:
        kb.append([InlineKeyboardButton("💳 پرداخت از کیف پول", callback_data="pay_wallet")])
    kb.append([InlineKeyboardButton("💵 پرداخت کارت به کارت", callback_data="pay_card")])
    kb.append([InlineKeyboardButton("🏷️ کد تخفیف دارم", callback_data="discount_code")])
    kb.append([InlineKeyboardButton("🔙 برگشت", callback_data="panel_" + panel_key)])
    await query.edit_message_text(
        "📋 خلاصه سفارش:\n\n🗂 پنل: " + panel["name"] + "\n📊 حجم: " + plan["name"] + "\n💰 قیمت: " + fmt(total) + " تومان" + ref_text + "\n👛 موجودی: " + fmt(wallet) + " تومان\n\nروش پرداخت رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(kb))

async def custom_plan_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    panel_key = query.data.split("_")[2]
    panel = PANELS[panel_key]
    context.user_data["selected_panel"] = panel_key
    await query.edit_message_text(
        "⚙️ خرید سفارشی - " + panel["name"] + "\n\nحداقل: " + str(panel["custom_min_gb"]) + "GB\nقیمت: " + fmt(panel["custom_price_per_gb"]) + " تومان هر گیگ\n\nمقدار گیگابایت مورد نظرت رو بنویس:")
    return WAIT_CUSTOM_GB

async def receive_custom_gb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    panel_key = context.user_data.get("selected_panel", "eco")
    panel = PANELS[panel_key]
    min_gb = panel["custom_min_gb"]
    price_per_gb = panel["custom_price_per_gb"]
    try:
        gb = int(update.message.text.strip())
        if gb < min_gb:
            await update.message.reply_text("❌ حداقل " + str(min_gb) + "GB باید باشه! دوباره وارد کن:")
            return WAIT_CUSTOM_GB
        total = gb * price_per_gb
        wallet = get_wallet(uid)
        context.user_data["selected_plan"] = panel_key + "_custom_" + str(gb) + "gb"
        context.user_data["selected_price"] = total
        context.user_data["selected_volume_gb"] = gb
        context.user_data["discount_code"] = None
        kb = []
        if wallet >= total:
            kb.append([InlineKeyboardButton("💳 پرداخت از کیف پول", callback_data="pay_wallet")])
        kb.append([InlineKeyboardButton("💵 پرداخت کارت به کارت", callback_data="pay_card")])
        kb.append([InlineKeyboardButton("🏷️ کد تخفیف دارم", callback_data="discount_code")])
        kb.append([InlineKeyboardButton("🔙 برگشت", callback_data="back_main")])
        await update.message.reply_text(
            "📋 خلاصه سفارش:\n\n🗂 پنل: " + panel["name"] + "\n📊 حجم: " + str(gb) + "GB\n💰 قیمت: " + fmt(total) + " تومان\n👛 موجودی: " + fmt(wallet) + " تومان\n\nروش پرداخت رو انتخاب کن:",
            reply_markup=InlineKeyboardMarkup(kb))
        return ConversationHandler.END
    except:
        await update.message.reply_text("❌ عدد معتبر وارد کن:")
        return WAIT_CUSTOM_GB

async def discount_code_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🏷️ کد تخفیف خودت رو وارد کن:")
    return WAIT_DISCOUNT_CODE

async def receive_discount_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip().upper()
    uid = update.effective_user.id
    percent, msg = check_discount_code(uid, code)
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
    wallet = get_wallet(uid)
    kb = []
    if wallet >= discounted:
        kb.append([InlineKeyboardButton("💳 پرداخت از کیف پول", callback_data="pay_wallet")])
    kb.append([InlineKeyboardButton("💵 پرداخت کارت به کارت", callback_data="pay_card")])
    kb.append([InlineKeyboardButton("🔙 برگشت", callback_data="back_main")])
    await update.message.reply_text(
        msg + "\n\n💰 قیمت اصلی: " + fmt(original) + " تومان\n✅ قیمت نهایی: " + fmt(discounted) + " تومان\n\nروش پرداخت:",
        reply_markup=InlineKeyboardMarkup(kb))
    return ConversationHandler.END

async def pay_card_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    price = context.user_data.get("selected_price", 0)
    context.user_data["pending_type"] = "buy"
    context.user_data["pending_price"] = price
    await query.edit_message_text(
        "💳 پرداخت کارت به کارت\n\nمبلغ: " + fmt(price) + " تومان\nشماره کارت: `" + CARD_NUMBER + "`\nبه نام: " + CARD_OWNER + "\n\nبعد از واریز عکس رسید رو اینجا بفرست 👇",
        parse_mode="Markdown")
    return WAIT_RECEIPT

async def pay_wallet_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    price = context.user_data.get("selected_price", 0)
    plan_key = context.user_data.get("selected_plan", "")
    volume_gb = context.user_data.get("selected_volume_gb", 0)
    uid = query.from_user.id
    wallet = get_wallet(uid)
    if wallet < price:
        await query.answer("موجودی کافی نیست!", show_alert=True)
        return
    discount_code = context.user_data.get("discount_code")
    if discount_code: use_discount_code(uid, discount_code)
    update_wallet(uid, -price)
    expire_at = (datetime.now() + timedelta(days=30)).isoformat()
    oid = create_order(uid, plan_key, price, "wallet", volume_gb, expire_at)
    approve_order(oid, volume_gb, expire_at)
    referrer = get_referred_by(uid)
    if referrer:
        reward = add_referral_reward(referrer, price)
        try:
            await context.bot.send_message(referrer, "🎉 یکی از دعوت شدگان شما خرید کرد!\n💰 " + fmt(reward) + " تومان اضافه شد.")
        except: pass
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(admin_id,
                "✅ خرید از کیف پول\nکاربر: " + str(uid) + "\nپلن: " + plan_key + "\nمبلغ: " + fmt(price) + " تومان\nسفارش #" + str(oid) + "\n\n"
                "برای ارسال کانفیگ: /config_" + str(oid) + "_" + str(uid))
        except: pass
    await query.edit_message_text(
        "✅ خرید موفق! 🎉\n\nسفارش #" + str(oid) + "\nانقضا: " + expire_at[:10] + "\n⭐ 1 امتیاز اضافه شد.\nکانفیگ شما به زودی ارسال میشه.",
        reply_markup=back_btn())

async def receive_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    pending_type = context.user_data.get("pending_type", "buy")
    if pending_type == "buy":
        plan_key = context.user_data.get("selected_plan", "")
        price = context.user_data.get("pending_price", 0)
        volume_gb = context.user_data.get("selected_volume_gb", 0)
        discount_code = context.user_data.get("discount_code", "")
        expire_at = (datetime.now() + timedelta(days=30)).isoformat()
        oid = create_order(user.id, plan_key, price, "receipt_sent", volume_gb, expire_at)
        if discount_code: use_discount_code(user.id, discount_code)
        caption = ("🧾 رسید جدید - سفارش #" + str(oid) + "\nکاربر: " + str(user.id) + " (@" + str(user.username) + ")\n"
                   "پلن: " + plan_key + "\nمبلغ: " + fmt(price) + " تومان\nحجم: " + str(volume_gb) + "GB\nانقضا: " + expire_at[:10] + "\n")
        if discount_code: caption += "کد تخفیف: " + discount_code + "\n"
        caption += "\n✅ تایید: /approve_" + str(oid) + "\n❌ رد: /reject_" + str(oid) + "\n📨 ارسال کانفیگ: /config_" + str(oid) + "_" + str(user.id)
    else:
        amount = context.user_data.get("topup_amount", 0)
        oid = create_order(user.id, "topup", amount, "receipt_sent", 0, None)
        caption = ("💰 شارژ کیف پول - #" + str(oid) + "\nکاربر: " + str(user.id) + " (@" + str(user.username) + ")\n"
                   "مبلغ: " + fmt(amount) + " تومان\n\n✅ تایید: /topup_approve_" + str(oid) + "_" + str(user.id) + "_" + str(amount) + "\n❌ رد: /reject_" + str(oid))
    for admin_id in ADMIN_IDS:
        try:
            if update.message.photo:
                await context.bot.send_photo(admin_id, update.message.photo[-1].file_id, caption=caption)
            else:
                await context.bot.send_message(admin_id, "⚠️ رسید بدون عکس\n" + caption)
        except: pass
    await update.message.reply_text("✅ رسیدت دریافت شد!\nبعد از بررسی (زیر 30 دقیقه) کانفیگت ارسال میشه. 🙏", reply_markup=main_menu())
    return ConversationHandler.END

async def topup_amount_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    amount = int(query.data.split("_")[2])
    context.user_data["topup_amount"] = amount
    context.user_data["pending_type"] = "topup"
    await query.edit_message_text(
        "💳 شارژ کیف پول\n\nمبلغ: " + fmt(amount) + " تومان\nشماره کارت: `" + CARD_NUMBER + "`\nبه نام: " + CARD_OWNER + "\n\nبعد از واریز عکس رسید رو اینجا بفرست 👇",
        parse_mode="Markdown")
    return WAIT_TOPUP_RECEIPT

async def spin_wheel1_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    if not can_spin_wheel1(uid):
        await query.answer("فردا میتونی بچرخونی! ⏳", show_alert=True)
        return
    update_wheel1_time(uid)
    await query.answer()
    prize = random.choice(WHEEL1_PRIZES)
    msg = "🎰 در حال چرخش...\n\n🎁 جایزه شما: " + prize["name"] + "\n\n"
    if prize["type"] == "none":
        msg += "😅 بدشانسی! فردا دوباره امتحان کن."
        kb = [[InlineKeyboardButton("🔙 برگشت", callback_data="back_main")]]
    elif prize["type"] == "discount":
        code = generate_wheel_code(str(prize["value"]) + "%_discount")
        msg += "🏷️ کد تخفیف " + str(prize["value"]) + "%:\n`" + code + "`\n\nاین کد رو موقع خرید وارد کن!"
        kb = [[InlineKeyboardButton("🛒 خرید VPN", callback_data="go_buy"), InlineKeyboardButton("🔙 برگشت", callback_data="back_main")]]
    else:
        msg += "📩 ادمین به زودی کانفیگت رو میفرسته."
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(admin_id, "🎰 جایزه گردونه 1\nکاربر: " + str(uid) + "\nجایزه: " + prize["name"])
            except: pass
        kb = [[InlineKeyboardButton("🔙 برگشت", callback_data="back_main")]]
    await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def spin_wheel2_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    if get_points(uid) < 3:
        await query.answer("امتیاز کافی نداری!", show_alert=True)
        return
    update_points(uid, -3)
    prize = random.choice(WHEEL2_PRIZES)
    msg = "🎰 در حال چرخش...\n\n🎁 جایزه شما: " + prize["name"] + "\n\n"
    if prize["type"] == "none":
        msg += "😅 بدشانسی! امتیاز بیشتر جمع کن."
    elif prize["type"] == "wallet":
        update_wallet(uid, prize["value"])
        msg += "✅ " + fmt(prize["value"]) + " تومان به کیف پول شما اضافه شد!"
    kb = [[InlineKeyboardButton("🔙 برگشت", callback_data="back_main")]]
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb))

async def roll_dice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    if get_points(uid) < 5:
        await query.answer("امتیاز کافی نداری!", show_alert=True)
        return
    update_points(uid, -5)
    dice_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣"]
    result = random.randint(1, 6)
    reward = result * 10000
    update_wallet(uid, reward)
    msg = ("🎲 تاس انداخته شد!\n\nنتیجه: " + dice_emojis[result-1] + "\n" +
           str(result) + " × 10,000 = " + fmt(reward) + " تومان\n\n✅ " + fmt(reward) + " تومان به کیف پول شما اضافه شد!")
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="back_main")]]))

async def wheel_locked_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("شرایط لازم رو نداری!", show_alert=True)

async def rate_server_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    oid = int(parts[2])
    rating = int(parts[3])
    uid = query.from_user.id
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT plan FROM orders WHERE id=?", (oid,))
    row = cur.fetchone()
    con.close()
    if row:
        panel = row[0].split("_")[0] if "_" in row[0] else row[0]
        con = sqlite3.connect("vpn_bot.db")
        cur = con.cursor()
        cur.execute("INSERT INTO server_ratings (order_id, user_id, panel, rating) VALUES (?,?,?,?)", (oid, uid, panel, rating))
        con.commit()
        con.close()
        mark_order_rated(oid)
    stars = "⭐" * rating
    await query.edit_message_text("✅ ممنون از نظرت!\n\nامتیاز شما: " + stars, reply_markup=back_btn())

async def go_buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = [[InlineKeyboardButton(PANELS[k]["name"], callback_data="panel_" + k)] for k in PANELS]
    kb.append([InlineKeyboardButton("🔙 برگشت", callback_data="back_main")])
    await query.edit_message_text("🛒 خرید VPN\n\nپنل مورد نظرت رو انتخاب کن:", reply_markup=InlineKeyboardMarkup(kb))

async def back_main_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✅")
    await context.bot.send_message(query.from_user.id, "یه گزینه انتخاب کن:", reply_markup=main_menu())

async def new_ticket_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🎫 تیکت جدید\n\nمشکل یا سوالت رو بنویس:")
    return WAIT_TICKET

async def receive_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    tid = create_ticket(user.id, update.message.text)
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(admin_id,
                "🎫 تیکت جدید #" + str(tid) + "\nکاربر: " + str(user.id) + " (@" + str(user.username) + ")\n"
                "پیام: " + update.message.text + "\n\nپاسخ: /tr_" + str(tid) + "_" + str(user.id))
        except: pass
    await update.message.reply_text("✅ تیکت #" + str(tid) + " ثبت شد!\nبه زودی پاسخ داده میشه.", reply_markup=back_btn())
    return ConversationHandler.END

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    tu, to_, ti, po = get_stats()
    kb = [
        [InlineKeyboardButton("📊 آمار فروش کامل", callback_data="admin_sales")],
        [InlineKeyboardButton("🏆 برترین خریداران", callback_data="admin_top")],
        [InlineKeyboardButton("📨 پیام همگانی", callback_data="admin_broadcast")],
        [InlineKeyboardButton("💬 پیام شخصی", callback_data="admin_private_msg")],
        [InlineKeyboardButton("💰 تغییر موجودی", callback_data="admin_wallet")],
        [InlineKeyboardButton("⭐ تغییر امتیاز", callback_data="admin_points")],
        [InlineKeyboardButton("⏳ سفارشات در انتظار", callback_data="admin_pending")],
        [InlineKeyboardButton("🎫 تیکت های باز", callback_data="admin_tickets")],
    ]
    await update.message.reply_text(
        "👑 پنل ادمین\n\n👤 کل کاربران: " + str(tu) + "\n🛒 کل سفارشات: " + str(to_) + "\n💰 کل درآمد: " + fmt(ti) + " تومان\n⏳ در انتظار: " + str(po),
        reply_markup=InlineKeyboardMarkup(kb))

def admin_back_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="admin_back")]])

async def admin_sales_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    today, week, month, total, top_plans = get_sales_stats()
    msg = "📊 آمار فروش کامل\n\n"
    msg += "📅 امروز: " + fmt(today[0] or 0) + " تومان (" + str(today[1]) + " سفارش)\n"
    msg += "📅 هفته: " + fmt(week[0] or 0) + " تومان (" + str(week[1]) + " سفارش)\n"
    msg += "📅 ماه: " + fmt(month[0] or 0) + " تومان (" + str(month[1]) + " سفارش)\n"
    msg += "💰 کل درآمد: " + fmt(total[0] or 0) + " تومان (" + str(total[1]) + " سفارش)\n\n"
    msg += "🔝 پرفروش‌ترین پلن‌ها:\n"
    for plan, cnt, income in top_plans:
        msg += "- " + str(plan) + ": " + str(cnt) + " بار | " + fmt(income) + " تومان\n"
    await query.edit_message_text(msg, reply_markup=admin_back_kb())

async def admin_top_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    top = get_top_buyers()
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    msg = "🏆 برترین خریداران\n\n"
    for i, (tid, username, total_gb, order_count) in enumerate(top):
        reward = RANK_REWARDS[i] if i < len(RANK_REWARDS) else 0
        name = "@" + str(username) if username else "کاربر " + str(tid)
        msg += medals[i] + " " + name + " (ID: " + str(tid) + ")\n📊 " + str(round(total_gb, 1)) + "GB | 🛒 " + str(order_count) + " خرید | 🎁 " + fmt(reward) + " تومان جایزه\n\n"
    msg += "\nبرای ارسال جایزه به رتبه‌ها: /send_rank_rewards"
    await query.edit_message_text(msg, reply_markup=admin_back_kb())

async def send_rank_rewards_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    top = get_top_buyers()
    sent = 0
    for i, (uid, username, total_gb, order_count) in enumerate(top):
        if i >= len(RANK_REWARDS): break
        reward = RANK_REWARDS[i]
        update_wallet(uid, reward)
        try:
            await context.bot.send_message(uid, "🎉 تبریک! شما رتبه " + str(i+1) + " برترین خریداران هستید!\n💰 " + fmt(reward) + " تومان جایزه به کیف پول شما اضافه شد.")
            sent += 1
        except: pass
    await update.message.reply_text("✅ جوایز به " + str(sent) + " نفر ارسال شد.")

async def admin_broadcast_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    await query.edit_message_text("📨 پیام همگانی\n\nمتن پیام رو بفرست:", reply_markup=admin_back_kb())
    return WAIT_BROADCAST

async def receive_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return ConversationHandler.END
    users = get_all_users()
    success = 0
    fail = 0
    for uid in users:
        try:
            await context.bot.send_message(uid, "📢 پیام از طرف مدیریت:\n\n" + update.message.text)
            success += 1
        except: fail += 1
    await update.message.reply_text("✅ پیام همگانی ارسال شد!\n\nموفق: " + str(success) + "\nناموفق: " + str(fail))
    return ConversationHandler.END

async def admin_private_msg_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    await query.edit_message_text("💬 پیام شخصی\n\nآیدی عددی کاربر رو بفرست:", reply_markup=admin_back_kb())
    return WAIT_PRIVATE_MSG_USER

async def receive_private_msg_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return ConversationHandler.END
    try:
        uid = int(update.message.text.strip())
        context.user_data["private_msg_target"] = uid
        await update.message.reply_text("متن پیام رو بفرست:")
        return WAIT_PRIVATE_MSG_TEXT
    except:
        await update.message.reply_text("❌ آیدی نامعتبر!")
        return ConversationHandler.END

async def receive_private_msg_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return ConversationHandler.END
    uid = context.user_data.get("private_msg_target")
    try:
        await context.bot.send_message(uid, "📩 پیام از طرف مدیریت:\n\n" + update.message.text)
        await update.message.reply_text("✅ پیام به کاربر " + str(uid) + " ارسال شد.")
    except:
        await update.message.reply_text("❌ ارسال ناموفق!")
    return ConversationHandler.END

async def admin_wallet_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return ConversationHandler.END
    await query.edit_message_text("💰 تغییر موجودی\n\nآیدی عددی کاربر رو بفرست:\n(برای انصراف /cancel بزن)", reply_markup=admin_back_kb())
    return WAIT_ADMIN_WALLET

async def receive_admin_wallet_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return ConversationHandler.END
    try:
        uid = int(update.message.text.strip())
        context.user_data["admin_target_user"] = uid
        await update.message.reply_text("کاربر " + str(uid) + "\n💰 موجودی فعلی: " + fmt(get_wallet(uid)) + " تومان\n\nمبلغ رو وارد کن (منفی برای کسر):")
        return WAIT_ADMIN_WALLET_AMOUNT
    except:
        await update.message.reply_text("❌ آیدی نامعتبر!")
        return ConversationHandler.END

async def receive_admin_wallet_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return ConversationHandler.END
    try:
        amount = int(update.message.text.strip())
        uid = context.user_data["admin_target_user"]
        update_wallet(uid, amount)
        new_wallet = get_wallet(uid)
        action = "اضافه" if amount > 0 else "کسر"
        try:
            await context.bot.send_message(uid, "💰 موجودی کیف پول شما " + action + " شد.\nموجودی جدید: " + fmt(new_wallet) + " تومان")
        except: pass
        await update.message.reply_text("✅ " + fmt(abs(amount)) + " تومان " + action + " شد.\nموجودی جدید: " + fmt(new_wallet) + " تومان")
    except:
        await update.message.reply_text("❌ مبلغ نامعتبر!")
    return ConversationHandler.END

async def admin_points_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return ConversationHandler.END
    await query.edit_message_text("⭐ تغییر امتیاز\n\nآیدی عددی کاربر رو بفرست:\n(برای انصراف /cancel بزن)", reply_markup=admin_back_kb())
    return WAIT_ADMIN_POINTS

async def receive_admin_points_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return ConversationHandler.END
    try:
        uid = int(update.message.text.strip())
        context.user_data["admin_target_user"] = uid
        await update.message.reply_text("کاربر " + str(uid) + "\n⭐ امتیاز فعلی: " + str(get_points(uid)) + "\n\nمقدار امتیاز رو وارد کن (منفی برای کسر):")
        return WAIT_ADMIN_POINTS_AMOUNT
    except:
        await update.message.reply_text("❌ آیدی نامعتبر!")
        return ConversationHandler.END

async def receive_admin_points_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return ConversationHandler.END
    try:
        amount = int(update.message.text.strip())
        uid = context.user_data["admin_target_user"]
        update_points(uid, amount)
        new_points = get_points(uid)
        action = "اضافه" if amount > 0 else "کسر"
        try:
            await context.bot.send_message(uid, "⭐ امتیاز شما " + action + " شد.\nامتیاز جدید: " + str(new_points))
        except: pass
        await update.message.reply_text("✅ " + str(abs(amount)) + " امتیاز " + action + " شد.\nامتیاز جدید: " + str(new_points))
    except:
        await update.message.reply_text("❌ مقدار نامعتبر!")
    return ConversationHandler.END

async def admin_config_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return ConversationHandler.END
    parts = update.message.text.split("_")
    if len(parts) < 3: return ConversationHandler.END
    oid = int(parts[1])
    uid = int(parts[2])
    context.user_data["config_order_id"] = oid
    context.user_data["config_user_id"] = uid
    await update.message.reply_text("📨 کانفیگ سفارش #" + str(oid) + " رو وارد کن:")
    return WAIT_CONFIG_TEXT

async def receive_config_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return ConversationHandler.END
    oid = context.user_data.get("config_order_id")
    uid = context.user_data.get("config_user_id")
    config = update.message.text
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("UPDATE orders SET config=? WHERE id=?", (config, oid))
    con.commit()
    con.close()
    try:
        await context.bot.send_message(uid,
            "✅ کانفیگ شما آماده شد!\n\nسفارش #" + str(oid) + "\n\n`" + config + "`",
            parse_mode="Markdown")
        await update.message.reply_text("✅ کانفیگ به کاربر " + str(uid) + " ارسال شد.")
    except:
        await update.message.reply_text("❌ ارسال ناموفق!")
    return ConversationHandler.END

async def admin_pending_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT id, user_id, plan, amount FROM orders WHERE status='pending' ORDER BY id DESC LIMIT 10")
    rows = cur.fetchall()
    con.close()
    if not rows:
        await query.edit_message_text("✅ هیچ سفارش در انتظاری نداری!", reply_markup=admin_back_kb())
        return
    text = "⏳ سفارشات در انتظار:\n\n"
    for oid, uid, plan, amount in rows:
        text += "#" + str(oid) + " - " + str(uid) + " - " + str(plan) + " - " + fmt(amount) + " تومان\n"
        text += "✅ /approve_" + str(oid) + "  ❌ /reject_" + str(oid) + "  📨 /config_" + str(oid) + "_" + str(uid) + "\n\n"
    await query.edit_message_text(text, reply_markup=admin_back_kb())

async def admin_tickets_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    tickets = get_open_tickets()
    if not tickets:
        await query.edit_message_text("✅ هیچ تیکت بازی نداری!", reply_markup=admin_back_kb())
        return
    text = "🎫 تیکت های باز:\n\n"
    for tid, uid, message, created in tickets:
        text += "#" + str(tid) + " - کاربر " + str(uid) + "\n" + message[:60] + "\nپاسخ: /tr_" + str(tid) + "_" + str(uid) + "\n\n"
    await query.edit_message_text(text, reply_markup=admin_back_kb())

async def admin_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    tu, to_, ti, po = get_stats()
    kb = [
        [InlineKeyboardButton("📊 آمار فروش کامل", callback_data="admin_sales")],
        [InlineKeyboardButton("🏆 برترین خریداران", callback_data="admin_top")],
        [InlineKeyboardButton("📨 پیام همگانی", callback_data="admin_broadcast")],
        [InlineKeyboardButton("💬 پیام شخصی", callback_data="admin_private_msg")],
        [InlineKeyboardButton("💰 تغییر موجودی", callback_data="admin_wallet")],
        [InlineKeyboardButton("⭐ تغییر امتیاز", callback_data="admin_points")],
        [InlineKeyboardButton("⏳ سفارشات در انتظار", callback_data="admin_pending")],
        [InlineKeyboardButton("🎫 تیکت های باز", callback_data="admin_tickets")],
    ]
    await query.edit_message_text(
        "👑 پنل ادمین\n\n👤 کل کاربران: " + str(tu) + "\n🛒 کل سفارشات: " + str(to_) + "\n💰 کل درآمد: " + fmt(ti) + " تومان\n⏳ در انتظار: " + str(po),
        reply_markup=InlineKeyboardMarkup(kb))

async def admin_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    oid = int(update.message.text.split("_")[1])
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT user_id, plan, amount, volume_gb, expire_at FROM orders WHERE id=?", (oid,))
    row = cur.fetchone()
    con.close()
    if not row:
        await update.message.reply_text("❌ سفارش پیدا نشد!")
        return
    uid, plan_key, amount, volume_gb, expire_at = row
    approve_order(oid, volume_gb, expire_at)
    referrer = get_referred_by(uid)
    if referrer:
        reward = add_referral_reward(referrer, amount)
        try:
            await context.bot.send_message(referrer, "🎉 یکی از دعوت شدگان شما خرید کرد!\n💰 " + fmt(reward) + " تومان اضافه شد.")
        except: pass
    try:
        await context.bot.send_message(uid,
            "✅ پرداخت تایید شد! 🎉\n\nپلن: " + str(plan_key) + "\nمبلغ: " + fmt(amount) + " تومان\n"
            "انقضا: " + (expire_at[:10] if expire_at else "نامشخص") + "\n⭐ 1 امتیاز اضافه شد.\n\n"
            "کانفیگ شما به زودی ارسال میشه.\nسفارش #" + str(oid))
    except: pass
    await update.message.reply_text("✅ سفارش #" + str(oid) + " تایید شد.\n\n📨 برای ارسال کانفیگ: /config_" + str(oid) + "_" + str(uid))

async def admin_topup_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    parts = update.message.text.split("_")
    oid, uid, amount = int(parts[2]), int(parts[3]), int(parts[4])
    approve_order(oid)
    update_wallet(uid, amount)
    try:
        await context.bot.send_message(uid, "✅ " + fmt(amount) + " تومان به کیف پول شما اضافه شد 💰\nموجودی جدید: " + fmt(get_wallet(uid)) + " تومان")
    except: pass
    await update.message.reply_text("✅ " + fmt(amount) + " تومان به کاربر " + str(uid) + " اضافه شد.")

async def admin_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
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
        except: pass
    await update.message.reply_text("❌ سفارش #" + str(oid) + " رد شد.")

async def ticket_reply_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return ConversationHandler.END
    parts = update.message.text.split("_")
    if len(parts) < 3: return ConversationHandler.END
    context.user_data["ticket_reply_id"] = int(parts[1])
    context.user_data["ticket_reply_user"] = int(parts[2])
    await update.message.reply_text("متن پاسخ رو بفرست:")
    return WAIT_TICKET_REPLY_TEXT

async def receive_ticket_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return ConversationHandler.END
    tid = context.user_data.get("ticket_reply_id")
    uid = context.user_data.get("ticket_reply_user")
    close_ticket(tid)
    try:
        await context.bot.send_message(uid, "📩 پاسخ تیکت #" + str(tid) + ":\n\n" + update.message.text)
        await update.message.reply_text("✅ پاسخ ارسال و تیکت بسته شد.")
    except:
        await update.message.reply_text("❌ ارسال ناموفق!")
    return ConversationHandler.END

async def check_expiry_job(context: ContextTypes.DEFAULT_TYPE):
    orders = get_expiring_orders()
    now = datetime.now()
    for row in orders:
        oid, uid, expire_at, plan, rated, n5d, n3d, n1d, n1h, nexp = row
        try:
            exp = datetime.fromisoformat(expire_at)
            diff = exp - now
            secs = diff.total_seconds()
            if secs < 0 and not nexp:
                mark_notif(oid, "notif_exp")
                try:
                    await context.bot.send_message(uid, "❌ اشتراک شما منقضی شد!\nسفارش #" + str(oid) + "\n\nبرای تمدید از منو اقدام کن.")
                except: pass
                for admin_id in ADMIN_IDS:
                    try:
                        await context.bot.send_message(admin_id, "⚠️ اشتراک کاربر " + str(uid) + " (سفارش #" + str(oid) + ") منقضی شد.")
                    except: pass
                if not rated:
                    kb = [[InlineKeyboardButton(str(i) + "⭐", callback_data="rate_server_" + str(oid) + "_" + str(i)) for i in range(1, 6)]]
                    try:
                        await context.bot.send_message(uid, "📊 لطفاً به سرور امتیاز بده:", reply_markup=InlineKeyboardMarkup(kb))
                    except: pass
            elif 0 < secs <= 3600 and not n1h:
                mark_notif(oid, "notif_1h")
                try: await context.bot.send_message(uid, "⚠️ اشتراک شما ظرف 1 ساعت منقضی میشه!\nسفارش #" + str(oid))
                except: pass
            elif 0 < secs <= 86400 and not n1d:
                mark_notif(oid, "notif_1d")
                try: await context.bot.send_message(uid, "⏰ فردا اشتراک شما منقضی میشه!\nسفارش #" + str(oid))
                except: pass
            elif 0 < secs <= 259200 and not n3d:
                mark_notif(oid, "notif_3d")
                try: await context.bot.send_message(uid, "⏰ 3 روز تا انقضای اشتراک شما.\nسفارش #" + str(oid))
                except: pass
            elif 0 < secs <= 432000 and not n5d:
                mark_notif(oid, "notif_5d")
                try: await context.bot.send_message(uid, "⏰ 5 روز تا انقضای اشتراک شما.\nسفارش #" + str(oid))
                except: pass
        except: pass

async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ عملیات لغو شد.", reply_markup=main_menu())
    return ConversationHandler.END

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
            CallbackQueryHandler(admin_points_callback,      pattern="^admin_points$"),
            CallbackQueryHandler(admin_private_msg_callback, pattern="^admin_private_msg$"),
            CallbackQueryHandler(new_ticket_callback,        pattern="^new_ticket$"),
            CallbackQueryHandler(custom_plan_callback,       pattern="^custom_plan_"),
            MessageHandler(filters.Regex(r"^/tr_\d+_\d+$"),        ticket_reply_cmd),
            MessageHandler(filters.Regex(r"^/config_\d+_\d+$"),    admin_config_cmd),
        ],
        states={
            WAIT_RECEIPT:             [MessageHandler(filters.PHOTO | filters.TEXT & ~filters.COMMAND, receive_receipt)],
            WAIT_TOPUP_RECEIPT:       [MessageHandler(filters.PHOTO | filters.TEXT & ~filters.COMMAND, receive_receipt)],
            WAIT_DISCOUNT_CODE:       [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_discount_code)],
            WAIT_BROADCAST:           [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_broadcast)],
            WAIT_ADMIN_WALLET:        [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_admin_wallet_user)],
            WAIT_ADMIN_WALLET_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_admin_wallet_amount)],
            WAIT_ADMIN_POINTS:        [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_admin_points_user)],
            WAIT_ADMIN_POINTS_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_admin_points_amount)],
            WAIT_PRIVATE_MSG_USER:    [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_private_msg_user)],
            WAIT_PRIVATE_MSG_TEXT:    [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_private_msg_text)],
            WAIT_TICKET:              [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_ticket)],
            WAIT_TICKET_REPLY_TEXT:   [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_ticket_reply)],
            WAIT_CUSTOM_GB:           [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_custom_gb)],
            WAIT_CONFIG_TEXT:         [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_config_text)],
        },
        fallbacks=[CommandHandler("start", start), CommandHandler("cancel", cancel_cmd)],
        per_message=False,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("cancel", cancel_cmd))
    app.add_handler(CommandHandler("send_rank_rewards", send_rank_rewards_cmd))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(check_join_callback,      pattern="^check_join$"))
    app.add_handler(CallbackQueryHandler(panel_callback,           pattern="^panel_"))
    app.add_handler(CallbackQueryHandler(plan_callback,            pattern="^plan_"))
    app.add_handler(CallbackQueryHandler(renew_callback,           pattern="^renew_"))
    app.add_handler(CallbackQueryHandler(pay_wallet_callback,      pattern="^pay_wallet$"))
    app.add_handler(CallbackQueryHandler(spin_wheel1_callback,     pattern="^spin_wheel1$"))
    app.add_handler(CallbackQueryHandler(spin_wheel2_callback,     pattern="^spin_wheel2$"))
    app.add_handler(CallbackQueryHandler(roll_dice_callback,       pattern="^roll_dice$"))
    app.add_handler(CallbackQueryHandler(wheel_locked_callback,    pattern="^wheel_locked$"))
    app.add_handler(CallbackQueryHandler(rate_server_callback,     pattern="^rate_server_"))
    app.add_handler(CallbackQueryHandler(go_buy_callback,          pattern="^go_buy$"))
    app.add_handler(CallbackQueryHandler(back_main_callback,       pattern="^back_main$"))
    app.add_handler(CallbackQueryHandler(admin_sales_callback,     pattern="^admin_sales$"))
    app.add_handler(CallbackQueryHandler(admin_top_callback,       pattern="^admin_top$"))
    app.add_handler(CallbackQueryHandler(admin_pending_callback,   pattern="^admin_pending$"))
    app.add_handler(CallbackQueryHandler(admin_tickets_callback,   pattern="^admin_tickets$"))
    app.add_handler(CallbackQueryHandler(admin_back_callback,      pattern="^admin_back$"))

    KEYBOARD_BUTTONS = "^(🛒 خرید VPN|🎁 تست رایگان|💰 افزایش موجودی|🎰 گردونه شانس|🎲 تاس شانس|👥 دعوت از دوستان|👤 حساب من|📋 اشتراک های من|🏆 برترین خریداران|🎫 تیکت پشتیبانی|📞 پشتیبانی)$"
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(KEYBOARD_BUTTONS), keyboard_handler))
    app.add_handler(MessageHandler(filters.Regex(r"^/approve_\d+$"),               admin_approve))
    app.add_handler(MessageHandler(filters.Regex(r"^/topup_approve_\d+_\d+_\d+$"), admin_topup_approve))
    app.add_handler(MessageHandler(filters.Regex(r"^/reject_\d+$"),                admin_reject))

    app.job_queue.run_repeating(check_expiry_job, interval=3600, first=60)

    print("✅ بات در حال اجراست...")
    app.run_polling()

if __name__ == "__main__":
    main()
