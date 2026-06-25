# -*- coding: utf-8 -*-
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, ADMIN_IDS, FIXED_PLANS
import database as db
from handlers import admin, user

logging.basicConfig(level=logging.INFO)


async def check_expiring_orders(bot: Bot):
    """هر ساعت یه‌بار سرویس‌های منقضی شده رو بررسی و به ادمین اطلاع میده"""
    while True:
        try:
            expired = db.get_expiring_orders()
            for order in expired:
                plan_id = order.get("plan_id")
                p = next((x for x in FIXED_PLANS if x["id"] == plan_id), None)
                plan_name = p["name"] if p else "سرویس"
                for admin_id in ADMIN_IDS:
                    try:
                        await bot.send_message(
                            admin_id,
                            f"⏰ سرویس کاربر منقضی شد!\n"
                            f"━━━━━━━━━━━━━━━\n"
                            f"🔹 کاربر: {order['user_id']}\n"
                            f"📦 پلن: {plan_name}\n"
                            f"🗓 تاریخ انقضا: {str(order.get('expires_at', ''))[:10]}\n"
                            f"━━━━━━━━━━━━━━━\n"
                            f"برای شارژ مجدد از /send_{order['id']} استفاده کن."
                        )
                    except Exception:
                        pass
                db.mark_order_notified(order["id"])
        except Exception as e:
            logging.error(f"check_expiring_orders error: {e}")
        await asyncio.sleep(3600)  # هر ۱ ساعت


async def main():
    db.init_db()
    bot = Bot(token=BOT_TOKEN)
    dp  = Dispatcher(storage=MemoryStorage())

    dp.include_router(admin.router)
    dp.include_router(user.router)

    asyncio.create_task(check_expiring_orders(bot))

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
