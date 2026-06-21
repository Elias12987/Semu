# -*- coding: utf-8 -*-
"""
ماژول ارتباط با پنل 3X-UI برای ساخت خودکار کاربر VLESS + Reality.

نکته مهم: ساختار API پنل‌های مبتنی بر X-UI ممکن است بین نسخه‌های مختلف
کمی تفاوت داشته باشد. اگر هنگام خرید با خطا مواجه شدید، endpoint های زیر
را با نسخه نصب‌شده روی سرورتان مقایسه و در صورت نیاز اصلاح کنید.
"""

import json
import time
import uuid

import requests

from config import PANEL_URL, PANEL_USERNAME, PANEL_PASSWORD


class PanelError(Exception):
    pass


class ThreeXUIClient:
    def __init__(self):
        self.base_url = PANEL_URL.rstrip("/")
        self.session = requests.Session()
        self._logged_in = False

    def login(self):
        url = f"{self.base_url}/login"
        resp = self.session.post(
            url,
            data={"username": PANEL_USERNAME, "password": PANEL_PASSWORD},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success", False):
            raise PanelError(f"ورود به پنل ناموفق بود: {data}")
        self._logged_in = True

    def _ensure_login(self):
        if not self._logged_in:
            self.login()

    def get_inbound(self, inbound_id: int) -> dict:
        self._ensure_login()
        url = f"{self.base_url}/panel/api/inbounds/get/{inbound_id}"
        resp = self.session.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success", False):
            raise PanelError(f"دریافت اطلاعات inbound ناموفق بود: {data}")
        return data["obj"]

    def add_client(self, inbound_id: int, email: str, traffic_gb: int, duration_days: int) -> dict:
        """
        یک کلاینت جدید به inbound مشخص‌شده اضافه می‌کند و دیکشنری شامل
        uuid و لینک vless آماده را برمی‌گرداند.
        """
        self._ensure_login()

        client_uuid = str(uuid.uuid4())
        total_bytes = traffic_gb * 1024 * 1024 * 1024 if traffic_gb else 0
        expiry_ms = 0
        if duration_days:
            expiry_ms = int((time.time() + duration_days * 86400) * 1000)

        client_obj = {
            "id": client_uuid,
            "email": email,
            "limitIp": 0,
            "totalGB": total_bytes,
            "expiryTime": expiry_ms,
            "enable": True,
            "flow": "xtls-rprx-vision",
        }
        settings = {"clients": [client_obj]}

        url = f"{self.base_url}/panel/api/inbounds/addClient"
        payload = {"id": inbound_id, "settings": json.dumps(settings)}
        resp = self.session.post(url, data=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success", False):
            raise PanelError(f"افزودن کلاینت ناموفق بود: {data}")

        inbound = self.get_inbound(inbound_id)
        link = self._build_vless_link(inbound, client_uuid, email)
        return {"uuid": client_uuid, "link": link}

    def _build_vless_link(self, inbound: dict, client_uuid: str, email: str) -> str:
        stream = json.loads(inbound.get("streamSettings", "{}"))
        reality = stream.get("realitySettings", {})
        reality_settings = reality.get("settings", {})

        port = inbound.get("port")
        server_host = self.base_url.split("//")[-1].split(":")[0].split("/")[0]

        pbk = reality_settings.get("publicKey", "")
        sids = reality.get("shortIds") or [""]
        sid = sids[0]
        sni_list = reality.get("serverNames") or [""]
        sni = sni_list[0]
        fp = reality_settings.get("fingerprint", "chrome")

        params = (
            f"type=tcp&security=reality&pbk={pbk}&fp={fp}"
            f"&sni={sni}&sid={sid}&spx=%2F&flow=xtls-rprx-vision"
        )
        return f"vless://{client_uuid}@{server_host}:{port}?{params}#{email}"
