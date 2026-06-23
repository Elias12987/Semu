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
ADMIN_IDS = _parse_admin_ids(os.getenv("ADMIN_IDS", "8471252047","8875652743"))
DB_PATH = os.getenv("DB_PATH", "bot_database.db")
CARD_NUMBER = os.getenv("CARD_NUMBER", "6219-8619-5197-9607")
CARD_HOLDER = os.getenv("CARD_HOLDER","علی فرحانی")
PANEL_URL = os.getenv("PANEL_URL", "https://195.38.19.57:56571")
PANEL_USERNAME = os.getenv("PANEL_USERNAME", "admin")
PANEL_PASSWORD = os.getenv("PANEL_PASSWORD,Admin@123")

PANEL_PATH = "/GIiXORcuW6CENAuZNr"
