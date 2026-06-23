# -*- coding: utf-8 -*-
"""
فایل تنظیمات ربات.

این فایل مقادیر را از Environment Variables می‌خواند (برای دیپلوی روی
Railway مناسب است). اگر متغیر محیطی تنظیم نشده باشد، از مقدار پیش‌فرض
(برای اجرای محلی روی سرور خودتان) استفاده می‌شود.

روی Railway: این مقادیر را در تب Variables پروژه ریلوی تنظیم کنید،
نه در همین فایل (تا توکن و پسوردها داخل کد عمومی نباشند).
"""

import os


def _parse_admin_ids(raw: str):
    ids = []
    for part in raw.split(","):
        part = part.strip()
        if part:
            ids.append(int(part))
    return ids


# توکنی که از @BotFather در تلگرام گرفتید
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# آیدی عددی تلگرام ادمین(ها) به‌صورت کاما-جدا، مثال: "111111,222222"
ADMIN_IDS = _parse_admin_ids(os.getenv("ADMIN_IDS", "123456789"))

# مسیر فایل دیتابیس SQLite.
# روی Railway حتما باید این مسیر داخل یک Volume باشد، مثلا: /data/bot_database.db
# در غیر این صورت با هر دیپلوی جدید، دیتابیس (کاربران/موجودی/سفارش‌ها) پاک می‌شود.
DB_PATH = os.getenv("DB_PATH", "bot_database.db")

# ---------------- اطلاعات شارژ کیف پول (کارت به کارت) ----------------
CARD_NUMBER = os.getenv("CARD_NUMBER", "6037-XXXX-XXXX-XXXX")
CARD_HOLDER = os.getenv("CARD_HOLDER", "نام و نام خانوادگی صاحب کارت")

# ---------------- اطلاعات پنل 3X-UI ----------------
# آدرس پنل باید از بیرون (از اینترنت) قابل دسترسی باشد چون ریلوی روی
# سرور دیگری اجرا می‌شود، نه روی همان VPS شما.
# مثال: http://1.2.3.4:54321/  یا اگر روی پنل دامنه و SSL گذاشتید: https://panel.example.com/
PANEL_URL = os.getenv("PANEL_URL", "https://195.38.19.57:56571/GIiXORcuW6CENAuZNr")
PANEL_USERNAME = os.getenv("PANEL_USERNAME", "admin")
PANEL_PASSWORD = os.getenv("PANEL_PASSWORD", "Admin@123")

