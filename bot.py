import os
import logging
import sqlite3
import random
import string
import json
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

CHANNEL_ID = -1002371447430  # آیدی عددی کانال خود را وارد کنید
ADMIN_PASSWORD = "ALIASMARDAN"
ADMIN_IDS = []  # با وارد شدن با رمز پر می‌شود
CARD_NUMBER = "6219-8619-2847-2389"
CARD_OWNER = "ایران بوصیدی"
BOT_USERNAME = "alii_nazer_bot"  # نام واقعی بات
SUPPORT_USERS = ["@Ali2011Ali2011_Ali", "@MARDAN_CORE"]

# ========== تنظیمات قفل فروش ==========
FREEZE_UNTIL = "2026-06-05"
FREEZE_MESSAGE = "🔒 فروش تا تاریخ ۵ خرداد به دلیل بروزرسانی متوقف شده.\nاز طریق بخش «👥 دعوت از دوستان» می‌تونی کانفیگ رایگان بگیری."

REFERRAL_CONFIG_REWARD = {"count": 3, "gb": 10, "days": 7}

# ========== پنل‌ها (قابل مدیریت از پنل ادمین) ==========
PANELS = {
    "eco": {
        "name": "💚 پنل اقتصادی",
        "desc": "تک کاربره - سرورهای متوسط",
        "plans": {
            "50gb": {"name": "50GB", "gb": 50, "price": 75000},
            "100gb": {"name": "100GB", "gb": 100, "price": 150000},
            "unlimited": {"name": "نامحدود", "gb": -1, "price": 800000},
        },
        "custom_min_gb": 20,
        "custom_price_per_gb": 1500,
    },
    "pro": {
        "name": "💙 پنل قوی",
        "desc": "دو کاربره - سرورهای قدرتمند",
        "plans": {
            "50gb": {"name": "50GB", "gb": 50, "price": 100000},
            "100gb": {"name": "100GB", "gb": 100, "price": 200000},
            "unlimited": {"name": "نامحدود", "gb": -1, "price": 1000000},
        },
        "custom_min_gb": 10,
        "custom_price_per_gb": 2000,
    },
}

DISCOUNT_CODES = {"INYAS": {"percent": 25, "first_only": False}}

# ========== حالت‌های مکالمه ==========
WAIT_RECEIPT, WAIT_TOPUP_RECEIPT, WAIT_DISCOUNT_CODE, WAIT_BROADCAST = 1,2,3,4
WAIT_ADMIN_WALLET, WAIT_ADMIN_WALLET_AMOUNT, WAIT_PRIVATE_MSG_USER, WAIT_PRIVATE_MSG_TEXT = 5,6,7,8
WAIT_TICKET, WAIT_TICKET_REPLY_TEXT, WAIT_CUSTOM_GB = 9,10,11
WAIT_ADMIN_PASSWORD, WAIT_CONFIG_NAME, WAIT_NEW_BUTTON, WAIT_NEW_PANEL = 20,21,22,23
WAIT_CONFIG_FOR_USER, WAIT_NEW_PLAN = 24,25

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
    try:
        freeze_date = datetime.strptime(FREEZE_UNTIL, "%Y-%m-%d")
        return datetime.now() > freeze_date
    except:
        return True

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
    # دکمه‌های پیش‌فرض
    default_buttons = [
        ("🛒 خرید VPN", 1), ("🎁 تست رایگان", 2), ("💰 افزایش موجودی", 3),
        ("🎲 تاس شانس", 4), ("👥 دعوت از دوستان", 5), ("👤 حساب من", 6),
        ("📋 اشتراک های من", 7), ("🎫 تیکت پشتیبانی", 8), ("📞 پشتیبانی", 9)
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
            cur.execute("UPDATE users SET referral_points = referral_points + 1 WHERE user_id=?", (referred_by,))
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

def get_referral_points(uid):
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT referral_points FROM users WHERE user_id=?", (uid,))
    row = cur.fetchone()
    con.close()
    return row[0] if row else 0

def use_referral_point(uid):
    con = get_db()
    cur = con.cursor()
    cur.execute("UPDATE users SET referral_points = referral_points - 1, used_points = used_points + 1 WHERE user_id=? AND referral_points > 0", (uid,))
    con.commit()
    con.close()

def get_order_count(uid):
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT order_count FROM users WHERE user_id=?", (uid,))
    row = cur.fetchone()
    con.close()
    return row[0] if row else 0

def get_referral_count(uid):
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=?", (uid,))
    row = cur.fetchone()
    con.close()
    return row[0] if row else 0

def get_referral_earnings(uid):
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT SUM(reward) FROM referrals WHERE referrer_id=?", (uid,))
    row = cur.fetchone()
    con.close()
    return row[0] or 0

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

def get_all_buyers():
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT DISTINCT user_id FROM orders WHERE status='approved'")
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

def get_static_configs():
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT id, name, config_link, is_active FROM static_configs")
    rows = cur.fetchall()
    con.close()
    return rows

def add_static_config(name, link):
    con = get_db()
    cur = con.cursor()
    cur.execute("INSERT INTO static_configs (name, config_link) VALUES (?,?)", (name, link))
    con.commit()
    con.close()

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
        msg = f"⚠️ برای استفاده از بات باید عضو کانال ما بشی!"
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
        try:
            await context.bot.send_message(referred_by, f"🎉 یه نفر با لینک دعوت شما ثبت‌نام کرد!\n⭐ ۱ امتیاز به حساب شما اضافه شد.\nاز منوی «🎲 تاس شانس» استفاده کن!")
        except:
            pass
    await update.message.reply_text(f"سلام {user.first_name} 👋\n\nبه بات فروش VPN خوش اومدی 🔒\nیه گزینه انتخاب کن:", reply_markup=get_active_menu())

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

# ========== تاس شانس ==========
async def roll_dice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    points = get_referral_points(uid)
    if points < 1:
        await query.answer("❌ امتیاز کافی نداری!\nهر دعوت = ۱ امتیاز", show_alert=True)
        return
    use_referral_point(uid)
    dice_message = await context.bot.send_dice(query.message.chat_id, emoji="🎲")
    result = dice_message.dice.value
    prize_amount = result * 10000
    update_wallet(uid, prize_amount)
    result_emojis = {1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣ 🎉", 5: "5️⃣ 🤩", 6: "6️⃣ 🎊🔥"}
    msg = (f"🎲 **تاس شانس**\n\n┏━━━━━━━━━━━━━━━━┓\n┃   {result_emojis.get(result, str(result))}   ┃\n┗━━━━━━━━━━━━━━━━┛\n\n"
           f"✨ **نتیجه: {result}**\n💰 **جایزه: {fmt(prize_amount)} تومان**\n\n⭐ امتیاز باقی‌مونده: {get_referral_points(uid)}")
    await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=back_btn())

# ========== منوی دعوت ==========
async def referral_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ref_link = f"https://t.me/{BOT_USERNAME}?start={uid}"
    count = get_referral_count(uid)
    points = get_referral_points(uid)
    kb = [[InlineKeyboardButton("🔗 کپی لینک دعوت", callback_data="copy_ref_link")],
          [InlineKeyboardButton("🔙 برگشت", callback_data="back_main")]]
    await update.message.reply_text(
        f"👥 **سیستم دعوت از دوستان**\n\n🔗 لینک دعوت شما:\n`{ref_link}`\n\n👤 دعوت شدگان: {count}\n⭐ امتیاز شما: {points}\n\nهر دعوت = ۱ امتیاز = ۱ بار تاس شانس 🎲",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def copy_ref_link_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    ref_link = f"https://t.me/{BOT_USERNAME}?start={uid}"
    await query.answer(f"لینک کپی شد: {ref_link}", show_alert=True)

# ========== خرید ==========
async def buy_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_shop_open():
        await update.message.reply_text(FREEZE_MESSAGE)
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
    context.user_data.update({"pending_type": "buy", "pending_price": price})
    await query.edit_message_text(f"💳 پرداخت کارت به کارت\n\nمبلغ: {fmt(price)} تومان\nشماره کارت: `{CARD_NUMBER}`\nبه نام: {CARD_OWNER}\n\nبعد از واریز عکس رسید رو بفرست 👇", parse_mode="Markdown")
    return WAIT_RECEIPT

async def topup_amount_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    amount = int(query.data.split("_")[2])
    context.user_data.update({"topup_amount": amount, "pending_type": "topup"})
    await query.edit_message_text(f"💳 شارژ کیف پول\n\nمبلغ: {fmt(amount)} تومان\nشماره کارت: `{CARD_NUMBER}`\nبه نام: {CARD_OWNER}\n\nبعد از واریز عکس رسید رو بفرست 👇", parse_mode="Markdown")
    return WAIT_TOPUP_RECEIPT

async def receive_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    pending_type = context.user_data.get("pending_type", "buy")
    if pending_type == "buy":
        plan_key = context.user_data.get("selected_plan", "")
        price = context.user_data.get("pending_price", 0)
        volume_gb = context.user_data.get("selected_volume_gb", 0)
        expire_at = (datetime.now() + timedelta(days=30)).isoformat()
        oid = create_order(user.id, plan_key, price, "receipt_sent", volume_gb, expire_at)
        caption = f"🧾 رسید جدید - سفارش #{oid}\nکاربر: {user.id} (@{user.username})\nپلن: {plan_key}\nمبلغ: {fmt(price)} تومان\n✅ /approve_{oid}\n❌ /reject_{oid}"
    else:
        amount = context.user_data.get("topup_amount", 0)
        oid = create_order(user.id, "topup", amount, "receipt_sent")
        caption = f"💰 شارژ کیف پول - #{oid}\nکاربر: {user.id} (@{user.username})\nمبلغ: {fmt(amount)} تومان\n✅ /topup_approve_{oid}_{user.id}_{amount}\n❌ /reject_{oid}"
    for admin_id in ADMIN_IDS:
        try:
            if update.message.photo:
                await context.bot.send_photo(admin_id, update.message.photo[-1].file_id, caption=caption)
            else:
                await context.bot.send_message(admin_id, f"⚠️ رسید بدون عکس\n{caption}")
        except:
            pass
    await update.message.reply_text("✅ رسیدت دریافت شد!\nبعد از بررسی کانفیگت ارسال میشه.", reply_markup=get_active_menu())
    return ConversationHandler.END

# ========== تیکت ==========
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
            await context.bot.send_message(admin_id, f"🎫 تیکت جدید #{tid}\nکاربر: {user.id}\nپیام: {update.message.text}\n\nپاسخ: /tr_{tid}_{user.id}")
        except:
            pass
    await update.message.reply_text(f"✅ تیکت #{tid} ثبت شد!\nبه زودی پاسخ داده میشه.", reply_markup=back_btn())
    return ConversationHandler.END

# ========== پنل ادمین ==========
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
    kb = [
        [InlineKeyboardButton("📊 آمار", callback_data="admin_stats")],
        [InlineKeyboardButton("👥 کاربران", callback_data="admin_users")],
        [InlineKeyboardButton("🛒 سفارشات در انتظار", callback_data="admin_pending")],
        [InlineKeyboardButton("🎫 تیکت‌ها", callback_data="admin_tickets")],
        [InlineKeyboardButton("📨 پیام همگانی", callback_data="admin_broadcast")],
        [InlineKeyboardButton("💬 پیام شخصی", callback_data="admin_private_msg")],
        [InlineKeyboardButton("💰 مدیریت موجودی", callback_data="admin_wallet")],
        [InlineKeyboardButton("🔗 مدیریت کانفیگ", callback_data="admin_configs")],
        [InlineKeyboardButton("🔘 مدیریت دکمه‌ها", callback_data="admin_menu")],
        [InlineKeyboardButton("📤 ارسال کانفیگ به خریداران", callback_data="admin_send_config")],
        [InlineKeyboardButton("🔙 خروج", callback_data="back_main")]
    ]
    msg = f"👑 **پنل مدیریت**\n\n👤 کاربران: {tu}\n🛒 سفارشات: {to_}\n💰 درآمد: {fmt(ti)} تومان\n⏳ در انتظار: {po}"
    if isinstance(update, Update) and update.message:
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

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
        text += f"🆔 {uid} - @{username or 'ندارد'} - خرید: {orders} - موجودی: {fmt(wallet)}\n"
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=admin_back_kb())

async def admin_pending_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT id, user_id, plan, amount FROM orders WHERE status='pending' ORDER BY id DESC")
    rows = cur.fetchall()
    con.close()
    if not rows:
        await query.edit_message_text("✅ هیچ سفارش در انتظاری نیست!", reply_markup=admin_back_kb())
        return
    text = "⏳ **سفارشات در انتظار**\n\n"
    for oid, uid, plan, amount in rows:
        text += f"#{oid} - {uid} - {plan} - {fmt(amount)} تومان\n✅ /approve_{oid} | ❌ /reject_{oid}\n\n"
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
        text += f"#{tid} - کاربر {uid}\n{msg[:50]}...\nپاسخ: /tr_{tid}_{uid}\n\n"
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
    await update.message.reply_text(f"✅ ارسال شد!\nموفق: {success}\nناموفق: {fail}")
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
        await update.message.reply_text("متن پیام رو بفرست:")
        return WAIT_PRIVATE_MSG_TEXT
    except:
        await update.message.reply_text("❌ آیدی نامعتبر!")
        return ConversationHandler.END

async def receive_private_msg_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = context.user_data.get("private_msg_target")
    try:
        await context.bot.send_message(uid, f"📩 **پیام از مدیریت:**\n\n{update.message.text}", parse_mode="Markdown")
        await update.message.reply_text(f"✅ پیام به {uid} ارسال شد.")
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
        await update.message.reply_text(f"کاربر {uid}\n💰 موجودی فعلی: {fmt(get_wallet(uid))} تومان\n\nمبلغ رو وارد کن (منفی برای کسر):")
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
            await context.bot.send_message(uid, f"💰 موجودی شما {action} شد.\nموجودی جدید: {fmt(get_wallet(uid))} تومان")
        except:
            pass
        await update.message.reply_text(f"✅ {fmt(abs(amount))} تومان {action} شد.")
    except:
        await update.message.reply_text("❌ مبلغ نامعتبر!")
    await show_admin_panel(update, context)
    return ConversationHandler.END

async def admin_configs_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    configs = get_static_configs()
    text = "🔗 **مدیریت کانفیگ‌ها**\n\n"
    for cid, name, link, active in configs:
        status = "✅ فعال" if active else "❌ غیرفعال"
        text += f"• {name} - {status}\n"
    kb = [[InlineKeyboardButton("➕ افزودن کانفیگ", callback_data="admin_add_config")],
          [InlineKeyboardButton("🔙 برگشت", callback_data="admin_back")]]
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def admin_add_config_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🔗 **افزودن کانفیگ**\n\nفرمت: `نام|لینک`\nمثال: `کانفیگ ایران|vless://example.com`", parse_mode="Markdown")
    return WAIT_CONFIG_NAME

async def receive_static_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        name, link = update.message.text.split("|", 1)
        add_static_config(name.strip(), link.strip())
        await update.message.reply_text(f"✅ کانفیگ «{name}» اضافه شد!")
    except:
        await update.message.reply_text("❌ فرمت اشتباه!")
    await show_admin_panel(update, context)
    return ConversationHandler.END

async def admin_send_config_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    configs = get_static_configs()
    if not configs:
        await query.edit_message_text("❌ هیچ کانفیگی وجود ندارد!", reply_markup=admin_back_kb())
        return
    kb = []
    for cid, name, link, active in configs:
        if active:
            kb.append([InlineKeyboardButton(f"📤 ارسال {name}", callback_data=f"send_config_{cid}")])
    kb.append([InlineKeyboardButton("🔙 برگشت", callback_data="admin_back")])
    await query.edit_message_text("📤 **ارسال کانفیگ به خریداران**\n\nکانفیگ مورد نظر را انتخاب کن:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def execute_send_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    config_id = int(query.data.split("_")[2])
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT name, config_link FROM static_configs WHERE id=?", (config_id,))
    name, link = cur.fetchone()
    buyers = get_all_buyers()
    con.close()
    success, fail = 0, 0
    for uid in buyers:
        try:
            await context.bot.send_message(uid, f"🎁 **کانفیگ جدید!**\n\n📛 {name}\n🔗 `{link}`", parse_mode="Markdown")
            success += 1
        except:
            fail += 1
    await query.edit_message_text(f"✅ ارسال شد!\nموفق: {success}\nناموفق: {fail}", reply_markup=admin_back_kb())

async def admin_menu_manager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT id, button_text, is_active FROM menu_buttons ORDER BY position")
    buttons = cur.fetchall()
    con.close()
    kb = []
    for bid, btn_text, is_active in buttons:
        status = "✅" if is_active else "❌"
        kb.append([InlineKeyboardButton(f"{status} {btn_text}", callback_data=f"toggle_btn_{bid}")])
    kb.append([InlineKeyboardButton("🔙 برگشت", callback_data="admin_back")])
    await query.edit_message_text("🔘 **مدیریت دکمه‌ها**\n\nبرای فعال/غیرفعال کردن کلیک کن:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

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
        await context.bot.send_message(uid, f"✅ پرداخت تایید شد!\n\nپلن: {plan_key}\nمبلغ: {fmt(amount)} تومان\nسفارش #{oid}")
    except:
        pass
    await update.message.reply_text(f"✅ سفارش #{oid} تایید شد.")

async def admin_topup_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    parts = update.message.text.split("_")
    oid, uid, amount = int(parts[2]), int(parts[3]), int(parts[4])
    approve_order(oid)
    update_wallet(uid, amount)
    try:
        await context.bot.send_message(uid, f"✅ {fmt(amount)} تومان به کیف پول شما اضافه شد!")
    except:
        pass
    await update.message.reply_text(f"✅ {fmt(amount)} تومان به کاربر {uid} اضافه شد.")

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
            await context.bot.send_message(row[0], f"❌ رسید سفارش #{oid} تایید نشد.")
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
    await update.message.reply_text("متن پاسخ رو بفرست:")
    return WAIT_TICKET_REPLY_TEXT

async def receive_ticket_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = context.user_data.get("ticket_reply_id")
    uid = context.user_data.get("ticket_reply_user")
    close_ticket(tid)
    try:
        await context.bot.send_message(uid, f"📩 **پاسخ تیکت #{tid}:**\n\n{update.message.text}", parse_mode="Markdown")
        await update.message.reply_text("✅ پاسخ ارسال و تیکت بسته شد.")
    except:
        await update.message.reply_text("❌ ارسال ناموفق!")
    return ConversationHandler.END

async def keyboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = update.effective_user.id

    if text == "🛒 خرید VPN":
        await buy_menu(update, context)
    elif text == "🎁 تست رایگان":
        await update.message.reply_text("🎁 تست رایگان موجود نیست!", reply_markup=back_btn())
    elif text == "💰 افزایش موجودی":
        if not is_shop_open():
            await update.message.reply_text(FREEZE_MESSAGE)
            return
        amounts = [50000, 100000, 200000, 500000]
        kb = [[InlineKeyboardButton(f"{fmt(a)} تومان", callback_data=f"topup_amount_{a}")] for a in amounts]
        kb.append([InlineKeyboardButton("🔙 برگشت", callback_data="back_main")])
        await update.message.reply_text("💰 افزایش موجودی\n\nمبلغ رو انتخاب کن:", reply_markup=InlineKeyboardMarkup(kb))
    elif text == "🎲 تاس شانس":
        points = get_referral_points(uid)
        kb = []
        if points > 0:
            kb.append([InlineKeyboardButton(f"🎲 بزن بریم! (⭐ {points} امتیاز)", callback_data="roll_dice")])
        else:
            kb.append([InlineKeyboardButton("🔒 امتیاز نداری! دوست دعوت کن", callback_data="wheel_locked")])
        kb.append([InlineKeyboardButton("🔙 برگشت", callback_data="back_main")])
        await update.message.reply_text(f"🎲 **تاس شانس**\n\n⭐ امتیاز شما: {points}\n\nهر دعوت = ۱ امتیاز = ۱ بار تاس\nجایزه = عدد تاس × ۱۰,۰۰۰ تومان", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    elif text == "👥 دعوت از دوستان":
        await referral_menu(update, context)
    elif text == "👤 حساب من":
        wallet = get_wallet(uid)
        orders = get_order_count(uid)
        points = get_referral_points(uid)
        ref_count = get_referral_count(uid)
        ref_link = f"https://t.me/{BOT_USERNAME}?start={uid}"
        await update.message.reply_text(f"👤 **حساب کاربری**\n\n💰 موجودی: {fmt(wallet)} تومان\n⭐ امتیاز: {points}\n🛒 خرید: {orders}\n👥 دعوت: {ref_count}\n\n🔗 لینک دعوت:\n`{ref_link}`", parse_mode="Markdown", reply_markup=back_btn())
    elif text == "📋 اشتراک های من":
        rows = get_user_orders(uid)
        if not rows:
            await update.message.reply_text("❌ هیچ اشتراکی نداری!", reply_markup=back_btn())
            return
        status_map = {"approved": "✅ فعال", "pending": "⏳ در انتظار", "rejected": "❌ رد"}
        msg = "📋 **اشتراک های شما:**\n\n"
        for oid, plan, amount, volume_gb, used_gb, status, expire_at, created in rows:
            msg += f"#{oid} - {plan}\n💰 {fmt(amount)} تومان - {status_map.get(status, status)}\n📅 {created[:10]}\n\n"
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=back_btn())
    elif text == "🎫 تیکت پشتیبانی":
        kb = [[InlineKeyboardButton("✏️ تیکت جدید", callback_data="new_ticket")],
              [InlineKeyboardButton("🔙 برگشت", callback_data="back_main")]]
        await update.message.reply_text("🎫 تیکت پشتیبانی", reply_markup=InlineKeyboardMarkup(kb))
    elif text == "📞 پشتیبانی":
        support_text = "📞 **پشتیبانی**\n\n" + "\n".join(SUPPORT_USERS)
        await update.message.reply_text(support_text, parse_mode="Markdown", reply_markup=back_btn())

async def wheel_locked_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("شرایط لازم رو نداری!", show_alert=True)

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
            CallbackQueryHandler(admin_add_config_callback, pattern="^admin_add_config$"),
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
            WAIT_CONFIG_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_static_config)],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(check_join_callback, pattern="^check_join$"))
    app.add_handler(CallbackQueryHandler(panel_callback, pattern="^panel_"))
    app.add_handler(CallbackQueryHandler(plan_callback, pattern="^plan_"))
    app.add_handler(CallbackQueryHandler(pay_wallet_callback, pattern="^pay_wallet$"))
    app.add_handler(CallbackQueryHandler(roll_dice_callback, pattern="^roll_dice$"))
    app.add_handler(CallbackQueryHandler(copy_ref_link_callback, pattern="^copy_ref_link$"))
    app.add_handler(CallbackQueryHandler(back_main_callback, pattern="^back_main$"))
    app.add_handler(CallbackQueryHandler(admin_stats_callback, pattern="^admin_stats$"))
    app.add_handler(CallbackQueryHandler(admin_users_callback, pattern="^admin_users$"))
    app.add_handler(CallbackQueryHandler(admin_pending_callback, pattern="^admin_pending$"))
    app.add_handler(CallbackQueryHandler(admin_tickets_callback, pattern="^admin_tickets$"))
    app.add_handler(CallbackQueryHandler(admin_configs_menu, pattern="^admin_configs$"))
    app.add_handler(CallbackQueryHandler(admin_send_config_callback, pattern="^admin_send_config$"))
    app.add_handler(CallbackQueryHandler(admin_menu_manager, pattern="^admin_menu$"))
    app.add_handler(CallbackQueryHandler(admin_back_callback, pattern="^admin_back$"))
    app.add_handler(CallbackQueryHandler(toggle_button, pattern="^toggle_btn_"))
    app.add_handler(CallbackQueryHandler(execute_send_config, pattern="^send_config_"))
    app.add_handler(CallbackQueryHandler(wheel_locked_callback, pattern="^wheel_locked$"))

    app.add_handler(MessageHandler(filters.Regex(r"^/approve_\d+$"), admin_approve))
    app.add_handler(MessageHandler(filters.Regex(r"^/topup_approve_\d+_\d+_\d+$"), admin_topup_approve))
    app.add_handler(MessageHandler(filters.Regex(r"^/reject_\d+$"), admin_reject))
    app.add_handler(MessageHandler(filters.Regex(r"^/tr_\d+_\d+$"), ticket_reply_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, keyboard_handler))

    print("✅ بات در حال اجراست...")
    app.run_polling()

if __name__ == "__main__":
    main()