# -*- coding: utf-8 -*-
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)


def main_menu(is_admin=False):
    buttons = [
        [KeyboardButton(text="🛒 خرید فیلترشکن")],
        [KeyboardButton(text="🎁 تست رایگان")],
        [KeyboardButton(text="📦 سرویس‌های من"), KeyboardButton(text="💰 کیف پول")],
        [KeyboardButton(text="🎫 پشتیبانی")],

    if is_admin:
        buttons.append([KeyboardButton(text="⚙️ پنل مدیریت")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def admin_menu():
    buttons = [
        [KeyboardButton(text="➕ افزودن محصول")],
        [KeyboardButton(text="📋 لیست محصولات")],
        [KeyboardButton(text="💳 درخواست‌های شارژ")],
        [KeyboardButton(text="🎫 تیکت‌های باز")],
        [KeyboardButton(text="👥 آمار کاربران")],
        [KeyboardButton(text="🔙 بازگشت به منوی کاربر")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def categories_keyboard(categories):
    buttons = [[InlineKeyboardButton(text=c, callback_data=f"cat:{c}")] for c in categories]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def products_keyboard(products):
    buttons = []
    for p in products:
        label = f"{p['name']} | {p['price']:,} تومان | {p['traffic_gb']}GB | {p['duration_days']} روز"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"buy:{p['id']}")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="back_cats")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_buy_keyboard(product_id):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ تایید خرید", callback_data=f"confirm:{product_id}"),
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


def order_action_keyboard(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📤 ارسال کانفیگ", callback_data=f"send_config:{order_id}"),
        InlineKeyboardButton(text="❌ رد سفارش", callback_data=f"reject_order:{order_id}"),
    ]])


def product_manage_keyboard(product_id):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🗑 حذف", callback_data=f"del_product:{product_id}")
    ]])
