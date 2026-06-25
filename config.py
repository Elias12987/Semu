# -*- coding: utf-8 -*-
import os

def _parse_admin_ids(raw: str):
    return [int(x.strip()) for x in raw.split(",") if x.strip().isdigit()]

BOT_TOKEN   = os.getenv("BOT_TOKEN", "")
ADMIN_IDS   = _parse_admin_ids(os.getenv("ADMIN_IDS", ""))
DB_PATH     = os.getenv("DB_PATH", "bot.db")
CARD_NUMBER = os.getenv("CARD_NUMBER", "")
CARD_HOLDER = os.getenv("CARD_HOLDER", "")

# ── پلن‌های ثابت پنل عادی ──────────────────────────────
FIXED_PLANS = [
    {"id": 1, "name": "پنل عادی ۱۰ گیگ",  "traffic_gb": 10,  "price": 20000,  "duration_days": 10},
    {"id": 2, "name": "پنل عادی ۱۵ گیگ",  "traffic_gb": 15,  "price": 30000,  "duration_days": 15},
    {"id": 3, "name": "پنل عادی ۲۵ گیگ",  "traffic_gb": 25,  "price": 50000,  "duration_days": 30},
    {"id": 4, "name": "پنل عادی ۵۰ گیگ",  "traffic_gb": 50,  "price": 100000, "duration_days": 30},
    {"id": 5, "name": "پنل عادی ۱۰۰ گیگ", "traffic_gb": 100, "price": 200000, "duration_days": 30},
]

# ── کانفیگ‌ها / ساب‌لینک‌ها برای هر پلن ──────────────
# هر پلن یه لیست از کانفیگ داره — به ازای هر خرید یکی مصرف میشه
# وقتی لیست خالی شد به ادمین اطلاع داده میشه
PLAN_CONFIGS = {
    1: [
        # کانفیگ‌های پلن ۱۰ گیگ رو اینجا بذار
        # "vless://...",
        # "vmess://...",
    ],
    2: [
        # کانفیگ‌های پلن ۱۵ گیگ
    ],
    3: [
        # کانفیگ‌های پلن ۲۵ گیگ
    ],
    4: [
        # کانفیگ‌های پلن ۵۰ گیگ
    ],
    5: [
        # کانفیگ‌های پلن ۱۰۰ گیگ
    ],
}

SERVER_LOCATION = "فرانسه 🇫🇷"
SERVER_NAME     = "پنل عادی"
