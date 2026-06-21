# -*- coding: utf-8 -*-
"""
ماژول دیتابیس (SQLite).
تمام دادهای ربات (کاربران، موجودی کیف پول، محصولات، سفارش‌ها،
درخواست‌های شارژ و تیکت‌های پشتیبانی) اینجا ذخیره می‌شود.
"""

import sqlite3
from contextlib import closing
from datetime import datetime

from config import DB_PATH


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with closing(get_conn()) as conn, conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance INTEGER NOT NULL DEFAULT 0,
                joined_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price INTEGER NOT NULL,
                duration_days INTEGER NOT NULL,
                traffic_gb INTEGER NOT NULL,
                inbound_id INTEGER NOT NULL,
                description TEXT,
                active INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                config_link TEXT,
                client_uuid TEXT,
                created_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS wallet_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                receipt_file_id TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                admin_reply TEXT,
                status TEXT NOT NULL DEFAULT 'open',
                created_at TEXT
            )
            """
        )


# ---------------- کاربران ----------------

def get_or_create_user(user_id: int, username):
    with closing(get_conn()) as conn, conn:
        row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO users (user_id, username, balance, joined_at) VALUES (?,?,0,?)",
                (user_id, username, datetime.utcnow().isoformat()),
            )
            row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        return dict(row)


def get_balance(user_id: int) -> int:
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT balance FROM users WHERE user_id=?", (user_id,)).fetchone()
        return row["balance"] if row else 0


def change_balance(user_id: int, delta: int):
    with closing(get_conn()) as conn, conn:
        conn.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (delta, user_id))


# ---------------- محصولات ----------------

def add_product(name, price, duration_days, traffic_gb, inbound_id, description=""):
    with closing(get_conn()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO products (name, price, duration_days, traffic_gb, inbound_id, description, active) "
            "VALUES (?,?,?,?,?,?,1)",
            (name, price, duration_days, traffic_gb, inbound_id, description),
        )
        return cur.lastrowid


def list_products(active_only=True):
    with closing(get_conn()) as conn:
        if active_only:
            rows = conn.execute("SELECT * FROM products WHERE active=1 ORDER BY price").fetchall()
        else:
            rows = conn.execute("SELECT * FROM products ORDER BY id").fetchall()
        return [dict(r) for r in rows]


def get_product(product_id: int):
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
        return dict(row) if row else None


def delete_product(product_id: int):
    with closing(get_conn()) as conn, conn:
        conn.execute("DELETE FROM products WHERE id=?", (product_id,))


# ---------------- سفارش‌ها ----------------

def create_order(user_id, product_id, config_link, client_uuid):
    with closing(get_conn()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO orders (user_id, product_id, config_link, client_uuid, created_at) VALUES (?,?,?,?,?)",
            (user_id, product_id, config_link, client_uuid, datetime.utcnow().isoformat()),
        )
        return cur.lastrowid


def list_orders(user_id):
    with closing(get_conn()) as conn:
        rows = conn.execute(
            "SELECT * FROM orders WHERE user_id=? ORDER BY id DESC", (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]


# ---------------- درخواست‌های شارژ کیف پول ----------------

def create_wallet_request(user_id, amount, receipt_file_id):
    with closing(get_conn()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO wallet_requests (user_id, amount, receipt_file_id, status, created_at) "
            "VALUES (?,?,?,'pending',?)",
            (user_id, amount, receipt_file_id, datetime.utcnow().isoformat()),
        )
        return cur.lastrowid


def get_wallet_request(request_id):
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT * FROM wallet_requests WHERE id=?", (request_id,)).fetchone()
        return dict(row) if row else None


def set_wallet_request_status(request_id, status):
    with closing(get_conn()) as conn, conn:
        conn.execute("UPDATE wallet_requests SET status=? WHERE id=?", (status, request_id))


# ---------------- تیکت‌های پشتیبانی ----------------

def create_ticket(user_id, message):
    with closing(get_conn()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO tickets (user_id, message, status, created_at) VALUES (?,?, 'open', ?)",
            (user_id, message, datetime.utcnow().isoformat()),
        )
        return cur.lastrowid


def list_open_tickets():
    with closing(get_conn()) as conn:
        rows = conn.execute("SELECT * FROM tickets WHERE status='open' ORDER BY id").fetchall()
        return [dict(r) for r in rows]


def get_ticket(ticket_id):
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
        return dict(row) if row else None


def close_ticket(ticket_id, admin_reply):
    with closing(get_conn()) as conn, conn:
        conn.execute(
            "UPDATE tickets SET status='closed', admin_reply=? WHERE id=?",
            (admin_reply, ticket_id),
        )
