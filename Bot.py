import logging
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

# ─────────────────────────────────────────
#  تنظیمات - اینا رو عوض کن
# ─────────────────────────────────────────
BOT_TOKEN = "8925445808:AAGkJU3BX7f82SVG4YyvYHJALKro5xrZAhM"
CHANNEL_ID = "@VPN_IRONMAN"          # آیدی کانالت (با @)
ADMIN_ID = 8471252047                 # آیدی عددی خودت
CARD_NUMBER = "6219-8619-2847-2389"  # شماره کارتت
CARD_OWNER = "ایران بوصیدی"

# ─────────────────────────────────────────
#  پلن‌ها
# ─────────────────────────────────────────
PLANS = {
    "1m": {"name": "۱ ماهه",  "price": 50_000,  "Net": 5gb},
    "3m": {"name": "۳ ماهه",  "price": 130_000, "days": 10gb},
    "6m": {"name": "۶ ماهه",  "price": 240_000, "days": 20gb},
}

# ─────────────────────────────────────────
#  State های ConversationHandler
# ─────────────────────────────────────────
WAIT_RECEIPT      = 1   # انتظار رسید پرداخت
WAIT_TOPUP_AMOUNT = 2   # انتظار مبلغ شارژ
WAIT_TOPUP_RECEIPT= 3   # انتظار رسید شارژ

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
    """)
    con.commit()
    con.close()

def get_user(user_id):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    con.close()
    return row

def ensure_user(user_id, username):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?,?)", (user_id, username))
    con.commit()
    con.close()

def get_wallet(user_id):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT wallet FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    con.close()
    return row[0] if row else 0

def update_wallet(user_id, amount):
    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("UPDATE users SET wallet = wallet + ? WHERE user_id=?", (amount, user_id))
    con.commit()
    con.close()

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
    con.commit()
    con.close()

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
        [InlineKeyboardButton("🛒 خرید VPN",         callback_data="buy")],
        [InlineKeyboardButton("🎁 تست رایگان",        callback_data="test")],
        [InlineKeyboardButton("💰 افزایش موجودی",     callback_data="topup")],
        [InlineKeyboardButton("👤 حساب من",           callback_data="account")],
        [InlineKeyboardButton("📞 پشتیبانی",          callback_data="support")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user.id, user.username)

    if not await check_membership(update, context):
        return

    await update.message.reply_text(
        f"سلام {user.first_name} 👋\n\nبه بات فروش VPN خوش اومدی 🔒\nیه گزینه انتخاب کن:",
        reply_markup=main_menu_keyboard()
    )

# ─── بررسی مجدد عضویت بعد از کلیک «عضو شدم» ───
async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    if await is_member(context.bot, user.id):
        ensure_user(user.id, user.username)
        await query.edit_message_text(
            f"✅ ممنون! عضویتت تأیید شد.\n\nسلام {user.first_name} 👋\nیه گزینه انتخاب کن:",
            reply_markup=main_menu_keyboard()
        )
    else:
        await query.answer("هنوز عضو نشدی! 😕", show_alert=True)

# ═══════════════════════════════════════════
#  خرید VPN
# ═══════════════════════════════════════════
async def buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not await check_membership(update, context):
        return

    wallet = get_wallet(query.from_user.id)
    keyboard = []
    for key, plan in PLANS.items():
        keyboard.append([InlineKeyboardButton(
            f"{plan['name']} — {plan['price']:,} تومان",
            callback_data=f"selectplan_{key}"
        )])
    keyboard.append([InlineKeyboardButton("🔙 برگشت", callback_data="back_main")])

    await query.edit_message_text(
        f"💰 موجودی کیف پول: {wallet:,} تومان\n\n📦 پلن مورد نظرت رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def select_plan_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan_key = query.data.split("_")[1]
    plan = PLANS[plan_key]
    wallet = get_wallet(query.from_user.id)

    context.user_data["selected_plan"] = plan_key

    keyboard = []
    if wallet >= plan["price"]:
        keyboard.append([InlineKeyboardButton("💳 پرداخت از کیف پول", callback_data=f"pay_wallet_{plan_key}")])
    keyboard.append([InlineKeyboardButton("💵 پرداخت کارت به کارت", callback_data=f"pay_card_{plan_key}")])
    keyboard.append([InlineKeyboardButton("🔙 برگشت", callback_data="buy")])

    await query.edit_message_text(
        f"📦 پلن انتخابی: {plan['name']}\n"
        f"💰 قیمت: {plan['price']:,} تومان\n"
        f"👛 موجودی کیف پول: {wallet:,} تومان\n\n"
        "روش پرداخت رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ─── پرداخت کارت به کارت ───
async def pay_card_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan_key = query.data.split("_")[2]
    plan = PLANS[plan_key]
    context.user_data["pending_plan"] = plan_key
    context.user_data["pending_type"] = "buy"

    await query.edit_message_text(
        f"💳 پرداخت کارت به کارت\n\n"
        f"مبلغ: {plan['price']:,} تومان\n"
        f"شماره کارت: `{CARD_NUMBER}`\n"
        f"به نام: {CARD_OWNER}\n\n"
        "بعد از واریز، **عکس رسید** رو اینجا بفرست 👇",
        parse_mode="Markdown"
    )
    return WAIT_RECEIPT

# ─── پرداخت از کیف پول ───
async def pay_wallet_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan_key = query.data.split("_")[2]
    plan = PLANS[plan_key]
    user_id = query.from_user.id
    wallet = get_wallet(user_id)

    if wallet < plan["price"]:
        await query.answer("موجودی کافی نیست!", show_alert=True)
        return

    update_wallet(user_id, -plan["price"])
    oid = create_order(user_id, plan_key, plan["price"], "wallet")
    approve_order(oid)

    # اطلاع به ادمین
    await context.bot.send_message(
        ADMIN_ID,
        f"✅ خرید از کیف پول\n"
        f"کاربر: {query.from_user.id} (@{query.from_user.username})\n"
        f"پلن: {plan['name']}\n"
        f"سفارش #{oid}"
    )

    await query.edit_message_text(
        f"✅ خرید موفق!\n\n"
        f"پلن {plan['name']} فعال شد 🎉\n"
        f"کانفیگ شما به زودی ارسال می‌شه.\n\n"
        f"شماره سفارش: #{oid}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 منوی اصلی", callback_data="back_main")]])
    )

# ─── دریافت رسید پرداخت ───
async def receive_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    pending_type = context.user_data.get("pending_type", "buy")

    if pending_type == "buy":
        plan_key = context.user_data.get("pending_plan")
        plan = PLANS[plan_key]
        oid = create_order(user.id, plan_key, plan["price"], "receipt_sent")

        caption = (
            f"🧾 رسید جدید — سفارش #{oid}\n"
            f"کاربر: {user.id} (@{user.username})\n"
            f"پلن: {plan['name']} — {plan['price']:,} تومان\n\n"
            f"تأیید: /approve_{oid}\n"
            f"رد: /reject_{oid}"
        )
    else:  # topup
        amount = context.user_data.get("topup_amount", 0)
        oid = create_order(user.id, "topup", amount, "receipt_sent")
        caption = (
            f"💰 شارژ کیف پول — #{oid}\n"
            f"کاربر: {user.id} (@{user.username})\n"
            f"مبلغ: {amount:,} تومان\n\n"
            f"تأیید: /topup_approve_{oid}_{user.id}_{amount}\n"
            f"رد: /reject_{oid}"
        )

    if update.message.photo:
        await context.bot.send_photo(ADMIN_ID, update.message.photo[-1].file_id, caption=caption)
    else:
        await context.bot.send_message(ADMIN_ID, "⚠️ رسید بدون عکس\n" + caption)

    await update.message.reply_text(
        "✅ رسیدت دریافت شد!\nبعد از بررسی (معمولاً زیر ۳۰ دقیقه) کانفیگت ارسال می‌شه. 🙏",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 منوی اصلی", callback_data="back_main")]])
    )
    return ConversationHandler.END

# ═══════════════════════════════════════════
#  تست رایگان
# ═══════════════════════════════════════════
TEST_CONFIG = """
🔰 کانفیگ تست (۲۴ ساعته):

vless://test-uuid@your-server.com:443?type=ws&security=tls&path=%2Fws#TestVPN

⚠️ این کانفیگ فقط ۲۴ ساعت اعتبار دارد.
"""

async def test_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not await check_membership(update, context):
        return

    user_id = query.from_user.id
    if test_used(user_id):
        await query.edit_message_text(
            "❌ قبلاً از تست رایگان استفاده کردی!\n\nبرای خرید از منو اقدام کن 👇",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛒 خرید VPN", callback_data="buy"),
                                               InlineKeyboardButton("🏠 منو", callback_data="back_main")]])
        )
        return

    mark_test_used(user_id, TEST_CONFIG)
    await query.edit_message_text(
        f"🎁 کانفیگ تست ۲۴ ساعته:\n\n{TEST_CONFIG}\n\n"
        "برای خرید پلن کامل از منو اقدام کن 👇",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛒 خرید VPN", callback_data="buy"),
                                           InlineKeyboardButton("🏠 منو", callback_data="back_main")]])
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
        "بعد از واریز، **عکس رسید** رو اینجا بفرست 👇",
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

    await query.edit_message_text(
        f"👤 حساب کاربری\n\n"
        f"آیدی: {user_id}\n"
        f"💰 موجودی: {wallet:,} تومان\n"
        f"🎁 تست رایگان: {used_test}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💰 افزایش موجودی", callback_data="topup")],
            [InlineKeyboardButton("🏠 منوی اصلی", callback_data="back_main")]
        ])
    )

# ═══════════════════════════════════════════
#  پشتیبانی
# ═══════════════════════════════════════════
async def support_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📞 پشتیبانی\n\nبرای ارتباط با پشتیبانی:\n👤 @your_support_username",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 منوی اصلی", callback_data="back_main")]])
    )

# ═══════════════════════════════════════════
#  برگشت به منو
# ═══════════════════════════════════════════
async def back_main_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "یه گزینه انتخاب کن 👇",
        reply_markup=main_menu_keyboard()
    )

# ═══════════════════════════════════════════
#  دستورات ادمین
# ═══════════════════════════════════════════
async def admin_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    oid = int(update.message.text.split("_")[1])
    approve_order(oid)

    con = sqlite3.connect("vpn_bot.db")
    cur = con.cursor()
    cur.execute("SELECT user_id, plan FROM orders WHERE id=?", (oid,))
    row = cur.fetchone()
    con.close()

    if row:
        user_id, plan_key = row
        plan = PLANS.get(plan_key, {})
        await context.bot.send_message(
            user_id,
            f"✅ پرداخت تأیید شد!\n\n"
            f"پلن {plan.get('name','')} فعال شد 🎉\n"
            f"کانفیگ شما:\n\n[اینجا کانفیگ رو قرار بده]\n\nشماره سفارش: #{oid}"
        )
        await update.message.reply_text(f"✅ سفارش #{oid} تأیید و کاربر {user_id} مطلع شد.")

async def admin_topup_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    # فرمت: /topup_approve_{oid}_{user_id}_{amount}
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
        await context.bot.send_message(row[0], f"❌ متأسفانه رسید سفارش #{oid} تأیید نشد.\nلطفاً با پشتیبانی تماس بگیر.")
    await update.message.reply_text(f"❌ سفارش #{oid} رد شد.")

# ═══════════════════════════════════════════
#  راه‌اندازی
# ═══════════════════════════════════════════
def main():
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # ConversationHandler برای رسید پرداخت
    conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(pay_card_callback,    pattern="^pay_card_"),
            CallbackQueryHandler(topup_amount_callback, pattern="^topup_amount_"),
        ],
        states={
            WAIT_RECEIPT:       [MessageHandler(filters.PHOTO | filters.TEXT, receive_receipt)],
            WAIT_TOPUP_RECEIPT: [MessageHandler(filters.PHOTO | filters.TEXT, receive_receipt)],
        },
        fallbacks=[CommandHandler("start", start)],
        per_message=False,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(check_join_callback,    pattern="^check_join$"))
    app.add_handler(CallbackQueryHandler(buy_callback,           pattern="^buy$"))
    app.add_handler(CallbackQueryHandler(select_plan_callback,   pattern="^selectplan_"))
    app.add_handler(CallbackQueryHandler(pay_wallet_callback,    pattern="^pay_wallet_"))
    app.add_handler(CallbackQueryHandler(test_callback,          pattern="^test$"))
    app.add_handler(CallbackQueryHandler(topup_callback,         pattern="^topup$"))
    app.add_handler(CallbackQueryHandler(account_callback,       pattern="^account$"))
    app.add_handler(CallbackQueryHandler(support_callback,       pattern="^support$"))
    app.add_handler(CallbackQueryHandler(back_main_callback,     pattern="^back_main$"))

    # دستورات ادمین
    app.add_handler(MessageHandler(filters.Regex(r"^/approve_\d+$"),                  admin_approve))
    app.add_handler(MessageHandler(filters.Regex(r"^/topup_approve_\d+_\d+_\d+$"),   admin_topup_approve))
    app.add_handler(MessageHandler(filters.Regex(r"^/reject_\d+$"),                   admin_reject))

    print("✅ بات در حال اجراست...")
    app.run_polling()

if __name__ == "__main__":
    main()
