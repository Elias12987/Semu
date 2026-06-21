# -*- coding: utf-8 -*-
import io
import os

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import qrcode

import database as db
import keyboards as kb
from config import ADMIN_IDS, CARD_NUMBER, CARD_HOLDER
from panel_api import ThreeXUIClient, PanelError

router = Router()


class WalletStates(StatesGroup):
    waiting_amount = State()
    waiting_receipt = State()


class SupportStates(StatesGroup):
    waiting_message = State()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


@router.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    db.get_or_create_user(message.from_user.id, message.from_user.username)
    await message.answer(
        "به ربات فروش فیلترشکن خوش اومدی 👋\nاز منوی پایین یکی از گزینه‌ها رو انتخاب کن:",
        reply_markup=kb.main_menu(is_admin(message.from_user.id)),
    )


# ==================== خرید سرویس ====================

@router.message(F.text == "🛒 خرید فیلترشکن")
async def show_products(message: Message):
    products = db.list_products()
    if not products:
        await message.answer("در حال حاضر محصولی موجود نیست.")
        return
    await message.answer("یکی از پلن‌ها رو انتخاب کن:", reply_markup=kb.products_keyboard(products))


@router.callback_query(F.data.startswith("buy:"))
async def select_product(callback: CallbackQuery):
    product_id = int(callback.data.split(":")[1])
    product = db.get_product(product_id)
    if not product:
        await callback.answer("این محصول دیگر موجود نیست.", show_alert=True)
        return
    text = (
        f"📦 {product['name']}\n"
        f"💰 قیمت: {product['price']:,} تومان\n"
        f"⏳ مدت: {product['duration_days']} روز\n"
        f"📶 ترافیک: {product['traffic_gb']} گیگابایت\n\n"
        f"{product.get('description') or ''}"
    )
    await callback.message.answer(text, reply_markup=kb.confirm_purchase_keyboard(product_id))
    await callback.answer()


@router.callback_query(F.data == "cancel")
async def cancel_callback(callback: CallbackQuery):
    await callback.message.answer("لغو شد.")
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_buy:"))
async def confirm_purchase(callback: CallbackQuery):
    product_id = int(callback.data.split(":")[1])
    product = db.get_product(product_id)
    user_id = callback.from_user.id

    if not product:
        await callback.answer("این محصول دیگر موجود نیست.", show_alert=True)
        return

    balance = db.get_balance(user_id)
    if balance < product["price"]:
        await callback.message.answer(
            f"موجودی کیف پولت کافی نیست.\n"
            f"موجودی فعلی: {balance:,} تومان\n"
            f"قیمت پلن: {product['price']:,} تومان\n"
            f"از بخش 💰 کیف پول شارژ کن."
        )
        await callback.answer()
        return

    await callback.message.answer("⏳ در حال ساخت سرویس روی سرور، چند لحظه صبر کن...")

    client = ThreeXUIClient()
    email = f"user{user_id}_{product_id}_{os.urandom(2).hex()}"
    try:
        result = client.add_client(
            inbound_id=product["inbound_id"],
            email=email,
            traffic_gb=product["traffic_gb"],
            duration_days=product["duration_days"],
        )
    except Exception as e:  # noqa: BLE001
        await callback.message.answer(
            "❌ متاسفانه ساخت سرویس روی سرور ناموفق بود. لطفا با پشتیبانی تماس بگیر."
        )
        for admin_id in ADMIN_IDS:
            await callback.bot.send_message(admin_id, f"⚠️ خطا در ساخت کلاینت برای کاربر {user_id}: {e}")
        await callback.answer()
        return

    db.change_balance(user_id, -product["price"])
    db.create_order(user_id, product_id, result["link"], result["uuid"])

    qr_img = qrcode.make(result["link"])
    buf = io.BytesIO()
    qr_img.save(buf, format="PNG")
    buf.seek(0)
    buf.name = "config.png"

    await callback.message.answer_photo(
        photo=buf,
        caption=(
            "✅ سرویس با موفقیت ساخته شد!\n\n"
            f"`{result['link']}`\n\n"
            "این لینک رو در v2rayNG وارد کن یا QR Code بالا رو اسکن کن."
        ),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.message(F.text == "📦 سرویس‌های من")
async def my_orders(message: Message):
    orders = db.list_orders(message.from_user.id)
    if not orders:
        await message.answer("هنوز هیچ سرویسی نخریدی.")
        return
    for o in orders:
        product = db.get_product(o["product_id"])
        name = product["name"] if product else "نامشخص"
        await message.answer(f"📦 {name}\n`{o['config_link']}`", parse_mode="Markdown")


# ==================== کیف پول ====================

@router.message(F.text == "💰 کیف پول")
async def wallet_info(message: Message, state: FSMContext):
    await state.clear()
    balance = db.get_balance(message.from_user.id)
    await message.answer(f"💰 موجودی فعلی شما: {balance:,} تومان", reply_markup=kb.wallet_menu())


@router.callback_query(F.data == "charge_wallet")
async def charge_wallet_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("مبلغ مورد نظر برای شارژ رو به تومان وارد کن (فقط عدد):")
    await state.set_state(WalletStates.waiting_amount)
    await callback.answer()


@router.message(WalletStates.waiting_amount)
async def charge_wallet_amount(message: Message, state: FSMContext):
    if not message.text or not message.text.isdigit():
        await message.answer("لطفا فقط عدد وارد کن.")
        return
    amount = int(message.text)
    await state.update_data(amount=amount)
    await message.answer(
        f"مبلغ {amount:,} تومان رو به شماره کارت زیر واریز کن:\n\n"
        f"`{CARD_NUMBER}`\nبه نام: {CARD_HOLDER}\n\n"
        "بعد از واریز، عکس رسید رو همینجا بفرست.",
        parse_mode="Markdown",
    )
    await state.set_state(WalletStates.waiting_receipt)


@router.message(WalletStates.waiting_receipt, F.photo)
async def charge_wallet_receipt(message: Message, state: FSMContext):
    data = await state.get_data()
    amount = data.get("amount")
    file_id = message.photo[-1].file_id

    request_id = db.create_wallet_request(message.from_user.id, amount, file_id)
    await message.answer("✅ رسید دریافت شد و برای بررسی به ادمین ارسال شد. بعد از تایید، کیف پولت شارژ میشه.")

    for admin_id in ADMIN_IDS:
        await message.bot.send_photo(
            admin_id,
            photo=file_id,
            caption=(
                "💳 درخواست شارژ کیف پول جدید\n"
                f"کاربر: {message.from_user.id} (@{message.from_user.username})\n"
                f"مبلغ: {amount:,} تومان\n"
                f"شماره درخواست: {request_id}"
            ),
            reply_markup=kb.wallet_approve_keyboard(request_id),
        )
    await state.clear()


@router.message(WalletStates.waiting_receipt)
async def charge_wallet_receipt_invalid(message: Message):
    await message.answer("لطفا عکس رسید واریز رو ارسال کن.")


# ==================== پشتیبانی ====================

@router.message(F.text == "🎫 پشتیبانی")
async def support_start(message: Message, state: FSMContext):
    await message.answer("پیامت رو بنویس، برای ادمین ارسال میشه و در اولین فرصت پاسخ داده میشه.")
    await state.set_state(SupportStates.waiting_message)


@router.message(SupportStates.waiting_message)
async def support_send(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("لطفا پیامت رو به صورت متنی بفرست.")
        return
    ticket_id = db.create_ticket(message.from_user.id, message.text)
    await message.answer("✅ پیامت ثبت شد. منتظر پاسخ پشتیبانی باش.")
    for admin_id in ADMIN_IDS:
        await message.bot.send_message(
            admin_id,
            f"🎫 تیکت جدید #{ticket_id}\n"
            f"از کاربر: {message.from_user.id} (@{message.from_user.username})\n\n"
            f"{message.text}\n\n"
            f"برای پاسخ از این دستور استفاده کن:\n/reply_{ticket_id} متن پاسخ",
        )
    await state.clear()
