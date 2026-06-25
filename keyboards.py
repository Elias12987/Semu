# -*- coding: utf-8 -*-
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from config import FIXED_PLANS


def main_menu(is_admin=False):
    buttons = [
        [KeyboardButton(text="🛒 خرید فیلترشکن")],
        [KeyboardButton(text="🎁 تست رایگان")],
        [KeyboardButton(text="📦 سرویس‌های من"), KeyboardButton(text="💰 کیف پول")],
        [KeyboardButton(text="🎫 پشتیبانی")],
    ]
    if is_admin:
        buttons.append([KeyboardButton(text="⚙️ پنل مدیریت")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def admin_menu():
    buttons = [
        [KeyboardButton(text="➕ افزودن کانفیگ")],
        [KeyboardButton(text="📊 موجودی کانفیگ‌ها")],
        [KeyboardButton(text="💳 درخواست‌های شارژ")],
        [KeyboardButton(text="🎫 تیکت‌های باز")],
        [KeyboardButton(text="👥 آمار کاربران")],
        [KeyboardButton(text="🔙 بازگشت به منوی کاربر")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def plans_keyboard():
    """نمایش پلن‌ها به صورت جدول — هر پلن یه دکمه خرید سبز جداگانه"""
    buttons = []
    for p in FIXED_PLANS:
        # ردیف اطلاعات پلن
        label = (
            f"📦 {p['name']}\n"
            f"💾 {p['traffic_gb']} گیگ  |  💰 {p['price']:,} تومان  |  ⏳ {p['duration_days']} روز"
        )
        buttons.append([InlineKeyboardButton(text=label, callback_data="noop")])
        # دکمه خرید سبز
        buttons.append([
            InlineKeyboardButton(
                text=f"🟢 خرید پلن {p['traffic_gb']} گیگ",
                callback_data=f"plan:{p['id']}"
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_plan_keyboard(plan_id):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ تایید و پرداخت", callback_data=f"confirm_plan:{plan_id}"),
        InlineKeyboardButton(text="❌ انصراف", callback_data="cancel"),
    ]])


def wallet_menu():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💳 شارژ کیف پول", callback_data="charge")
    ]])


def wallet_approve_keyboard(request_id):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ تایید", callback_data=f"wapprove:{request_id}"),
        InlineKeyboardButton(text="❌ رد", callback_data=f"wreject:{request_id}"),
    ]])


def admin_config_plans_keyboard():
    """برای ادمین: انتخاب پلن جهت افزودن کانفیگ"""
    buttons = [[
        InlineKeyboardButton(
            text=f"📦 {p['name']} ({p['traffic_gb']}G)",
            callback_data=f"addcfg:{p['id']}"
        )
    ] for p in FIXED_PLANS]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
