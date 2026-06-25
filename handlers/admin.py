# -*- coding: utf-8 -*-
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
import keyboards as kb
from config import ADMIN_IDS, FIXED_PLANS

router = Router()


def is_admin(uid): return uid in ADMIN_IDS

def get_plan(plan_id):
    return next((p for p in FIXED_PLANS if p["id"] == plan_id), None)


class ConfigFSM(StatesGroup):
    plan_id = State()
    waiting = State()


class ManualConfigFSM(StatesGroup):
    order_id = State()
    waiting  = State()


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


# ── افزودن کانفیگ به استخر ──────────────────────────────

@router.message(F.text == "➕ افزودن کانفیگ")
async def add_config_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await message.answer("برای کدام پلن کانفیگ اضافه می‌کنی؟", reply_markup=kb.admin_config_plans_keyboard())


@router.callback_query(F.data.startswith("addcfg:"))
async def add_config_select_plan(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        await cb.answer("دسترسی نداری.", show_alert=True)
        return
    plan_id = int(cb.data.split(":")[1])
    p = get_plan(plan_id)
    plan_name = p["name"] if p else "🎁 تست رایگان"
    await state.update_data(plan_id=plan_id)
    await cb.message.answer(
        f"✅ پلن انتخابی: <b>{plan_name}</b>\n\n"
        "کانفیگ‌ها رو بفرست — هر خط یه کانفیگ:\n"
        "<i>(مثلاً vless://... یا vmess://... یا ساب‌لینک)</i>",
        parse_mode="HTML"
    )
    await state.set_state(ConfigFSM.waiting)
    await cb.answer()


@router.message(ConfigFSM.waiting)
async def add_config_receive(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    plan_id = data["plan_id"]
    lines = [l.strip() for l in message.text.strip().splitlines() if l.strip()]
    for cfg in lines:
        db.add_config_to_pool(plan_id, cfg)
    p = get_plan(plan_id)
    plan_name = p["name"] if p else "🎁 تست رایگان"
    total = db.count_available_configs(plan_id)
    await message.answer(
        f"✅ {len(lines)} کانفیگ برای <b>{plan_name}</b> اضافه شد.\n"
        f"📦 موجودی الان: {total} کانفیگ",
        parse_mode="HTML",
        reply_markup=kb.admin_menu()
    )
    await state.clear()


# ── موجودی کانفیگ‌ها ────────────────────────────────────

@router.message(F.text == "📊 موجودی کانفیگ‌ها")
async def config_stock(message: Message):
    if not is_admin(message.from_user.id): return
    lines = ["📦 <b>موجودی کانفیگ‌ها:</b>\n━━━━━━━━━━━━━━━"]
    # تست رایگان
    free_count = db.count_available_configs(0)
    emoji = "🟢" if free_count > 2 else ("🟡" if free_count > 0 else "🔴")
    lines.append(f"{emoji} 🎁 تست رایگان: <b>{free_count}</b> کانفیگ")
    # پلن‌های پولی
    for p in FIXED_PLANS:
        count = db.count_available_configs(p["id"])
        emoji = "🟢" if count > 2 else ("🟡" if count > 0 else "🔴")
        lines.append(f"{emoji} {p['name']}: <b>{count}</b> کانفیگ")
    await message.answer("\n".join(lines), parse_mode="HTML")


# ── ارسال دستی کانفیگ (برای سفارش‌های بدون کانفیگ) ────

@router.message(F.text.startswith("/send_"))
async def manual_send_config(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try:
        parts = message.text.split(" ", 1)
        order_id = int(parts[0].replace("/send_", ""))
        config = parts[1].strip() if len(parts) > 1 else None
    except (ValueError, IndexError):
        await message.answer("فرمت: /send_شماره کانفیگ")
        return

    order = db.get_order(order_id)
    if not order:
        await message.answer("سفارش پیدا نشد.")
        return
    if not config:
        await message.answer(f"کانفیگ رو بعد از دستور بنویس:\n/send_{order_id} vless://...")
        return

    plan_id = order["plan_id"]
    p = get_plan(plan_id) if plan_id else None
    db.set_order_config(order_id, config)

    try:
        await message.bot.send_message(
            order["user_id"],
            f"💸 <b>خرید شما با موفقیت انجام شد</b>\n"
            "━━━━━━━━━━━━━━━\n"
            f"🔹 کاربر: <code>{order['user_id']}</code>\n"
            f"🔸 سرویس فعال: {p['name'] if p else 'سرویس'}\n"
            f"📍 موقعیت سرور: فرانسه 🇫🇷\n"
            f"⏳ اعتبار: {p['duration_days'] if p else 30} روز\n"
            f"📦 حجم اختصاصی: {p['traffic_gb'] if p else '—'} گیگابایت\n"
            "━━━━━━━━━━━━━━━\n"
            "🔗 <b>اطلاعات اتصال:</b>\n\n"
            f"<code>{config}</code>\n\n"
            "━━━━━━━━━━━━━━━\n"
            "⚡️ سرویس شما فعال شد و آماده استفاده است",
            parse_mode="HTML"
        )
        await message.answer(f"✅ کانفیگ سفارش #{order_id} ارسال شد.")
    except Exception as e:
        await message.answer(f"❌ ارسال ناموفق: {e}")


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
