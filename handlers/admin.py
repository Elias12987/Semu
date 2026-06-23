# -*- coding: utf-8 -*-
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
import keyboards as kb
from config import ADMIN_IDS

router = Router()

CATEGORIES = ["نت ملی", "گیم", "پرسرعت", "عادی"]


def admin_only(user_id: int) -> bool:
    return user_id in ADMIN_IDS


class ProductStates(StatesGroup):
    name = State()
    category = State()
    price = State()
    duration = State()
    traffic = State()
    inbound_id = State()
    description = State()


# ==================== پنل مدیریت ====================

@router.message(F.text == "⚙️ پنل مدیریت")
async def admin_panel(message: Message, state: FSMContext):
    if not admin_only(message.from_user.id):
        return
    await state.clear()
    await message.answer("پنل مدیریت:", reply_markup=kb.admin_menu())


@router.message(F.text == "🔙 بازگشت به منوی کاربر")
async def back_to_user(message: Message, state: FSMContext):
    if not admin_only(message.from_user.id):
        return
    await state.clear()
    await message.answer("برگشتی به منوی کاربر.", reply_markup=kb.main_menu(True))


# ==================== افزودن محصول ====================

@router.message(F.text == "➕ افزودن محصول")
async def add_product_start(message: Message, state: FSMContext):
    if not admin_only(message.from_user.id):
        return
    await message.answer("نام محصول رو وارد کن:")
    await state.set_state(ProductStates.name)


@router.message(ProductStates.name)
async def add_product_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    cats = "\n".join([f"{i+1}. {c}" for i, c in enumerate(CATEGORIES)])
    await message.answer(f"دسته‌بندی:\n\n{cats}\n\nعدد یا اسم دلخواه بفرست:")
    await state.set_state(ProductStates.category)


@router.message(ProductStates.category)
async def add_product_category(message: Message, state: FSMContext):
    text = message.text.strip()
    if text.isdigit():
        idx = int(text) - 1
        if 0 <= idx < len(CATEGORIES):
            category = CATEGORIES[idx]
        else:
            await message.answer(f"عدد باید بین ۱ تا {len(CATEGORIES)} باشه.")
            return
    else:
        category = text
    await state.update_data(category=category)
    await message.answer("قیمت رو به تومان وارد کن:")
    await state.set_state(ProductStates.price)


@router.message(ProductStates.price)
async def add_product_price(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("فقط عدد وارد کن.")
        return
    await state.update_data(price=int(message.text.strip()))
    await message.answer("مدت زمان سرویس رو به روز وارد کن:")
    await state.set_state(ProductStates.duration)


@router.message(ProductStates.duration)
async def add_product_duration(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("فقط عدد وارد کن.")
        return
    await state.update_data(duration=int(message.text.strip()))
    await message.answer("حجم ترافیک به گیگابایت (برای نامحدود 0 بزن):")
    await state.set_state(ProductStates.traffic)


@router.message(ProductStates.traffic)
async def add_product_traffic(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("فقط عدد وارد کن.")
        return
    await state.update_data(traffic=int(message.text.strip()))
    await message.answer("آیدی Inbound در پنل 3X-UI رو وارد کن:")
    await state.set_state(ProductStates.inbound_id)


@router.message(ProductStates.inbound_id)
async def add_product_inbound(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("فقط عدد وارد کن.")
        return
    await state.update_data(inbound_id=int(message.text.strip()))
    await message.answer("توضیحات محصول (یا - برای رد کردن):")
    await state.set_state(ProductStates.description)


@router.message(ProductStates.description)
async def add_product_description(message: Message, state: FSMContext):
    data = await state.get_data()
    description = "" if (message.text or "").strip() == "-" else message.text

    pid = db.add_product(
        name=data["name"],
        category=data["category"],
        price=data["price"],
        duration_days=data["duration"],
        traffic_gb=data["traffic"],
        inbound_id=data["inbound_id"],
        description=description,
    )
    await message.answer(f"✅ محصول #{pid} اضافه شد.", reply_markup=kb.admin_menu())
    await state.clear()


# ==================== لیست / حذف ====================

@router.message(F.text == "📋 لیست محصولات")
async def list_products(message: Message):
    if not admin_only(message.from_user.id):
        return
    products = db.list_products(active_only=False)
    if not products:
        await message.answer("محصولی ثبت نشده.")
        return
    for p in products:
        status = "✅" if p["active"] else "❌"
        text = (
            f"{status} #{p['id']} - {p['name']}\n"
            f"دسته: {p['category']} | قیمت: {p['price']:,} تومان\n"
            f"{p['duration_days']} روز | {p['traffic_gb']}GB | Inbound: {p['inbound_id']}"
        )
        await message.answer(text, reply_markup=kb.product_manage_keyboard(p["id"]))


@router.callback_query(F.data.startswith("del_product:"))
async def delete_product(callback: CallbackQuery):
    if not admin_only(callback.from_user.id):
        await callback.answer("دسترسی نداری.", show_alert=True)
        return
    product_id = int(callback.data.split(":")[1])
    db.delete_product(product_id)
    await callback.message.answer(f"🗑 محصول #{product_id} حذف شد.")
    await callback.answer()


# ==================== شارژ کیف پول ====================

@router.message(F.text == "💳 درخواست‌های شارژ")
async def pending_wallet_requests(message: Message):
    if not admin_only(message.from_user.id):
        return
    await message.answer(
        "درخواست‌های شارژ به محض ثبت، همراه با رسید و دکمه‌های تایید/رد برات ارسال میشن."
    )


@router.callback_query(F.data.startswith("wallet_approve:"))
async def wallet_approve(callback: CallbackQuery):
    if not admin_only(callback.from_user.id):
        await callback.answer("دسترسی نداری.", show_alert=True)
        return

    request_id = int(callback.data.split(":")[1])
    req = db.get_wallet_request(request_id)

    if not req:
        await callback.answer("درخواست پیدا نشد.", show_alert=True)
        return
    if req["status"] != "pending":
        await callback.answer("این درخواست قبلاً بررسی شده.", show_alert=True)
        return

    # آپدیت موجودی
    new_balance = db.change_balance(req["user_id"], req["amount"])
    db.set_wallet_request_status(request_id, "approved")

    # آپدیت کپشن پیام ادمین
    try:
        new_caption = (callback.message.caption or "") + f"\n\n✅ تایید شد. موجودی جدید کاربر: {new_balance:,} تومان"
        await callback.message.edit_caption(caption=new_caption)
    except Exception:
        pass

    # اطلاع به کاربر
    try:
        await callback.bot.send_message(
            req["user_id"],
            f"✅ کیف پولت به مبلغ {req['amount']:,} تومان شارژ شد.\n"
            f"💰 موجودی فعلی: {new_balance:,} تومان"
        )
    except Exception:
        pass

    await callback.answer("✅ تایید شد.")


@router.callback_query(F.data.startswith("wallet_reject:"))
async def wallet_reject(callback: CallbackQuery):
    if not admin_only(callback.from_user.id):
        await callback.answer("دسترسی نداری.", show_alert=True)
        return

    request_id = int(callback.data.split(":")[1])
    req = db.get_wallet_request(request_id)

    if not req:
        await callback.answer("درخواست پیدا نشد.", show_alert=True)
        return
    if req["status"] != "pending":
        await callback.answer("این درخواست قبلاً بررسی شده.", show_alert=True)
        return

    db.set_wallet_request_status(request_id, "rejected")

    try:
        new_caption = (callback.message.caption or "") + "\n\n❌ رد شد."
        await callback.message.edit_caption(caption=new_caption)
    except Exception:
        pass

    try:
        await callback.bot.send_message(
            req["user_id"],
            "❌ درخواست شارژ کیف پولت رد شد. با پشتیبانی تماس بگیر."
        )
    except Exception:
        pass

    await callback.answer("❌ رد شد.")


# ==================== تیکت‌ها ====================

@router.message(F.text == "🎫 تیکت‌های باز")
async def open_tickets(message: Message):
    if not admin_only(message.from_user.id):
        return
    tickets = db.list_open_tickets()
    if not tickets:
        await message.answer("تیکت بازی وجود نداره.")
        return
    for t in tickets:
        await message.answer(
            f"🎫 #{t['id']} از کاربر {t['user_id']}:\n{t['message']}\n\n"
            f"پاسخ: /reply_{t['id']} متن_پاسخ"
        )


@router.message(F.text.startswith("/reply_"))
async def reply_ticket(message: Message):
    if not admin_only(message.from_user.id):
        return
    try:
        head, reply_text = message.text.split(" ", 1)
        ticket_id = int(head.replace("/reply_", ""))
    except ValueError:
        await message.answer("فرمت: /reply_شماره متن_پاسخ")
        return

    ticket = db.get_ticket(ticket_id)
    if not ticket:
        await message.answer("تیکتی با این شماره پیدا نشد.")
        return

    db.close_ticket(ticket_id, reply_text)
    try:
        await message.bot.send_message(
            ticket["user_id"],
            f"📩 پاسخ پشتیبانی به تیکت #{ticket_id}:\n\n{reply_text}"
        )
    except Exception:
        pass
    await message.answer("✅ پاسخ ارسال شد.")


# ==================== آمار ====================

@router.message(F.text == "👥 آمار کاربران")
async def users_stats(message: Message):
    if not admin_only(message.from_user.id):
        return
    users = db.get_all_users()
    total_orders = db.count_orders()
    total_balance = sum(u["balance"] for u in users)
    await message.answer(
        f"📊 آمار ربات:\n\n"
        f"👥 تعداد کاربران: {len(users)}\n"
        f"📦 تعداد سفارش‌ها: {total_orders}\n"
        f"💰 مجموع موجودی کاربران: {total_balance:,} تومان"
    )
