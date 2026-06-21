# -*- coding: utf-8 -*-
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)


def main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="🛒 خرید فیلترشکن")],
        [KeyboardButton(text="💰 کیف پول"), KeyboardButton(text="🎫 پشتیبانی")],
        [KeyboardButton(text="📦 سرویس‌های من")],
    ]
    if is_admin:
        buttons.append([KeyboardButton(text="⚙️ پنل مدیریت")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def products_keyboard(products) -> InlineKeyboardMarkup:
    rows = []
    for p in products:
        text = f"{p['name']} - {p['price']:,} تومان"
        rows.append([InlineKeyboardButton(text=text, callback_data=f"buy:{p['id']}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_purchase_keyboard(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ تایید و خرید", callback_data=f"confirm_buy:{product_id}"),
                InlineKeyboardButton(text="❌ انصراف", callback_data="cancel"),
            ]
        ]
    )


def wallet_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="➕ شارژ کیف پول", callback_data="charge_wallet")]]
    )


def wallet_approve_keyboard(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ تایید", callback_data=f"wallet_approve:{request_id}"),
                InlineKeyboardButton(text="❌ رد", callback_data=f"wallet_reject:{request_id}"),
            ]
        ]
    )


def admin_menu() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="➕ افزودن محصول")],
        [KeyboardButton(text="📋 لیست محصولات")],
        [KeyboardButton(text="💳 درخواست‌های شارژ")],
        [KeyboardButton(text="🎫 تیکت‌های باز")],
        [KeyboardButton(text="🔙 بازگشت به منوی کاربر")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def product_manage_keyboard(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🗑 حذف", callback_data=f"del_product:{product_id}")]]
    )
