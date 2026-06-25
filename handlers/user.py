# -*- coding: utf-8 -*-
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
import keyboards as kb
from config import ADMIN_IDS, CARD_NUMBER, CARD_HOLDER, FIXED_PLANS, SERVER_LOCATION, SERVER_NAME

router = Router()


def is_admin(uid): return uid in ADMIN_IDS

def get_plan(plan_id):
    return next((p for p in FIXED_PLANS if p["id"] == plan_id), None)


class WalletFSM(StatesGroup):
    amount  = State()
    receipt = State()


class SupportFSM(StatesGroup):
    msg = State()


# ── /start ──────────────────────────────────────────────

@router.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    db.get_or_create_user(message.from_user.id, message.from_user.username)
    await message.answer(
        "به ربات فروش فیلترشکن خوش اومدی 👋\nاز منو یه گزینه انتخاب کن:",
        reply_markup=kb.main_menu(is_admin(message.from_user.id)),
    )


# ── تست رایگان ─────────────────────────────────────────

@router.message(F.text == "🎁 تست رایگان")
async def free_test(message: Message):
    uid = message.from_user.id
    db.get_or_create_user(uid, message.from_user.username)
    if db.has_used_free(uid):
        await message.answer("❌ قبلاً از تست رایگان استفاده کردی.")
        return
    order_id = db.create_order(uid, 0, "free")
    db.mark_free_used(uid)

    config = db.pop_config_from_pool(0)

    if config:
        db.set_order_config(order_id, config)
        await message.answer(
            "🎁 <b>تست رایگان شما آماده شد!</b>\n"
            "━━━━━━━━━━━━━━━\n"
            f"🔹 کاربر: <code>{uid}</code>\n"
            "🔸 سرویس: تست رایگان\n"
            "📍 موقعیت سرور: فرانسه 🇫🇷\n"
            "⏳ اعتبار: 1 روز\n"
    "📦 حجم اختصاصی: 1 گیگابایت\n"
            "━━━━━━━━━━━━━━━\n"
            "🔗 <b>اطلاعات اتصال:</b>\n\n"
            f"<code>{config}</code>\n\n"
            "━━━━━━━━━━━━━━━\n"
            "⚡️ سرویس شما فعال شد و آماده استفاده است",
            parse_mode="HTML"
        )
        for admin_id in ADMIN_IDS:
            try:
                await message.bot.send_message(
                    admin_id,
                    f"🎁 تست رایگان — کانفیگ خودکار ارسال شد\n"
                    f"کاربر: {uid} (@{message.from_user.username})\n"
                    f"کانفیگ‌های تست باقی‌مانده: {db.count_available_configs(0)} عدد"
                )
            except Exception:
                pass
    else:
        await message.answer("✅ درخواست تست رایگانت ثبت شد. تا چند دقیقه دیگه کانفیگ برات ارسال میشه.")
        for admin_id in ADMIN_IDS:
            try:
                await message.bot.send_message(
                    admin_id,
                    f"🎁 درخواست تست رایگان — کانفیگ موجود نیست!\n"
                    f"کاربر: {uid} (@{message.from_user.username})\n"
                    f"سفارش: #{order_id}\n\n"
                    "❗️ لطفاً از پنل مدیریت کانفیگ تست اضافه کن.",
                )
            except Exception:
                pass


# ── خرید ────────────────────────────────────────────────

@router.message(F.text == "🛒 خرید فیلترشکن")
async def show_plans(message: Message):
    db.get_or_create_user(message.from_user.id, message.from_user.username)
    text = (
        "🛍 <b>پلن‌های موجود — پنل عادی</b>\n"
        "━━━━━━━━━━━━━━━\n"
        "یه پلن انتخاب کن و دکمه 🟢 خرید رو بزن:"
    )
    await message.answer(text, reply_markup=kb.plans_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "noop")
async def noop(cb: CallbackQuery):
    await cb.answer()


@router.callback_query(F.data.startswith("plan:"))
async def select_plan(cb: CallbackQuery):
    plan_id = int(cb.data.split(":")[1])
    p = get_plan(plan_id)
    if not p:
        await cb.answer("این پلن موجود نیست.", show_alert=True)
        return
    balance = db.get_balance(cb.from_user.id)
    text = (
        f"📦 <b>{p['name']}</b>\n"
        "━━━━━━━━━━━━━━━\n"
        f"💾 حجم: <b>{p['traffic_gb']} گیگابایت</b>\n"
        f"💰 قیمت: <b>{p['price']:,} تومان</b>\n"
        f"⏳ مدت: <b>{p['duration_days']} روز</b>\n"
        f"📍 سرور: <b>{SERVER_LOCATION}</b>\n"
        "━━━━━━━━━━━━━━━\n"
        f"👛 موجودی شما: <b>{balance:,} تومان</b>"
    )
    await cb.message.answer(text, reply_markup=kb.confirm_plan_keyboard(plan_id), parse_mode="HTML")
    await cb.answer()


@router.callback_query(F.data == "cancel")
async def cancel_cb(cb: CallbackQuery):
    await cb.message.answer("لغو شد.")
    await cb.answer()


@router.callback_query(F.data.startswith("confirm_plan:"))
async def confirm_purchase(cb: CallbackQuery):
    plan_id = int(cb.data.split(":")[1])
    uid = cb.from_user.id
    p = get_plan(plan_id)

    if not p:
        await cb.answer("پلن موجود نیست.", show_alert=True)
        return

    db.get_or_create_user(uid, cb.from_user.username)
    balance = db.get_balance(uid)

    if balance < p["price"]:
        await cb.message.answer(
            f"❌ موجودی کافی نیست.\n"
            f"موجودی: {balance:,} تومان | قیمت: {p['price']:,} تومان\n\n"
            "از بخش 💰 کیف پول شارژ کن."
        )
        await cb.answer()
        return

    # بررسی موجودی کانفیگ
    config = db.pop_config_from_pool(plan_id)

    # کم کردن موجودی و ثبت سفارش
    db.change_balance(uid, -p["price"])
    order_id = db.create_order(uid, plan_id, "paid")

    if config:
        # کانفیگ آماده بود — بده به کاربر
        db.set_order_config(order_id, config)
        await cb.message.answer(
            f"💸 <b>خرید شما با موفقیت انجام شد</b>\n"
            "━━━━━━━━━━━━━━━\n"
            f"🔹 کاربر: <code>{uid}</code>\n"
            f"🔸 سرویس فعال: {SERVER_NAME}\n"
            f"📍 موقعیت سرور: {SERVER_LOCATION}\n"
            f"⏳ اعتبار: {p['duration_days']} روز\n"
            f"📦 حجم اختصاصی: {p['traffic_gb']} گیگابایت\n"
            "━━━━━━━━━━━━━━━\n"
            "🔗 <b>اطلاعات اتصال:</b>\n\n"
            f"<code>{config}</code>\n\n"
            "━━━━━━━━━━━━━━━\n"
            "⚡️ سرویس شما فعال شد و آماده استفاده است",
            parse_mode="HTML",
        )
        # اطلاع به ادمین
        for admin_id in ADMIN_IDS:
            try:
                await cb.bot.send_message(
                    admin_id,
                    f"🛒 سفارش جدید #{order_id} — کانفیگ خودکار ارسال شد\n"
                    f"کاربر: {uid} (@{cb.from_user.username})\n"
                    f"پلن: {p['name']} | {p['price']:,} تومان\n"
                    f"کانفیگ‌های باقی‌مانده: {db.count_available_configs(plan_id)} عدد"
                )
            except Exception:
                pass
    else:
        # کانفیگ موجود نیست — به ادمین اطلاع بده
        await cb.message.answer(
            f"💸 <b>خرید شما با موفقیت انجام شد</b>\n"
            "━━━━━━━━━━━━━━━\n"
            f"🔹 کاربر: <code>{uid}</code>\n"
            f"🔸 سرویس فعال: {SERVER_NAME}\n"
            f"📍 موقعیت سرور: {SERVER_LOCATION}\n"
            f"⏳ اعتبار: {p['duration_days']} روز\n"
            f"📦 حجم اختصاصی: {p['traffic_gb']} گیگابایت\n"
            "━━━━━━━━━━━━━━━\n"
            "⏳ کانفیگ به زودی برات ارسال میشه — ادمین در حال آماده‌سازیه.",
            parse_mode="HTML",
        )
        for admin_id in ADMIN_IDS:
            try:
                await cb.bot.send_message(
                    admin_id,
                    f"⚠️ سفارش جدید #{order_id} — کانفیگ موجود نیست!\n"
                    f"کاربر: {uid} (@{cb.from_user.username})\n"
                    f"پلن: {p['name']} | {p['price']:,} تومان\n\n"
                    "❗️ لطفاً از پنل مدیریت کانفیگ اضافه کن و سفارش رو تکمیل کن."
                )
            except Exception:
                pass

    await cb.answer()


# ── سرویس‌های من ────────────────────────────────────────

@router.message(F.text == "📦 سرویس‌های من")
async def my_orders(message: Message):
    db.get_or_create_user(message.from_user.id, message.from_user.username)
    orders = db.list_orders(message.from_user.id)
    done = [o for o in orders if o["config"]]
    if not done:
        await message.answer("هنوز سرویس فعالی نداری.")
        return
    for o in done:
        p = get_plan(o["plan_id"]) if o["plan_id"] else None
        name = p["name"] if p else "تست رایگان"
        expires = o.get("expires_at", "")[:10] if o.get("expires_at") else "—"
        await message.answer(
            f"📦 <b>{name}</b>\n"
            f"⏳ انقضا: {expires}\n\n"
            f"<code>{o['config']}</code>",
            parse_mode="HTML"
        )


# ── کیف پول ────────────────────────────────────────────

@router.message(F.text == "💰 کیف پول")
async def wallet_info(message: Message, state: FSMContext):
    await state.clear()
    db.get_or_create_user(message.from_user.id, message.from_user.username)
    bal = db.get_balance(message.from_user.id)
    await message.answer(f"👛 موجودی: {bal:,} تومان", reply_markup=kb.wallet_menu())


@router.callback_query(F.data == "charge")
async def charge_start(cb: CallbackQuery, state: FSMContext):
    await cb.message.answer("مبلغ مورد نظر برای شارژ رو به تومان وارد کن:")
    await state.set_state(WalletFSM.amount)
    await cb.answer()


@router.message(WalletFSM.amount)
async def charge_amount(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("فقط عدد وارد کن.")
        return
    amount = int(message.text.strip())
    if amount < 1000:
        await message.answer("حداقل مبلغ ۱۰۰۰ تومانه.")
        return
    await state.update_data(amount=amount)
    await message.answer(
        f"مبلغ {amount:,} تومان رو به کارت زیر واریز کن:\n\n"
        f"<code>{CARD_NUMBER}</code>\nبه نام: {CARD_HOLDER}\n\n"
        "بعد عکس رسید رو همینجا بفرست.",
        parse_mode="HTML",
    )
    await state.set_state(WalletFSM.receipt)


@router.message(WalletFSM.receipt, F.photo)
async def charge_receipt(message: Message, state: FSMContext):
    data = await state.get_data()
    amount = data.get("amount")
    file_id = message.photo[-1].file_id
    rid = db.create_wallet_request(message.from_user.id, amount, file_id)
    await message.answer("✅ رسید دریافت شد و برای ادمین ارسال شد.")
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_photo(
                admin_id,
                photo=file_id,
                caption=(
                    f"💳 درخواست شارژ #{rid}\n"
                    f"کاربر: {message.from_user.id} (@{message.from_user.username})\n"
                    f"مبلغ: {amount:,} تومان"
                ),
                reply_markup=kb.wallet_approve_keyboard(rid),
            )
        except Exception:
            pass
    await state.clear()


@router.message(WalletFSM.receipt)
async def charge_receipt_invalid(message: Message):
    await message.answer("لطفا عکس رسید رو بفرست.")


# ── پشتیبانی ────────────────────────────────────────────

@router.message(F.text == "🎫 پشتیبانی")
async def support_start(message: Message, state: FSMContext):
    await message.answer("پیامت رو بنویس:")
    await state.set_state(SupportFSM.msg)


@router.message(SupportFSM.msg)
async def support_send(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("پیام متنی بفرست.")
        return
    tid = db.create_ticket(message.from_user.id, message.text)
    await message.answer(f"✅ تیکت #{tid} ثبت شد.")
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(
                admin_id,
                f"🎫 تیکت #{tid}\nاز: {message.from_user.id} (@{message.from_user.username})\n\n"
                f"{message.text}\n\nپاسخ: /reply_{tid} متن"
            )
        except Exception:
            pass
    await state.clear()
