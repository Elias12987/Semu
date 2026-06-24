# -*- coding: utf-8 -*-
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
import keyboards as kb
from config import ADMIN_IDS, CARD_NUMBER, CARD_HOLDER

router = Router()


def is_admin(uid): return uid in ADMIN_IDS


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

    order_id = db.create_order(uid, None, "free")
    db.mark_free_used(uid)

    await message.answer("✅ درخواست تست رایگانت ثبت شد. تا چند دقیقه دیگه کانفیگ برات ارسال میشه.")

    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(
                admin_id,
                f"🎁 درخواست تست رایگان\n"
                f"کاربر: {uid} (@{message.from_user.username})\n"
                f"شناسه سفارش: #{order_id}",
                reply_markup=kb.order_action_keyboard(order_id),
            )
        except Exception:
            pass


# ── خرید ────────────────────────────────────────────────

@router.message(F.text == "🛒 خرید فیلترشکن")
async def show_categories(message: Message):
    db.get_or_create_user(message.from_user.id, message.from_user.username)
    cats = db.list_categories()
    if not cats:
        await message.answer("در حال حاضر محصولی موجود نیست.")
        return
    await message.answer("دسته‌بندی رو انتخاب کن:", reply_markup=kb.categories_keyboard(cats))


@router.callback_query(F.data == "back_cats")
async def back_cats(cb: CallbackQuery):
    cats = db.list_categories()
    await cb.message.answer("دسته‌بندی رو انتخاب کن:", reply_markup=kb.categories_keyboard(cats))
    await cb.answer()


@router.callback_query(F.data.startswith("cat:"))
async def show_products(cb: CallbackQuery):
    cat = cb.data.split(":", 1)[1]
    products = db.list_products(category=cat)
    if not products:
        await cb.answer("محصولی در این دسته نیست.", show_alert=True)
        return
    await cb.message.answer(f"پلن‌های «{cat}»:", reply_markup=kb.products_keyboard(products))
    await cb.answer()


@router.callback_query(F.data.startswith("buy:"))
async def select_product(cb: CallbackQuery):
    pid = int(cb.data.split(":")[1])
    p = db.get_product(pid)
    if not p:
        await cb.answer("این محصول موجود نیست.", show_alert=True)
        return
    balance = db.get_balance(cb.from_user.id)
    text = (
        f"📦 {p['name']}\n"
        f"💰 قیمت: {p['price']:,} تومان\n"
        f"⏳ مدت: {p['duration_days']} روز\n"
        f"📶 ترافیک: {p['traffic_gb']} GB\n"
        f"👛 موجودی شما: {balance:,} تومان"
    )
    if p.get("description"):
        text += f"\n\n{p['description']}"
    await cb.message.answer(text, reply_markup=kb.confirm_buy_keyboard(pid))
    await cb.answer()


@router.callback_query(F.data == "cancel")
async def cancel_cb(cb: CallbackQuery):
    await cb.message.answer("لغو شد.")
    await cb.answer()


@router.callback_query(F.data.startswith("confirm:"))
async def confirm_purchase(cb: CallbackQuery):
    pid   = int(cb.data.split(":")[1])
    uid   = cb.from_user.id
    p     = db.get_product(pid)

    if not p:
        await cb.answer("محصول موجود نیست.", show_alert=True)
        return

    db.get_or_create_user(uid, cb.from_user.username)
    balance = db.get_balance(uid)

    if balance < p["price"]:
        await cb.message.answer(
            f"❌ موجودی کافی نیست.\nموجودی: {balance:,} تومان | قیمت: {p['price']:,} تومان\n\n"
            "از بخش 💰 کیف پول شارژ کن."
        )
        await cb.answer()
        return

    # کم کردن موجودی
    new_balance = db.change_balance(uid, -p["price"])
    order_id = db.create_order(uid, pid, "paid")

    await cb.message.answer(
        f"✅ سفارش #{order_id} ثبت شد!\n"
        f"موجودی باقیمانده: {new_balance:,} تومان\n\n"
        "کانفیگ به زودی برات ارسال میشه. ⏳"
    )

    # اطلاع به ادمین
    for admin_id in ADMIN_IDS:
        try:
            await cb.bot.send_message(
                admin_id,
                f"🛒 سفارش جدید #{order_id}\n"
                f"کاربر: {uid} (@{cb.from_user.username})\n"
                f"محصول: {p['name']}\n"
                f"مبلغ: {p['price']:,} تومان",
                reply_markup=kb.order_action_keyboard(order_id),
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
        p = db.get_product(o["product_id"]) if o["product_id"] else None
        name = (p["name"] if p else "تست رایگان")
        await message.answer(f"📦 {name}\n\n`{o['config']}`", parse_mode="Markdown")


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
        f"`{6219-8619-5197-9607}`\nبه نام: {علی فرحانی}\n\n"
        "بعد عکس رسید رو همینجا بفرست.",
        parse_mode="Markdown",
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
