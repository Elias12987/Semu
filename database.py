# -*- coding: utf-8 -*-
import sqlite3
from contextlib import closing
from datetime import datetime
from config import DB_PATH


def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    with closing(get_conn()) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id   INTEGER PRIMARY KEY,
                username  TEXT,
                balance   INTEGER NOT NULL DEFAULT 0,
                free_used INTEGER NOT NULL DEFAULT 0,
                joined_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                name         TEXT NOT NULL,
                category     TEXT NOT NULL DEFAULT 'عادی',
                price        INTEGER NOT NULL,
                duration_days INTEGER NOT NULL,
                traffic_gb   INTEGER NOT NULL,
                description  TEXT,
                active       INTEGER NOT NULL DEFAULT 1
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                product_id INTEGER,
                type       TEXT NOT NULL DEFAULT 'paid',
                status     TEXT NOT NULL DEFAULT 'pending',
                config     TEXT,
                created_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS wallet_requests (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL,
                amount          INTEGER NOT NULL,
                receipt_file_id TEXT,
                status          TEXT NOT NULL DEFAULT 'pending',
                created_at      TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                message     TEXT NOT NULL,
                admin_reply TEXT,
                status      TEXT NOT NULL DEFAULT 'open',
                created_at  TEXT
            )
        """)
        conn.commit()


# ---- کاربران ----

def get_or_create_user(user_id, username):
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not row:
            conn.execute(
                "INSERT INTO users (user_id,username,balance,free_used,joined_at) VALUES (?,?,0,0,?)",
                (user_id, username, datetime.utcnow().isoformat())
            )
            conn.commit()
            row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        return dict(row)


def get_balance(user_id):
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT balance FROM users WHERE user_id=?", (user_id,)).fetchone()
        return int(row["balance"]) if row else 0


def change_balance(user_id, delta):
    with closing(get_conn()) as conn:
        conn.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (delta, user_id))
        conn.commit()
        row = conn.execute("SELECT balance FROM users WHERE user_id=?", (user_id,)).fetchone()
        return int(row["balance"]) if row else 0


def has_used_free(user_id):
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT free_used FROM users WHERE user_id=?", (user_id,)).fetchone()
        return bool(row and row["free_used"])


def mark_free_used(user_id):
    with closing(get_conn()) as conn:
        conn.execute("UPDATE users SET free_used=1 WHERE user_id=?", (user_id,))
        conn.commit()


def get_all_users():
    with closing(get_conn()) as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM users ORDER BY joined_at DESC").fetchall()]


# ---- محصولات ----

def add_product(name, category, price, duration_days, traffic_gb, description=""):
    with closing(get_conn()) as conn:
        cur = conn.execute(
            "INSERT INTO products (name,category,price,duration_days,traffic_gb,description,active) VALUES (?,?,?,?,?,?,1)",
            (name, category, price, duration_days, traffic_gb, description)
        )
        conn.commit()
        return cur.lastrowid


def list_products(active_only=True, category=None):
    with closing(get_conn()) as conn:
        if category:
            rows = conn.execute("SELECT * FROM products WHERE active=1 AND category=? ORDER BY price", (category,)).fetchall()
        elif active_only:
            rows = conn.execute("SELECT * FROM products WHERE active=1 ORDER BY category,price").fetchall()
        else:
            rows = conn.execute("SELECT * FROM products ORDER BY id").fetchall()
        return [dict(r) for r in rows]


def list_categories():
    with closing(get_conn()) as conn:
        rows = conn.execute("SELECT DISTINCT category FROM products WHERE active=1 ORDER BY category").fetchall()
        return [r["category"] for r in rows]


def get_product(product_id):
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
        return dict(row) if row else None


def delete_product(product_id):
    with closing(get_conn()) as conn:
        conn.execute("DELETE FROM products WHERE id=?", (product_id,))
        conn.commit()


# ---- سفارش‌ها ----

def create_order(user_id, product_id, order_type="paid"):
    with closing(get_conn()) as conn:
        cur = conn.execute(
            "INSERT INTO orders (user_id,product_id,type,status,created_at) VALUES (?,?,?,'pending',?)",
            (user_id, product_id, order_type, datetime.utcnow().isoformat())
        )
        conn.commit()
        return cur.lastrowid


def get_order(order_id):
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        return dict(row) if row else None


def set_order_config(order_id, config):
    with closing(get_conn()) as conn:
        conn.execute("UPDATE orders SET config=?, status='done' WHERE id=?", (config, order_id))
        conn.commit()


def list_orders(user_id):
    with closing(get_conn()) as conn:
        rows = conn.execute("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC", (user_id,)).fetchall()
        return [dict(r) for r in rows]


def count_orders():
    with closing(get_conn()) as conn:
        return conn.execute("SELECT COUNT(*) as c FROM orders").fetchone()["c"]


# ---- کیف پول ----

def create_wallet_request(user_id, amount, receipt_file_id):
    with closing(get_conn()) as conn:
        cur = conn.execute(
            "INSERT INTO wallet_requests (user_id,amount,receipt_file_id,status,created_at) VALUES (?,?,?,'pending',?)",
            (user_id, amount, receipt_file_id, datetime.utcnow().isoformat())
        )
        conn.commit()
        return cur.lastrowid


def get_wallet_request(request_id):
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT * FROM wallet_requests WHERE id=?", (request_id,)).fetchone()
        return dict(row) if row else None


def set_wallet_request_status(request_id, status):
    with closing(get_conn()) as conn:
        conn.execute("UPDATE wallet_requests SET status=? WHERE id=?", (status, request_id))
        conn.commit()


# ---- تیکت‌ها ----

def create_ticket(user_id, message):
    with closing(get_conn()) as conn:
        cur = conn.execute(
            "INSERT INTO tickets (user_id,message,status,created_at) VALUES (?,?,'open',?)",
            (user_id, message, datetime.utcnow().isoformat())
        )
        conn.commit()
        return cur.lastrowid


def list_open_tickets():
    with closing(get_conn()) as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM tickets WHERE status='open' ORDER BY id").fetchall()]


def get_ticket(ticket_id):
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
        return dict(row) if row else None


def close_ticket(ticket_id, admin_reply):
    with closing(get_conn()) as conn:
        conn.execute("UPDATE tickets SET status='closed',admin_reply=? WHERE id=?", (admin_reply, ticket_id))
        conn.commit()
