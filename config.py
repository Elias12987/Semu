# -*- coding: utf-8 -*-
import os

def _parse_admin_ids(raw: str):
    return [int(x.strip()) for x in raw.split(",") if x.strip().isdigit()]

BOT_TOKEN   = os.getenv("BOT_TOKEN", "")
ADMIN_IDS   = _parse_admin_ids(os.getenv("ADMIN_IDS", ""))
DB_PATH     = os.getenv("DB_PATH", "bot.db")
CARD_NUMBER = os.getenv("CARD_NUMBER", "")
CARD_HOLDER = os.getenv("CARD_HOLDER", "")
