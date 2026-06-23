# xui_client.py
# -*- coding: utf-8 -*-

import json
import time
import uuid
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class PanelError(Exception):
    pass


class ThreeXUIClient:
    def __init__(self, base_url: str, panel_path: str):
        base = base_url.rstrip("/")
        path = panel_path.strip("/")

        self.base_url = f"{base}/{path}" if path else base
        self.session = requests.Session()
        self.session.verify = False  # اگر SSL self-signed باشد

    # -----------------------------
    # Get inbound info
    # -----------------------------
    def get_inbound(self, inbound_id: int) -> dict:
        url = f"{self.base_url}/panel/api/inbounds/get/{inbound_id}"
        resp = self.session.get(url, timeout=15)
        resp.raise_for_status()

        data = resp.json()
        if not data.get("success"):
            raise PanelError(f"Get inbound failed: {data}")

        return data["obj"]

    # -----------------------------
    # Add client to inbound
    # -----------------------------
    def add_client(self, inbound_id: int, email: str,
                   traffic_gb: int = 0,
                   duration_days: int = 0):

        client_uuid = str(uuid.uuid4())

        total_bytes = 0
        if traffic_gb > 0:
            total_bytes = traffic_gb * 1024 * 1024 * 1024

        expiry_ms = 0
        if duration_days > 0:
            expiry_ms = int((time.time() + duration_days * 86400) * 1000)

        client = {
            "id": client_uuid,
            "email": email,
            "limitIp": 0,
            "totalGB": total_bytes,
            "expiryTime": expiry_ms,
            "enable": True,
            "flow": "xtls-rprx-vision"
        }

        settings = {
            "clients": [client]
        }

        url = f"{self.base_url}/panel/api/inbounds/addClient"

        payload = {
            "id": inbound_id,
            "settings": json.dumps(settings)
        }

        resp = self.session.post(url, data=payload, timeout=15)
        resp.raise_for_status()

        data = resp.json()
        if not data.get("success"):
            raise PanelError(f"Add client failed: {data}")

        inbound = self.get_inbound(inbound_id)
        link = self.build_link(inbound, client_uuid, email)

        return {
            "uuid": client_uuid,
            "link": link
        }

    # -----------------------------
    # Build VLESS / VMess link
    # -----------------------------
    def build_link(self, inbound: dict, uuid_str: str, email: str):

        stream = json.loads(inbound.get("streamSettings", "{}"))

        port = inbound.get("port")
        host = self.base_url.split("//")[-1].split(":")[0].split("/")[0]
        protocol = inbound.get("protocol", "vless")

        security = stream.get("security", "none")
        network = stream.get("network", "tcp")

        # ---------------- REALITY ----------------
        if security == "reality":
            r = stream.get("realitySettings", {})
            rset = r.get("settings", {})

            pbk = rset.get("publicKey", "")
            fp = rset.get("fingerprint", "chrome")

            sid = ""
            if r.get("shortIds"):
                sid = r["shortIds"][0]

            sni = ""
            if r.get("serverNames"):
                sni = r["serverNames"][0]

            params = (
                f"type=tcp&security=reality"
                f"&pbk={pbk}&fp={fp}"
                f"&sni={sni}&sid={sid}"
                f"&flow=xtls-rprx-vision"
            )

            return f"vless://{uuid_str}@{host}:{port}?{params}#{email}"

        # ---------------- TLS ----------------
        if security == "tls":
            params = f"type={network}&security=tls"

            if network == "ws":
                ws = stream.get("wsSettings", {})
                path = ws.get("path", "/")
                params += f"&path={path}"

            return f"vless://{uuid_str}@{host}:{port}?{params}#{email}"

        # ---------------- NONE ----------------
        if protocol == "vmess":
            import base64

            vmess = {
                "v": "2",
                "ps": email,
                "add": host,
                "port": str(port),
                "id": uuid_str,
                "aid": "0",
                "net": network,
                "type": "none",
                "host": "",
                "path": "/",
                "tls": ""
            }

            return "vmess://" + base64.b64encode(
                json.dumps(vmess).encode()
            ).decode()

        params = f"type={network}&security=none"
        return f"vless://{uuid_str}@{host}:{port}?{params}#{email}"