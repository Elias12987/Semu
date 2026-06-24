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


def is_admin(uid): return uid in ADMIN_IDS


class ProductFSM(StatesGroup):
    name        = State()
    category    = State()
    price       = State()
    duration    = State()
    traffic     = State()
    description = State()


class ConfigFSM(StatesGroup):
    waiting = State()


# ── پنل مدیریت ──────────────────────────────────────────

@router.message(F.text == "⚙️ پنل مدیریت")
async def admin_panel(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.clear()
    await message.answer("پنل مدیریت:", reply_markup=kb.admin_menu())


@router.message(F.text == "🔙 بازگشت به منوی کاربر")
async def back_to_user(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.clear()
    await message.answer("منوی کاربر:", reply_markup=kb.main_menu(True))


# ── ارسال کانفیگ به کاربر ───────────────────────────────

@router.callback_query(F.data.startswith("send_config:"))
async def send_config_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        await cb.answer("دسترسی نداری.", show_alert=True)
        return
    order_id = int(cb.data.split(":")[1])
    order = db.get_order(order_id)
    if not order:
        await cb.answer("سفارش پیدا نشد.", show_alert=True)
        return
    await state.update_data(order_id=order_id, user_id=order["user_id"])
    await cb.message.answer(f"کانفیگ رو برای سفارش #{order_id} بفرست:")
    await state.set_state(ConfigFSM.waiting)
    await cb.answer()


@router.message(ConfigFSM.waiting)
async def send_config_receive(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    config = message.text
    if not config:
        await message.answer("لطفا کانفیگ رو به صورت متنی بفرست.")
        return
    data = await state.get_data()
    order_id = data["order_id"]
    user_id  = data["user_id"]

    db.set_order_config(order_id, config)

    try:
        await message.bot.send_message(
            user_id,
            f"✅ سرویست آماده شد!\n\n`{config}`\n\nاین لینک رو در v2rayNG وارد کن.",
            parse_mode="Markdown",
        )
        await message.answer(f"✅ کانفیگ به کاربر {user_id} ارسال شد.")
    except Exception as e:
        await message.answer(f"❌ ارسال ناموفق: {e}")

    await state.clear()


@router.callback_query(F.data.startswith("reject_order:"))
async def reject_order(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        await cb.answer("دسترسی نداری.", show_alert=True)
        return
    order_id = int(cb.data.split(":")[1])
    order = db.get_order(order_id)
    if not order:
        await cb.answer("سفارش پیدا نشد.", show_alert=True)
        return

    # اگه پولی کم شده، برگردون
    if order["type"] == "paid" and order["product_id"]:
        p = db.get_product(order["product_id"])
        if p:
            db.change_balance(order["user_id"], p["price"])

    try:
        await cb.bot.send_message(order["user_id"], f"❌ سفارش #{order_id} رد شد. با پشتیبانی تماس بگیر.")
    except Exception:
        pass

    await cb.message.answer(f"سفارش #{order_id} رد شد.")
    await cb.answer()


# ── شارژ کیف پول ────────────────────────────────────────

@router.callback_query(F.data.startswith("wapprove:"))
async def wallet_approve(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        await cb.answer("دسترسی نداری.", show_alert=True)
        return
    rid = int(cb.data.split(":")[1])
    req = db.get_wallet_request(rid)
    if not req:
        await cb.answer("درخواست پیدا نشد.", show_alert=True)
        return
    if req["status"] != "pending":
        await cb.answer("قبلاً بررسی شده.", show_alert=True)
        return

    new_bal = db.change_balance(req["user_id"], req["amount"])
    db.set_wallet_request_status(rid, "approved")

    try:
        cap = (cb.message.caption or "") + f"\n\n✅ تایید شد | موجودی جدید: {new_bal:,} تومان"
        await cb.message.edit_caption(caption=cap)
    except Exception:
        pass

    try:
        await cb.bot.send_message(
            req["user_id"],
            f"✅ کیف پولت به مبلغ {req['amount']:,} تومان شارژ شد.\n💰 موجودی: {new_bal:,} تومان"
        )
    except Exception:
        pass

    await cb.answer("✅ تایید شد.")


@router.callback_query(F.data.startswith("wreject:"))
async def wallet_reject(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        await cb.answer("دسترسی نداری.", show_alert=True)
        return
    rid = int(cb.data.split(":")[1])
    req = db.get_wallet_request(rid)
    if not req:
        await cb.answer("درخواست پیدا نشد.", show_alert=True)
        return
    if req["status"] != "pending":
        await cb.answer("قبلاً بررسی شده.", show_alert=True)
        return

    db.set_wallet_request_status(rid, "rejected")

    try:
        cap = (cb.message.caption or "") + "\n\n❌ رد شد."
        await cb.message.edit_caption(caption=cap)
    except Exception:
        pass

    try:
        await cb.bot.send_message(req["user_id"], "❌ درخواست شارژ رد شد. با پشتیبانی تماس بگیر.")
    except Exception:
        pass

    await cb.answer("❌ رد شد.")


# ── افزودن محصول ────────────────────────────────────────

@router.message(F.text == "➕ افزودن محصول")
async def add_product_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await message.answer("نام محصول:")
    await state.set_state(ProductFSM.name)


@router.message(ProductFSM.name)
async def product_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    cats = "\n".join([f"{i+1}. {c}" for i, c in enumerate(CATEGORIES)])
    await message.answer(f"دسته‌بندی:\n{cats}\n\nعدد یا اسم دلخواه:")
    await state.set_state(ProductFSM.category)


@router.message(ProductFSM.category)
async def product_category(message: Message, state: FSMContext):
    t = message.text.strip()
    cat = CATEGORIES[int(t)-1] if t.isdigit() and 1 <= int(t) <= len(CATEGORIES) else t
    await state.update_data(category=cat)
    await message.answer("قیمت (تومان):")
    await state.set_state(ProductFSM.price)


@router.message(ProductFSM.price)
async def product_price(message: Message, state: FSMContext):
    if not message.text.strip().isdigit():
        await message.answer("فقط عدد.")
        return
    await state.update_data(price=int(message.text.strip()))
    await message.answer("مدت (روز):")
    await state.set_state(ProductFSM.duration)


@router.message(ProductFSM.duration)
async def product_duration(message: Message, state: FSMContext):
    if not message.text.strip().isdigit():
        await message.answer("فقط عدد.")
        return
    await state.update_data(duration=int(message.text.strip()))
    await message.answer("ترافیک (GB) — برای نامحدود 0:")
    await state.set_state(ProductFSM.traffic)


@router.message(ProductFSM.traffic)
async def product_traffic(message: Message, state: FSMContext):
    if not message.text.strip().isdigit():
        await message.answer("فقط عدد.")
        return
    await state.update_data(traffic=int(message.text.strip()))
    await message.answer("توضیحات (یا - برای رد):")
    await state.set_state(ProductFSM.description)


@router.message(ProductFSM.description)
async def product_description(message: Message, state: FSMContext):
    data = await state.get_data()
    desc = "" if message.text.strip() == "-" else message.text
    pid = db.add_product(
        name=data["name"], category=data["category"],
        price=data["price"], duration_days=data["duration"],
        traffic_gb=data["traffic"], description=desc,
    )
    await message.answer(f"✅ محصول #{pid} اضافه شد.", reply_markup=kb.admin_menu())
    await state.clear()


# ── لیست / حذف محصول ────────────────────────────────────

@router.message(F.text == "📋 لیست محصولات")
async def list_products(message: Message):
    if not is_admin(message.from_user.id): return
    products = db.list_products(active_only=False)
    if not products:
        await message.answer("محصولی ثبت نشده.")
        return
    for p in products:
        s = "✅" if p["active"] else "❌"
        await message.answer(
            f"{s} #{p['id']} {p['name']}\n{p['category']} | {p['price']:,} تومان | {p['duration_days']}روز | {p['traffic_gb']}GB",
            reply_markup=kb.product_manage_keyboard(p["id"])
        )


@router.callback_query(F.data.startswith("del_product:"))
async def del_product(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        await cb.answer("دسترسی نداری.", show_alert=True)
        return
    pid = int(cb.data.split(":")[1])
    db.delete_product(pid)
    await cb.message.answer(f"🗑 محصول #{pid} حذف شد.")
    await cb.answer()


# ── تیکت‌ها ─────────────────────────────────────────────

@router.message(F.text == "🎫 تیکت‌های باز")
async def open_tickets(message: Message):
    if not is_admin(message.from_user.id): return
    tickets = db.list_open_tickets()
    if not tickets:
        await message.answer("تیکت بازی نیست.")
        return
    for t in tickets:
        await message.answer(
            f"🎫 #{t['id']} از {t['user_id']}:\n{t['message']}\n\nپاسخ: /reply_{t['id']} متن"
        )


@router.message(F.text.startswith("/reply_"))
async def reply_ticket(message: Message):
    if not is_admin(message.from_user.id): return
    try:
        head, reply = message.text.split(" ", 1)
        tid = int(head.replace("/reply_", ""))
    except ValueError:
        await message.answer("فرمت: /reply_شماره متن")
        return
    ticket = db.get_ticket(tid)
    if not ticket:
        await message.answer("تیکت پیدا نشد.")
        return
    db.close_ticket(tid, reply)
    try:
        await message.bot.send_message(ticket["user_id"], f"📩 پاسخ پشتیبانی #{tid}:\n\n{reply}")
    except Exception:
        pass
    await message.answer("✅ پاسخ ارسال شد.")


# ── آمار ────────────────────────────────────────────────

@router.message(F.text == "👥 آمار کاربران")
async def stats(message: Message):
    if not is_admin(message.from_user.id): return
    users = db.get_all_users()
    orders = db.count_orders()
    total_bal = sum(u["balance"] for u in users)
    await message.answer(
        f"📊 آمار:\n👥 کاربران: {len(users)}\n📦 سفارش‌ها: {orders}\n💰 مجموع موجودی: {total_bal:,} تومان"
    )
