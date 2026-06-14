import os
import logging
import sqlite3
import random
import string
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

# ========== تنظیمات اولیه ==========
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable not set!")

CHANNEL_ID = @VPN_IRONMAN
ADMIN_PASSWORD = "ALIASMARDAN"
ADMIN_IDS = []
CARD_NUMBER = "6219-8619-2847-2389"
CARD_OWNER = "ایران بوصیدی"
BOT_USERNAME = "MARDAN_VPN_BOT"
SUPPORT_USERS = ["@Ali2011Ali2011_Ali", "@MARDAN_CORE"]

# ========== تنظیمات قفل فروش ==========
SHOP_OPEN = False
SHOP_CLOSE_DATE = "۱۴۰۵/۰۴/۰۵"

SHOP_CLOSED_MESSAGE = """
🔒 **فروش به طور موقت متوقف شده است**

📅 تاریخ بازگشایی فروش: **{date}**

🎁 **خدمات فعال در این دوره:**
• 👥 دعوت از دوستان (دریافت کانفیگ رایگان)
• 🎁 کانفیگ‌های رایگان من
• 🎫 تیکت پشتیبانی
• 📞 ارتباط با پشتیبانی

📌 با دعوت دوستانت کانفیگ نامحدود ۱ روزه رایگان بگیر!
"""

# ========== تنظیمات جایزه دعوت ==========
REFERRAL_REWARD = {
    "points_needed": 1,
    "days": 1,
    "name": "🎁 کانفیگ رایگان - نامحدود ۱ روزه"
}

# ========== پنل‌ها ==========
PANELS = {
    "eco": {
        "name": "💚 پنل اقتصادی",
        "desc": "تک کاربره - سرورهای متوسط رو به بالا",
        "plans": {
            "50gb": {"name": "50GB", "gb": 50, "price": 75000},
            "100gb": {"name": "100GB", "gb": 100, "price": 150000},
            "150gb": {"name": "150GB", "gb": 150, "price": 225000},
            "200gb": {"name": "200GB", "gb": 200, "price": 300000},
            "unlimited": {"name": "نامحدود (1.5TB)", "gb": -1, "price": 800000},
        },
        "custom_min_gb": 20,
        "custom_price_per_gb": 1500,
    },
    "pro": {
        "name": "💙 پنل قوی",
        "desc": "دو کاربره - سرورهای قدرتمندتر",
        "plans": {
            "50gb": {"name": "50GB", "gb": 50, "price": 100000},
            "100gb": {"name": "100GB", "gb": 100, "price": 200000},
            "150gb": {"name": "150GB", "gb": 150, "price": 300000},
            "200gb": {"name": "200GB", "gb": 200, "price": 350000},
            "unlimited": {"name": "نامحدود (2TB)", "gb": -1, "price": 1000000},
        },
        "custom_min_gb": 10,
        "custom_price_per_gb": 2000,
    },
    "trade": {
        "name": "🟡 پنل ترید",
        "desc": "آی‌پی ثابت - پینگ پایین",
        "plans": {
            "50gb": {"name": "50GB", "gb": 50, "price": 150000},
            "100gb": {"name": "100GB", "gb": 100, "price": 300000},
            "150gb": {"name": "150GB", "gb": 150, "price": 450000},
            "200gb": {"name": "200GB", "gb": 200, "price": 600000},
            "unlimited": {"name": "نامحدود (1TB)", "gb": -1, "price": 1500000},
        },
        "custom_min_gb": 8,
        "custom_price_per_gb": 5000,
    },
    "game": {
        "name": "🔴 پنل گیمینگ",
        "desc": "مخصوص گیم - پینگ 50 تا 100 تضمینی",
        "plans": {
            "50gb": {"name": "50GB", "gb": 50, "price": 250000},
            "100gb": {"name": "100GB", "gb": 100, "price": 500000},
            "150gb": {"name": "150GB", "gb": 150, "price": 750000},
            "200gb": {"name": "200GB", "gb": 200, "price": 1000000},
            "unlimited": {"name": "نامحدود (1TB)", "gb": -1, "price": 2500000},
        },
        "custom_min_gb": 5,
        "custom_price_per_gb": 8000,
    },
}

DISCOUNT_CODES = {
    "INYAS": {"percent": 25, "first_only": False},
    "MARDAN": {"percent": 100, "first_only": True},
}

# ========== حالت‌های مکالمه ==========
WAIT_RECEIPT, WAIT_TOPUP_RECEIPT, WAIT_DISCOUNT_CODE, WAIT_BROADCAST = 1,2,3,4
WAIT_ADMIN_WALLET, WAIT_ADMIN_WALLET_AMOUNT, WAIT_PRIVATE_MSG_USER, WAIT_PRIVATE_MSG_TEXT = 5,6,7,8
WAIT_TICKET, WAIT_TICKET_REPLY_TEXT, WAIT_CUSTOM_GB = 9,10,11
WAIT_ADMIN_PASSWORD, WAIT_CONFIG_NAME, WAIT_CONFIG_LINK = 20,21,22
WAIT_NEW_BUTTON, WAIT_NEW_PANEL, WAIT_EDIT_CONFIG = 23,24,25

logging.basicConfig(level=logging.INFO)

def fmt(n):
    try:
        return "{:,}".format(int(n))
    except:
        return str(n)

def back_btn():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="back_main")]])

def admin_back_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="admin_back")]])

def is_shop_open():
    return SHOP_OPEN

def get_db():
    db_path = "/tmp/vpn_bot.db"
    return sqlite3.connect(db_path)

def init_db():
    con = get_db()
    cur = con.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, wallet INTEGER DEFAULT 0,
            order_count INTEGER DEFAULT 0, points INTEGER DEFAULT 0, referred_by INTEGER DEFAULT NULL,
            referral_points INTEGER DEFAULT 0, used_points INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, plan TEXT, amount INTEGER,
            volume_gb REAL DEFAULT 0, used_gb REAL DEFAULT 0, status TEXT DEFAULT 'pending',
            receipt TEXT, expire_at TEXT DEFAULT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS user_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, config_link TEXT,
            config_name TEXT, days INTEGER, expire_at TEXT, is_used INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS static_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, config_link TEXT,
            is_active INTEGER DEFAULT 1, created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS menu_buttons (
            id INTEGER PRIMARY KEY AUTOINCREMENT, button_text TEXT UNIQUE,
            is_active INTEGER DEFAULT 1, position INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS discount_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, code TEXT, used_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT, referrer_id INTEGER, referred_id INTEGER,
            reward INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, message TEXT,
            status TEXT DEFAULT 'open', created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER,
            notif_5d INTEGER DEFAULT 0, notif_3d INTEGER DEFAULT 0,
            notif_1d INTEGER DEFAULT 0, notif_1h INTEGER DEFAULT 0, notif_exp INTEGER DEFAULT 0
        );
    """)
    
    default_buttons = [
        ("🛒 خرید VPN", 1), ("🎁 تست رایگان", 2), ("💰 افزایش موجودی", 3),
        ("👥 دعوت از دوستان", 4), ("👤 حساب من", 5),
        ("📋 اشتراک های من", 6), ("🎫 تیکت پشتیبانی", 7), ("📞 پشتیبانی", 8)
    ]
    for btn, pos in default_buttons:
        cur.execute("INSERT OR IGNORE INTO menu_buttons (button_text, position, is_active) VALUES (?,?,1)", (btn, pos))
    con.commit()
    con.close()

def get_active_menu():
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT button_text FROM menu_buttons WHERE is_active=1 ORDER BY position")
    buttons = cur.fetchall()
    con.close()
    
    if not is_shop_open():
        allowed_buttons = ["👥 دعوت از دوستان", "📋 اشتراک های من", "🎫 تیکت پشتیبانی", "📞 پشتیبانی", "👤 حساب من"]
        buttons = [(btn,) for btn in allowed_buttons if btn in [b[0] for b in buttons]]
    
    keyboard = []
    row = []
    for (btn_text,) in buttons:
        row.append(KeyboardButton(btn_text))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def ensure_user(uid, username, referred_by=None):
    con = get_db()
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
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT wallet FROM users WHERE user_id=?", (uid,))
    row = cur.fetchone()
    con.close()
    return row[0] if row else 0

def update_wallet(uid, amount):
    con = get_db()
    cur = con.cursor()
    cur.execute("UPDATE users SET wallet = wallet + ? WHERE user_id=?", (amount, uid))
    con.commit()
    con.close()

def get_referral_count(uid):
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=?", (uid,))
    row = cur.fetchone()
    con.close()
    return row[0] if row else 0

def get_order_count(uid):
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT order_count FROM users WHERE user_id=?", (uid,))
    row = cur.fetchone()
    con.close()
    return row[0] if row else 0

def create_order(uid, plan, amount, receipt, volume_gb=0, expire_at=None):
    con = get_db()
    cur = con.cursor()
    cur.execute("INSERT INTO orders (user_id, plan, amount, volume_gb, expire_at, receipt) VALUES (?,?,?,?,?,?)",
                (uid, plan, amount, volume_gb, expire_at, receipt))
    oid = cur.lastrowid
    cur.execute("INSERT INTO notifications (order_id) VALUES (?)", (oid,))
    con.commit()
    con.close()
    return oid

def approve_order(oid, volume_gb=0, expire_at=None):
    con = get_db()
    cur = con.cursor()
    if expire_at:
        cur.execute("UPDATE orders SET status='approved', volume_gb=?, expire_at=? WHERE id=?", (volume_gb, expire_at, oid))
    else:
        cur.execute("UPDATE orders SET status='approved' WHERE id=?", (oid,))
    cur.execute("SELECT user_id, amount FROM orders WHERE id=?", (oid,))
    row = cur.fetchone()
    if row:
        cur.execute("UPDATE users SET order_count = order_count + 1 WHERE user_id=?", (row[0],))
    con.commit()
    con.close()
    return row

def get_user_orders(uid):
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT id, plan, amount, volume_gb, used_gb, status, expire_at, created_at FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10", (uid,))
    rows = cur.fetchall()
    con.close()
    return rows

def get_all_users():
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT user_id FROM users")
    rows = cur.fetchall()
    con.close()
    return [r[0] for r in rows]

def get_stats():
    con = get_db()
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

def create_ticket(uid, message):
    con = get_db()
    cur = con.cursor()
    cur.execute("INSERT INTO tickets (user_id, message) VALUES (?,?)", (uid, message))
    tid = cur.lastrowid
    con.commit()
    con.close()
    return tid

def get_open_tickets():
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT id, user_id, message, created_at FROM tickets WHERE status='open' ORDER BY id DESC LIMIT 20")
    rows = cur.fetchall()
    con.close()
    return rows

def close_ticket(tid):
    con = get_db()
    cur = con.cursor()
    cur.execute("UPDATE tickets SET status='closed' WHERE id=?", (tid,))
    con.commit()
    con.close()

def get_user_configs(uid):
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT id, config_link, config_name, days, expire_at, is_used FROM user_configs WHERE user_id=? AND is_used=0 AND expire_at > ? ORDER BY id DESC", 
                (uid, datetime.now().isoformat()))
    rows = cur.fetchall()
    con.close()
    return rows

def add_user_config(user_id, config_link, config_name, days, expire_at):
    con = get_db()
    cur = con.cursor()
    cur.execute("INSERT INTO user_configs (user_id, config_link, config_name, days, expire_at) VALUES (?,?,?,?,?)",
                (user_id, config_link, config_name, days, expire_at))
    con.commit()
    con.close()

def mark_config_used(config_id):
    con = get_db()
    cur = con.cursor()
    cur.execute("UPDATE user_configs SET is_used=1 WHERE id=?", (config_id,))
    con.commit()
    con.close()

def get_all_active_configs():
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT id, user_id, config_link, config_name, expire_at FROM user_configs WHERE is_used=0 AND expire_at > ? ORDER BY id DESC", 
                (datetime.now().isoformat(),))
    rows = cur.fetchall()
    con.close()
    return rows

def update_config_link(config_id, new_link):
    con = get_db()
    cur = con.cursor()
    cur.execute("UPDATE user_configs SET config_link=? WHERE id=?", (new_link, config_id))
    con.commit()
    con.close()

async def is_member(bot, uid):
    try:
        m = await bot.get_chat_member(CHANNEL_ID, uid)
        return m.status in ("member", "administrator", "creator")
    except:
        return False

async def check_membership(update, context):
    uid = update.effective_user.id
    if not await is_member(context.bot, uid):
        kb = [[InlineKeyboardButton("📢 عضویت در کانال", url=f"https://t.me/{str(CHANNEL_ID).lstrip('-')}")],
              [InlineKeyboardButton("✅ عضو شدم", callback_data="check_join")]]
        msg = "⚠️ برای استفاده از بات باید عضو کانال ما بشی!"
        if update.message:
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb))
        else:
            await update.callback_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb))
        return False
    return True

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
        expire_at = datetime.now() + timedelta(days=REFERRAL_REWARD["days"])
        default_link = "لینک کانفیگ را اینجا وارد کن"
        add_user_config(referred_by, default_link, REFERRAL_REWARD["name"], REFERRAL_REWARD["days"], expire_at.isoformat())
        
        try:
            await context.bot.send_message(
                referred_by,
                f"🎉 **تبریک! شما یک کانفیگ رایگان دریافت کردید!**\n\n"
                f"📦 **کانفیگ نامحدود ۱ روزه**\n"
                f"📅 انقضا: {expire_at.strftime('%Y-%m-%d %H:%M')}\n\n"
                f"🔗 منتظر بمان تا ادمین لینک کانفیگ را وارد کند.\n"
                f"بعد از وارد شدن، از منوی «🎁 کانفیگ‌های رایگان من» دریافت کن.\n\n"
                f"📌 با دعوت دوستان بیشتر، کانفیگ‌های بیشتری دریافت کن!",
                parse_mode="Markdown"
            )
        except:
            pass
        
        await update.message.reply_text(
            f"🎉 **ثبت‌نام شما با موفقیت انجام شد!**\n\n"
            f"دعوت‌کننده شما یک کانفیگ رایگان نامحدود ۱ روزه دریافت کرد.\n\n"
            f"📌 **شما هم می‌توانی دوستانت را دعوت کنی!**\n"
            f"هر دوستی که با لینک تو بیاد = ۱ کانفیگ رایگان نامحدود ۱ روزه\n\n"
            f"از منوی «👥 دعوت از دوستان» لینک خودتو دریافت کن.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"سلام {user.first_name} 👋\n\nبه بات فروش VPN خوش اومدی 🔒\nیه گزینه انتخاب کن:",
            reply_markup=get_active_menu()
        )

async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    if await is_member(context.bot, user.id):
        ensure_user(user.id, user.username)
        await query.edit_message_text("✅ عضویتت تایید شد!")
        await context.bot.send_message(user.id, "یه گزینه انتخاب کن:", reply_markup=get_active_menu())
    else:
        await query.answer("هنوز عضو نشدی!", show_alert=True)

async def referral_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ref_link = f"https://t.me/{BOT_USERNAME}?start={uid}"
    count = get_referral_count(uid)
    configs = get_user_configs(uid)
    
    kb = [
        [InlineKeyboardButton("🔗 کپی لینک دعوت", callback_data="copy_ref_link")],
        [InlineKeyboardButton("🎁 کانفیگ‌های رایگان من", callback_data="my_reward_configs")],
        [InlineKeyboardButton("🔙 برگشت", callback_data="back_main")]
    ]
    
    await update.message.reply_text(
        f"👥 **سیستم دعوت از دوستان**\n\n"
        f"🔗 لینک دعوت شما:\n`{ref_link}`\n\n"
        f"📊 **آمار شما:**\n"
        f"👤 دعوت شدگان: {count} نفر\n"
        f"🎁 کانفیگ فعال: {len(configs)} عدد\n\n"
        f"🎯 **قوانین:**\n"
        f"• هر دوستی که با لینک تو ثبت‌نام کنه = ۱ کانفیگ رایگان\n"
        f"• حجم: **نامحدود**\n"
        f"• مدت: **۱ روزه**\n\n"
        f"🔥 هرچه دوست بیشتر = کانفیگ بیشتر!",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def copy_ref_link_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    ref_link = f"https://t.me/{BOT_USERNAME}?start={uid}"
    await query.answer(f"لینک کپی شد: {ref_link}", show_alert=True)

async def my_reward_configs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT id, config_link, config_name, days, expire_at, is_used FROM user_configs WHERE user_id=? ORDER BY id DESC", (uid,))
    configs = cur.fetchall()
    con.close()
    
    if not configs:
        await query.edit_message_text(
            "📭 **کانفیگ‌های رایگان شما**\n\n"
            "شما هنوز هیچ کانفیگ رایگانی دریافت نکرده‌اید.\n\n"
            "🎁 با دعوت دوستانت، کانفیگ نامحدود ۱ روزه دریافت کن!",
            parse_mode="Markdown",
            reply_markup=back_btn()
        )
        return
    
    text = "🎁 **کانفیگ‌های رایگان شما**\n\n"
    kb = []
    
    for idx, (cid, link, name, days, expire_at, is_used) in enumerate(configs, 1):
        expire_date = datetime.fromisoformat(expire_at)
        remaining_hours = int((expire_date - datetime.now()).total_seconds() / 3600)
        
        if expire_date < datetime.now():
            status = "⏰ منقضی شده"
        elif is_used:
            status = "✅ استفاده شده"
        else:
            if link == "لینک کانفیگ را اینجا وارد کن":
                status = "⏳ در انتظار لینک از سمت ادمین"
            else:
                status = f"🟢 فعال - {remaining_hours} ساعت باقی"
                text += f"{idx}. {name}\n   📅 {status}\n   🔗 `{link[:50]}...`\n\n"
                kb.append([InlineKeyboardButton(f"📥 دریافت کانفیگ #{idx}", callback_data=f"get_reward_config_{cid}")])
    
    if not kb:
        text += "❌ هیچ کانفیگ فعالی ندارید!\n\nبا دعوت دوستان جدید، کانفیگ رایگان دریافت کنید."
    
    kb.append([InlineKeyboardButton("🔙 برگشت", callback_data="back_main")])
    
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def get_reward_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    config_id = int(query.data.split("_")[3])
    
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT config_link, config_name, days, expire_at, is_used FROM user_configs WHERE id=? AND user_id=?", (config_id, uid))
    row = cur.fetchone()
    
    if not row:
        await query.answer("کانفیگ یافت نشد!", show_alert=True)
        return
    
    link, name, days, expire_at, is_used = row
    
    if is_used:
        await query.answer("این کانفیگ قبلاً استفاده شده!", show_alert=True)
        return
    
    expire_date = datetime.fromisoformat(expire_at)
    if expire_date < datetime.now():
        await query.answer("این کانفیگ منقضی شده است!", show_alert=True)
        return
    
    if link == "لینک کانفیگ را اینجا وارد کن":
        await query.answer("لینک کانفیگ توسط ادمین وارد نشده است! صبر کنید...", show_alert=True)
        return
    
    mark_config_used(config_id)
    con.close()
    
    await query.edit_message_text(
        f"🎁 **کانفیگ رایگان شما**\n\n"
        f"📛 {name}\n"
        f"📦 حجم: **نامحدود**\n"
        f"⏰ مدت: {days} روز\n"
        f"📅 انقضا: {expire_at[:16]}\n\n"
        f"🔗 **لینک کانفیگ:**\n`{link}`\n\n"
        f"⚠️ این لینک یکبار مصرف است.",
        parse_mode="Markdown",
        reply_markup=back_btn()
    )

async def buy_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_shop_open():
        await update.message.reply_text(SHOP_CLOSED_MESSAGE.format(date=SHOP_CLOSE_DATE), parse_mode="Markdown")
        return
    kb = [[InlineKeyboardButton(PANELS[k]["name"], callback_data="panel_" + k)] for k in PANELS]
    kb.append([InlineKeyboardButton("🔙 برگشت", callback_data="back_main")])
    await update.message.reply_text("🛒 خرید VPN\n\nپنل مورد نظر رو انتخاب کن:", reply_markup=InlineKeyboardMarkup(kb))

async def panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    panel_key = query.data.split("_")[1]
    panel = PANELS[panel_key]
    context.user_data["selected_panel"] = panel_key
    kb = []
    for k, p in panel["plans"].items():
        kb.append([InlineKeyboardButton(f"{p['name']} - {fmt(p['price'])} تومان", callback_data=f"plan_{panel_key}_{k}")])
    kb.append([InlineKeyboardButton("🔙 برگشت", callback_data="back_main")])
    await query.edit_message_text(f"{panel['name']}\n{panel['desc']}\n\n📦 پلن مورد نظرت رو انتخاب کن:", reply_markup=InlineKeyboardMarkup(kb))

async def plan_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    panel_key, plan_key = parts[1], parts[2]
    panel, plan = PANELS[panel_key], PANELS[panel_key]["plans"][plan_key]
    uid = query.from_user.id
    wallet = get_wallet(uid)
    total = plan["price"]
    context.user_data.update({"selected_plan": f"{panel_key}_{plan_key}", "selected_price": total, "selected_volume_gb": plan["gb"]})
    kb = []
    if wallet >= total:
        kb.append([InlineKeyboardButton("💳 پرداخت از کیف پول", callback_data="pay_wallet")])
    kb.append([InlineKeyboardButton("💵 پرداخت کارت به کارت", callback_data="pay_card")])
    kb.append([InlineKeyboardButton("🔙 برگشت", callback_data=f"panel_{panel_key}")])
    await query.edit_message_text(f"📋 خلاصه سفارش:\n\n🗂 پنل: {panel['name']}\n📊 حجم: {plan['name']}\n💰 قیمت: {fmt(total)} تومان\n👛 موجودی: {fmt(wallet)} تومان\n\nروش پرداخت رو انتخاب کن:", reply_markup=InlineKeyboardMarkup(kb))

async def pay_wallet_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    price = context.user_data.get("selected_price", 0)
    plan_key = context.user_data.get("selected_plan", "")
    volume_gb = context.user_data.get("selected_volume_gb", 0)
    uid = query.from_user.id
    if get_wallet(uid) < price:
        await query.answer("موجودی کافی نیست!", show_alert=True)
        return
    update_wallet(uid, -price)
    expire_at = (datetime.now() + timedelta(days=30)).isoformat()
    oid = create_order(uid, plan_key, price, "wallet", volume_gb, expire_at)
    approve_order(oid, volume_gb, expire_at)
    await query.edit_message_text(f"✅ خرید موفق! 🎉\n\nسفارش #{oid}\nانقضا: {expire_at[:10]}", reply_markup=back_btn())

async def pay_card_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    price = context.user_data.get("selected_price", 0)
    plan_key = context.user_data.get("selected_plan", "")
    volume_gb = context.user_data.get("selected_volume_gb", 0)
    expire_at = (datetime.now() + timedelta(days=30)).isoformat()
    uid = query.from_user.id
    oid = create_order(uid, plan_key, price, "waiting", volume_gb, expire_at)
    context.user_data.update({"pending_order_id": oid, "pending_price": price})
    await query.edit_message_text(f"💳 **پرداخت کارت به کارت**\n\n💰 مبلغ: {fmt(price)} تومان\n💳 شماره کارت: `{CARD_NUMBER}`\n👤 به نام: {CARD_OWNER}\n🆔 شماره سفارش: `{oid}`\n\n📸 بعد از واریز، عکس رسید رو اینجا بفرست 👇", parse_mode="Markdown")
    return WAIT_RECEIPT

async def topup_amount_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    amount = int(query.data.split("_")[2])
    uid = query.from_user.id
    oid = create_order(uid, "topup", amount, "waiting")
    context.user_data.update({"pending_order_id": oid, "topup_amount": amount})
    await query.edit_message_text(f"💰 **شارژ کیف پول**\n\n💰 مبلغ: {fmt(amount)} تومان\n💳 شماره کارت: `{CARD_NUMBER}`\n👤 به نام: {CARD_OWNER}\n🆔 شماره سفارش: `{oid}`\n\n📸 بعد از واریز، عکس رسید رو اینجا بفرست 👇", parse_mode="Markdown")
    return WAIT_TOPUP_RECEIPT

async def receive_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    oid = context.user_data.get("pending_order_id")
    
    if not oid:
        await update.message.reply_text("❌ خطا! لطفا دوباره تلاش کن.")
        return ConversationHandler.END
    
    con = get_db()
    cur = con.cursor()
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        cur.execute("UPDATE orders SET receipt=?, status='pending' WHERE id=?", (file_id, oid))
    else:
        cur.execute("UPDATE orders SET receipt=?, status='pending' WHERE id=?", (update.message.text, oid))
    con.commit()
    con.close()
    
    await update.message.reply_text("✅ **رسید شما دریافت شد!**\n\n🔍 در حال بررسی توسط ادمین...\n⏱ حداکثر ۳۰ دقیقه دیگر کانفیگ شما ارسال می‌شود.", parse_mode="Markdown", reply_markup=get_active_menu())
    return ConversationHandler.END

async def new_ticket_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🎫 **تیکت جدید**\n\nمشکل یا سوالت رو بنویس:", parse_mode="Markdown")
    return WAIT_TICKET

async def receive_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    tid = create_ticket(user.id, update.message.text)
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(admin_id, f"🎫 **تیکت جدید #{tid}**\n\n👤 کاربر: {user.id}\n📝 پیام: {update.message.text}\n\n💬 پاسخ: `/tr_{tid}_{user.id}`")
        except:
            pass
    await update.message.reply_text(f"✅ **تیکت #{tid} با موفقیت ثبت شد!**\n\nبه زودی پاسخ داده می‌شود.", parse_mode="Markdown", reply_markup=back_btn())
    return ConversationHandler.END

async def admin_panel_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in ADMIN_IDS:
        await show_admin_panel(update, context)
    else:
        await update.message.reply_text("🔐 **ورود به پنل مدیریت**\n\nرمز عبور را وارد کنید:", parse_mode="Markdown")
        return WAIT_ADMIN_PASSWORD

async def receive_admin_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.strip() == ADMIN_PASSWORD:
        uid = update.effective_user.id
        if uid not in ADMIN_IDS:
            ADMIN_IDS.append(uid)
        await show_admin_panel(update, context)
    else:
        await update.message.reply_text("❌ رمز اشتباه است!")
    return ConversationHandler.END

async def show_admin_panel(update, context):
    tu, to_, ti, po = get_stats()
    pending_orders_count = len([oid for oid, _, _, _, _ in get_pending_orders()])
    active_configs = len(get_all_active_configs())
    
    shop_status = "🔓 باز" if SHOP_OPEN else "🔒 بسته"
    
    kb = [
        [InlineKeyboardButton("📊 آمار", callback_data="admin_stats")],
        [InlineKeyboardButton("👥 کاربران", callback_data="admin_users")],
        [InlineKeyboardButton(f"🛒 سفارشات در انتظار ({pending_orders_count})", callback_data="admin_pending")],
        [InlineKeyboardButton("🎫 تیکت‌ها", callback_data="admin_tickets")],
        [InlineKeyboardButton("📨 پیام همگانی", callback_data="admin_broadcast")],
        [InlineKeyboardButton("💬 پیام شخصی", callback_data="admin_private_msg")],
        [InlineKeyboardButton("💰 مدیریت موجودی", callback_data="admin_wallet")],
        [InlineKeyboardButton(f"🔗 مدیریت کانفیگ‌ها ({active_configs})", callback_data="admin_configs")],
        [InlineKeyboardButton("🔘 مدیریت دکمه‌ها", callback_data="admin_menu")],
        [InlineKeyboardButton(f"🔓 باز/بستن فروش ({shop_status})", callback_data="admin_toggle_shop")],
        [InlineKeyboardButton("🔙 خروج", callback_data="back_main")]
    ]
    
    msg = f"👑 **پنل مدیریت**\n\n👤 کاربران: {tu}\n🛒 سفارشات تایید: {to_}\n💰 درآمد: {fmt(ti)} تومان\n⏳ در انتظار تایید: {pending_orders_count}\n🏪 فروش: {shop_status}"
    
    if isinstance(update, Update) and update.message:
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

def get_pending_orders():
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT id, user_id, plan, amount, created_at FROM orders WHERE status='pending' ORDER BY id DESC")
    rows = cur.fetchall()
    con.close()
    return rows

async def admin_toggle_shop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global SHOP_OPEN
    SHOP_OPEN = not SHOP_OPEN
    query = update.callback_query
    await query.answer(f"فروش {'باز' if SHOP_OPEN else 'بسته'} شد!")
    await show_admin_panel(update, context)

async def admin_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tu, to_, ti, po = get_stats()
    await query.edit_message_text(f"📊 **آمار کامل**\n\n👤 کاربران: {tu}\n🛒 سفارشات تایید: {to_}\n⏳ در انتظار: {po}\n💰 درآمد: {fmt(ti)} تومان", parse_mode="Markdown", reply_markup=admin_back_kb())

async def admin_users_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT user_id, username, wallet, order_count FROM users ORDER BY order_count DESC LIMIT 20")
    users = cur.fetchall()
    con.close()
    text = "👥 **لیست کاربران (۲۰ نفر برتر)**\n\n"
    for uid, username, wallet, orders in users:
        text += f"🆔 `{uid}` - @{username or 'ندارد'} - خرید: {orders} - موجودی: {fmt(wallet)}\n"
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=admin_back_kb())

async def admin_pending_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pending_orders = get_pending_orders()
    if not pending_orders:
        await query.edit_message_text("✅ هیچ سفارش در انتظاری نیست!", reply_markup=admin_back_kb())
        return
    text = "⏳ **سفارشات در انتظار تایید**\n\n"
    for oid, uid, plan, amount, created_at in pending_orders:
        text += f"🆔 #{oid} | 👤 {uid}\n📦 {plan} | 💰 {fmt(amount)} تومان\n📅 {created_at[:16]}\n✅ `/approve_{oid}` | ❌ `/reject_{oid}`\n\n"
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=admin_back_kb())

async def admin_tickets_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tickets = get_open_tickets()
    if not tickets:
        await query.edit_message_text("✅ هیچ تیکت بازی نیست!", reply_markup=admin_back_kb())
        return
    text = "🎫 **تیکت‌های باز**\n\n"
    for tid, uid, msg, created in tickets:
        text += f"🆔 #{tid} | 👤 {uid}\n📝 {msg[:50]}...\n📅 {created[:16]}\n💬 پاسخ: `/tr_{tid}_{uid}`\n\n"
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=admin_back_kb())

async def admin_broadcast_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📨 **پیام همگانی**\n\nمتن پیام رو بفرست:", parse_mode="Markdown", reply_markup=admin_back_kb())
    return WAIT_BROADCAST

async def receive_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    users = get_all_users()
    success, fail = 0, 0
    for uid in users:
        try:
            await context.bot.send_message(uid, f"📢 **پیام از مدیریت:**\n\n{text}", parse_mode="Markdown")
            success += 1
        except:
            fail += 1
    await update.message.reply_text(f"✅ **ارسال پیام همگانی**\n\n✓ موفق: {success}\n✗ ناموفق: {fail}")
    await show_admin_panel(update, context)
    return ConversationHandler.END

async def admin_private_msg_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("💬 **پیام شخصی**\n\nآیدی عددی کاربر رو بفرست:", parse_mode="Markdown", reply_markup=admin_back_kb())
    return WAIT_PRIVATE_MSG_USER

async def receive_private_msg_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        uid = int(update.message.text.strip())
        context.user_data["private_msg_target"] = uid
        await update.message.reply_text("📝 متن پیام رو بفرست:")
        return WAIT_PRIVATE_MSG_TEXT
    except:
        await update.message.reply_text("❌ آیدی نامعتبر!")
        return ConversationHandler.END

async def receive_private_msg_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = context.user_data.get("private_msg_target")
    try:
        await context.bot.send_message(uid, f"📩 **پیام از مدیریت:**\n\n{update.message.text}", parse_mode="Markdown")
        await update.message.reply_text(f"✅ پیام به کاربر `{uid}` ارسال شد.", parse_mode="Markdown")
    except:
        await update.message.reply_text("❌ ارسال ناموفق!")
    await show_admin_panel(update, context)
    return ConversationHandler.END

async def admin_wallet_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("💰 **مدیریت موجودی**\n\nآیدی عددی کاربر رو بفرست:", parse_mode="Markdown", reply_markup=admin_back_kb())
    return WAIT_ADMIN_WALLET

async def receive_admin_wallet_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        uid = int(update.message.text.strip())
        context.user_data["admin_target_user"] = uid
        await update.message.reply_text(f"👤 کاربر: `{uid}`\n💰 موجودی فعلی: `{fmt(get_wallet(uid))}` تومان\n\n➕ مبلغ مورد نظر رو وارد کن (برای کسر از منفی استفاده کن، مثال: -10000):", parse_mode="Markdown")
        return WAIT_ADMIN_WALLET_AMOUNT
    except:
        await update.message.reply_text("❌ آیدی نامعتبر!")
        return ConversationHandler.END

async def receive_admin_wallet_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = int(update.message.text.strip())
        uid = context.user_data["admin_target_user"]
        update_wallet(uid, amount)
        action = "اضافه" if amount > 0 else "کسر"
        try:
            await context.bot.send_message(uid, f"💰 موجودی کیف پول شما {action} شد.\n📊 موجودی جدید: {fmt(get_wallet(uid))} تومان")
        except:
            pass
        await update.message.reply_text(f"✅ {fmt(abs(amount))} تومان با موفقیت {action} شد.\n💰 موجودی جدید کاربر `{uid}`: {fmt(get_wallet(uid))} تومان", parse_mode="Markdown")
    except:
        await update.message.reply_text("❌ مبلغ نامعتبر!")
    await show_admin_panel(update, context)
    return ConversationHandler.END

async def admin_configs_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    configs = get_all_active_configs()
    
    if not configs:
        await query.edit_message_text("✅ هیچ کانفیگ فعالی در انتظار ویرایش نیست!", reply_markup=admin_back_kb())
        return
    
    text = "🔗 **لیست کانفیگ‌های فعال (در انتظار لینک)**\n\n"
    kb = []
    
    for cid, uid, link, name, expire_at in configs:
        text += f"🆔 #{cid} | 👤 {uid}\n📛 {name}\n📅 انقضا: {expire_at[:10]}\n🔗 `{link[:30]}...`\n\n"
        kb.append([InlineKeyboardButton(f"✏️ ویرایش کانفیگ #{cid}", callback_data=f"edit_config_{cid}")])
    
    kb.append([InlineKeyboardButton("🔙 برگشت", callback_data="admin_back")])
    
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def edit_config_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    config_id = int(query.data.split("_")[2])
    context.user_data["editing_config_id"] = config_id
    
    await query.edit_message_text(
        f"✏️ **ویرایش کانفیگ #{config_id}**\n\n"
        "لطفا لینک جدید کانفیگ نامحدود ۱ روزه را وارد کنید:\n\n"
        "مثال: `vless://example.com...`\n\n"
        "⚠️ این کانفیگ فقط برای یک بار مصرف است.",
        parse_mode="Markdown"
    )
    return WAIT_EDIT_CONFIG

async def save_edited_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config_id = context.user_data.get("editing_config_id")
    new_link = update.message.text.strip()
    
    update_config_link(config_id, new_link)
    
    # اطلاع به کاربر
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT user_id FROM user_configs WHERE id=?", (config_id,))
    user_id = cur.fetchone()[0]
    con.close()
    
    try:
        await context.bot.send_message(
            user_id,
            f"✅ **لینک کانفیگ رایگان شما آماده شد!**\n\n"
            f"🔗 از منوی «🎁 کانفیگ‌های رایگان من» می‌توانید آن را دریافت کنید.\n\n"
            f"⚠️ این لینک فقط یکبار قابل استفاده است.",
            parse_mode="Markdown"
        )
    except:
        pass
    
    await update.message.reply_text(f"✅ لینک کانفیگ #{config_id} با موفقیت به‌روزرسانی و به کاربر اعلام شد!")
    await show_admin_panel(update, context)
    return ConversationHandler.END

async def admin_menu_manager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT id, button_text, is_active FROM menu_buttons ORDER BY position")
    buttons = cur.fetchall()
    con.close()
    text = "🔘 **مدیریت دکمه‌های منو**\n\n"
    kb = []
    for bid, btn_text, is_active in buttons:
        status = "✅" if is_active else "❌"
        text += f"{status} {btn_text}\n"
        kb.append([InlineKeyboardButton(f"{'غیرفعال' if is_active else 'فعال'} کردن {btn_text}", callback_data=f"toggle_btn_{bid}")])
    kb.append([InlineKeyboardButton("🔙 برگشت", callback_data="admin_back")])
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def toggle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    btn_id = int(query.data.split("_")[2])
    con = get_db()
    cur = con.cursor()
    cur.execute("UPDATE menu_buttons SET is_active = NOT is_active WHERE id=?", (btn_id,))
    con.commit()
    con.close()
    await admin_menu_manager(update, context)

async def admin_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await show_admin_panel(update, context)

async def back_main_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✅")
    await context.bot.send_message(query.from_user.id, "یه گزینه انتخاب کن:", reply_markup=get_active_menu())

async def admin_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ شما دسترسی ادمین ندارید!")
        return
    oid = int(update.message.text.split("_")[1])
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT user_id, plan, amount, volume_gb, expire_at FROM orders WHERE id=?", (oid,))
    row = cur.fetchone()
    con.close()
    if not row:
        await update.message.reply_text("❌ سفارش پیدا نشد!")
        return
    uid, plan_key, amount, volume_gb, expire_at = row
    approve_order(oid, volume_gb, expire_at)
    try:
        await context.bot.send_message(uid, f"✅ **پرداخت شما تایید شد!** 🎉\n\n📦 پلن: {plan_key}\n💰 مبلغ: {fmt(amount)} تومان\n🆔 سفارش: #{oid}", parse_mode="Markdown")
    except:
        pass
    await update.message.reply_text(f"✅ سفارش #{oid} تایید شد.")

async def admin_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    oid = int(update.message.text.split("_")[1])
    con = get_db()
    cur = con.cursor()
    cur.execute("UPDATE orders SET status='rejected' WHERE id=?", (oid,))
    cur.execute("SELECT user_id FROM orders WHERE id=?", (oid,))
    row = cur.fetchone()
    con.commit()
    con.close()
    if row:
        try:
            await context.bot.send_message(row[0], f"❌ متاسفانه رسید سفارش #{oid} تایید نشد.\n\nلطفا با پشتیبانی تماس بگیرید.")
        except:
            pass
    await update.message.reply_text(f"❌ سفارش #{oid} رد شد.")

async def ticket_reply_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    parts = update.message.text.split("_")
    if len(parts) < 3:
        return
    tid, uid = int(parts[1]), int(parts[2])
    context.user_data.update({"ticket_reply_id": tid, "ticket_reply_user": uid})
    await update.message.reply_text(f"💬 **پاسخ به تیکت #{tid}**\n\nمتن پاسخ رو بفرست:", parse_mode="Markdown")
    return WAIT_TICKET_REPLY_TEXT

async def receive_ticket_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = context.user_data.get("ticket_reply_id")
    uid = context.user_data.get("ticket_reply_user")
    close_ticket(tid)
    try:
        await context.bot.send_message(uid, f"📩 **پاسخ تیکت #{tid}**\n\n{update.message.text}", parse_mode="Markdown")
        await update.message.reply_text(f"✅ پاسخ تیکت #{tid} ارسال شد.")
    except:
        await update.message.reply_text("❌ ارسال ناموفق!")
    return ConversationHandler.END

async def keyboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = update.effective_user.id

    if text == "🛒 خرید VPN":
        if not is_shop_open():
            await update.message.reply_text(SHOP_CLOSED_MESSAGE.format(date=SHOP_CLOSE_DATE), parse_mode="Markdown")
            return
        await buy_menu(update, context)
    
    elif text == "🎁 تست رایگان":
        await update.message.reply_text(SHOP_CLOSED_MESSAGE.format(date=SHOP_CLOSE_DATE), parse_mode="Markdown", reply_markup=back_btn())
    
    elif text == "💰 افزایش موجودی":
        if not is_shop_open():
            await update.message.reply_text(SHOP_CLOSED_MESSAGE.format(date=SHOP_CLOSE_DATE), parse_mode="Markdown")
            return
        amounts = [50000, 100000, 200000, 500000, 1000000]
        kb = [[InlineKeyboardButton(f"{fmt(a)} تومان", callback_data=f"topup_amount_{a}")] for a in amounts]
        kb.append([InlineKeyboardButton("🔙 برگشت", callback_data="back_main")])
        await update.message.reply_text("💰 **افزایش موجودی کیف پول**\n\nمبلغ مورد نظر رو انتخاب کن:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    
    elif text == "👥 دعوت از دوستان":
        await referral_menu(update, context)
    
    elif text == "👤 حساب من":
        wallet = get_wallet(uid)
        orders = get_order_count(uid)
        ref_count = get_referral_count(uid)
        configs = get_user_configs(uid)
        ref_link = f"https://t.me/{BOT_USERNAME}?start={uid}"
        
        if not is_shop_open():
            await update.message.reply_text(
                f"👤 **حساب کاربری من**\n\n"
                f"💰 موجودی کیف پول: {fmt(wallet)} تومان\n"
                f"🛒 تعداد خرید قبلی: {orders}\n"
                f"👥 تعداد دعوت: {ref_count}\n"
                f"🎁 کانفیگ فعال: {len(configs)} عدد\n\n"
                f"🔗 لینک دعوت شما:\n`{ref_link}`\n\n"
                f"🔒 **فروش تا تاریخ {SHOP_CLOSE_DATE} بسته است.**\n"
                f"💰 موجودی شما در زمان بازگشایی قابل استفاده است.\n\n"
                f"📌 با دعوت دوستانتان کانفیگ رایگان بگیرید!",
                parse_mode="Markdown",
                reply_markup=back_btn()
            )
        else:
            await update.message.reply_text(
                f"👤 **حساب کاربری من**\n\n"
                f"💰 موجودی کیف پول: {fmt(wallet)} تومان\n"
                f"🛒 تعداد خرید: {orders}\n"
                f"👥 تعداد دعوت: {ref_count}\n"
                f"🎁 کانفیگ فعال: {len(configs)} عدد\n\n"
                f"🔗 لینک دعوت شما:\n`{ref_link}`",
                parse_mode="Markdown",
                reply_markup=back_btn()
            )
    
    elif text == "📋 اشتراک های من":
        rows = get_user_orders(uid)
        if not rows:
            await update.message.reply_text("❌ **هیچ اشتراکی ندارید!**", parse_mode="Markdown", reply_markup=back_btn())
            return
        status_map = {"approved": "✅ فعال", "pending": "⏳ در انتظار تایید", "rejected": "❌ رد شده"}
        msg = "📋 **لیست اشتراک‌های من**\n\n"
        for oid, plan, amount, volume_gb, used_gb, status, expire_at, created in rows:
            msg += f"🆔 #{oid}\n📦 {plan}\n💰 {fmt(amount)} تومان\n📊 وضعیت: {status_map.get(status, status)}\n📅 تاریخ خرید: {created[:10]}\n\n"
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=back_btn())
    
    elif text == "🎫 تیکت پشتیبانی":
        kb = [[InlineKeyboardButton("✏️ ثبت تیکت جدید", callback_data="new_ticket")],
              [InlineKeyboardButton("🔙 برگشت", callback_data="back_main")]]
        await update.message.reply_text("🎫 **تیکت پشتیبانی**\n\nمشکل یا سوال خود را ثبت کنید.", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    
    elif text == "📞 پشتیبانی":
        support_text = "📞 **پشتیبانی**\n\nبرای ارتباط با پشتیبانی:\n\n" + "\n".join([f"👤 {s}" for s in SUPPORT_USERS])
        await update.message.reply_text(support_text, parse_mode="Markdown", reply_markup=back_btn())

def main():
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(pay_card_callback, pattern="^pay_card$"),
            CallbackQueryHandler(topup_amount_callback, pattern="^topup_amount_"),
            CallbackQueryHandler(admin_broadcast_callback, pattern="^admin_broadcast$"),
            CallbackQueryHandler(admin_wallet_callback, pattern="^admin_wallet$"),
            CallbackQueryHandler(admin_private_msg_callback, pattern="^admin_private_msg$"),
            CallbackQueryHandler(new_ticket_callback, pattern="^new_ticket$"),
            CallbackQueryHandler(admin_configs_menu, pattern="^admin_configs$"),
            CallbackQueryHandler(edit_config_callback, pattern="^edit_config_"),
            CommandHandler("ALIASMARDAN", admin_panel_entry),
        ],
        states={
            WAIT_RECEIPT: [MessageHandler(filters.PHOTO | filters.TEXT & ~filters.COMMAND, receive_receipt)],
            WAIT_TOPUP_RECEIPT: [MessageHandler(filters.PHOTO | filters.TEXT & ~filters.COMMAND, receive_receipt)],
            WAIT_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_broadcast)],
            WAIT_ADMIN_WALLET: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_admin_wallet_user)],
            WAIT_ADMIN_WALLET_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_admin_wallet_amount)],
            WAIT_PRIVATE_MSG_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_private_msg_user)],
            WAIT_PRIVATE_MSG_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_private_msg_text)],
            WAIT_TICKET: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_ticket)],
            WAIT_TICKET_REPLY_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_ticket_reply)],
            WAIT_ADMIN_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_admin_password)],
            WAIT_EDIT_CONFIG: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_edited_config)],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(check_join_callback, pattern="^check_join$"))
    app.add_handler(CallbackQueryHandler(panel_callback, pattern="^panel_"))
    app.add_handler(CallbackQueryHandler(plan_callback, pattern="^plan_"))
    app.add_handler(CallbackQueryHandler(pay_wallet_callback, pattern="^pay_wallet$"))
    app.add_handler(CallbackQueryHandler(copy_ref_link_callback, pattern="^copy_ref_link$"))
    app.add_handler(CallbackQueryHandler(back_main_callback, pattern="^back_main$"))
    app.add_handler(CallbackQueryHandler(admin_stats_callback, pattern="^admin_stats$"))
    app.add_handler(CallbackQueryHandler(admin_users_callback, pattern="^admin_users$"))
    app.add_handler(CallbackQueryHandler(admin_pending_callback, pattern="^admin_pending$"))
    app.add_handler(CallbackQueryHandler(admin_tickets_callback, pattern="^admin_tickets$"))
    app.add_handler(CallbackQueryHandler(admin_menu_manager, pattern="^admin_menu$"))
    app.add_handler(CallbackQueryHandler(admin_back_callback, pattern="^admin_back$"))
    app.add_handler(CallbackQueryHandler(admin_toggle_shop_callback, pattern="^admin_toggle_shop$"))
    app.add_handler(CallbackQueryHandler(toggle_button, pattern="^toggle_btn_"))
    app.add_handler(CallbackQueryHandler(my_reward_configs, pattern="^my_reward_configs$"))
    app.add_handler(CallbackQueryHandler(get_reward_config, pattern="^get_reward_config_"))

    app.add_handler(MessageHandler(filters.Regex(r"^/approve_\d+$"), admin_approve))
    app.add_handler(MessageHandler(filters.Regex(r"^/reject_\d+$"), admin_reject))
    app.add_handler(MessageHandler(filters.Regex(r"^/tr_\d+_\d+$"), ticket_reply_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, keyboard_handler))

    print("✅ بات در حال اجراست...")
    app.run_polling()

if __name__ == "__main__":
    main()