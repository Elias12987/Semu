# -*- coding: utf-8 -*-
import os

def _parse_admin_ids(raw: str):
    ids = []
    for part in raw.split(","):
        part = part.strip()
        if part:
            ids.append(int(part))
    return ids

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
ADMIN_IDS = _parse_admin_ids(os.getenv("ADMIN_IDS", "123456789"))
DB_PATH = os.getenv("DB_PATH", "bot_database.db")
CARD_NUMBER = os.getenv("CARD_NUMBER", "6037-XXXX-XXXX-XXXX")
CARD_HOLDER = os.getenv("CARD_HOLDER", "نام صاحب کارت")
PANEL_URL = os.getenv("PANEL_URL", "http://YOUR_IP:PORT")
PANEL_USERNAME = os.getenv("PANEL_USERNAME", "admin")
PANEL_PASSWORD = os.getenv("PANEL_PASSWORD", "admin_password")
PANEL_PATH = os.getenv("PANEL_PATH", "")  # مثال: /GIiXORcuW6CENAuZNr
