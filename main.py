# -*- coding: utf-8 -*-
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN
import database as db
from handlers import user, admin


async def main():
    logging.basicConfig(level=logging.INFO)
    db.init_db()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    dp.include_router(admin.router)
    dp.include_router(user.router)

    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("ربات شروع به کار کرد ✅")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
