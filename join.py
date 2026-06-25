from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

join_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(
            text="📢 عضویت در کانال",
            url="https://t.me/VPN_IRONMANl"
        )],
        [InlineKeyboardButton(
            text="✅ بررسی عضویت",
            callback_data="check_join"
        )]
    ]
)