import logging
import random
import string
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler
from config import *
from database import *
from keyboards import *

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# States for conversation
WAITING_FOR_MESSAGE = 1

def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    return user_id == ADMIN_USER_ID

# ==================== START COMMAND ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    session = get_session()
    
    try:
        # Check if user exists
        db_user = session.query(User).filter_by(user_id=user.id).first()
        
        if not db_user:
            # Generate unique referral code
            referral_code = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
            
            # Ensure unique referral code
            while session.query(User).filter_by(referral_code=referral_code).first():
                referral_code = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
            
            # Check for referral
            referred_by = None
            if context.args and len(context.args) > 0:
                ref_code = context.args[0]
                referrer = session.query(User).filter_by(referral_code=ref_code).first()
                if referrer and referrer.user_id != user.id:
                    referred_by = referrer.user_id
                    # Award referral points
                    referrer.referral_points += REFERRAL_POINTS
                    
                    # Notify referrer
                    try:
                        await context.bot.send_message(
                            chat_id=referrer.user_id,
                            text=f"🎉 کاربر جدید با کد دعوت شما ثبت‌نام کرد!\n"
                                 f"➕ {REFERRAL_POINTS} امتیاز به حساب شما اضافه شد.\n"
                                 f"⭐ مجموع امتیاز: {referrer.referral_points}"
                        )
                    except Exception as e:
                        logger.error(f"Could not notify referrer: {e}")
            
            # Create new user
            new_user = User(
                user_id=user.id,
                username=user.username or "",
                full_name=user.full_name or "Unknown",
                referral_code=referral_code,
                referred_by=referred_by,
                wallet_balance=0,
                referral_points=0
            )
            session.add(new_user)
            session.commit()
            
            welcome_text = (
                f"🎉 سلام {user.full_name}!\n"
                f"به ربات فروش فیلترشکن خوش آمدید!\n\n"
                f"🔐 با خرید از ما، امنیت و آزادی اینترنت رو تجربه کنید!\n\n"
                f"🎁 کد دعوت شما: <code>{referral_code}</code>\n"
                f"با دعوت دوستان، امتیاز بگیرید و گیگ رایگان ببرید!\n\n"
                f"📞 برای راهنمایی از دکمه‌های زیر استفاده کنید."
            )
        else:
            welcome_text = (
                f"سلام مجدد {user.full_name}! 👋\n"
                f"به ربات فروش فیلترشکن خوش برگشتی!\n\n"
                f"💰 موجودی کیف پول: {db_user.wallet_balance:,.0f} تومان\n"
                f"⭐ امتیاز: {db_user.referral_points}"
            )
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=main_keyboard(),
            parse_mode='HTML'
        )
        
    except Exception as e:
        logger.error(f"Error in start: {e}")
        await update.message.reply_text(
            "❌ خطایی رخ داد! لطفاً دوباره تلاش کنید.",
            reply_markup=main_keyboard()
        )
    finally:
        session.close()

# ==================== ADMIN COMMANDS ====================
async def elias_core(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Special admin command /Elias.core"""
    user_id = update.effective_user.id
    
    if user_id == ADMIN_USER_ID:
        await update.message.reply_text(
            "👑 به پنل مدیریت خوش آمدید!\n"
            "از منوی زیر برای مدیریت ربات استفاده کنید:",
            reply_markup=admin_panel_inline()
        )
    else:
        await update.message.reply_text("⛔ شما دسترسی ادمین ندارید!")

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command handler"""
    await elias_core(update, context)

# ==================== MESSAGE HANDLER ====================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all text messages"""
    text = update.message.text
    user_id = update.effective_user.id
    
    try:
        if text == '🛍 خرید محصولات':
            await show_products(update, context)
        
        elif text == '📦 محصولات':
            await show_products_list(update, context)
        
        elif text == '💰 کیف پول':
            await show_wallet(update, context)
        
        elif text == '🎲 تست شانس':
            await play_dice(update, context)
        
        elif text == '🎁 کد تخفیف':
            await apply_discount(update, context)
        
        elif text == '👥 دعوت دوستان':
            await show_referral(update, context)
        
        elif text == '📞 پشتیبانی':
            await show_support(update, context)
        
        elif text == '💳 شماره کارت':
            await show_card_info(update, context)
        
        elif text == '👑 پنل ادمین' and is_admin(user_id):
            await update.message.reply_text(
                "👑 پنل مدیریت:",
                reply_markup=admin_panel_inline()
            )
        
        elif text == '🏠 منوی اصلی':
            await update.message.reply_text(
                "🏠 منوی اصلی:",
                reply_markup=main_keyboard()
            )
        
        elif text == '📊 آمار' and is_admin(user_id):
            await show_stats(update, context)
        
        elif text == '📨 پیام همگانی' and is_admin(user_id):
            context.user_data['admin_state'] = 'awaiting_broadcast'
            await update.message.reply_text(
                "📨 پیام خود را برای ارسال به همه کاربران بنویسید:\n"
                "برای لغو، /cancel را بفرستید."
            )
        
        elif text == '👤 پیام به کاربر' and is_admin(user_id):
            context.user_data['admin_state'] = 'awaiting_user_message'
            await update.message.reply_text(
                "👤 برای ارسال پیام به یک کاربر خاص:\n"
                "فرمت: user_id|message\n"
                "مثال: 123456789|سلام کاربر عزیز"
            )
        
        else:
            # Check if admin is in a state
            if is_admin(user_id) and context.user_data.get('admin_state'):
                await handle_admin_states(update, context)
            # Check if user is entering discount code
            elif context.user_data.get('awaiting_discount'):
                await validate_discount_code(update, context)
            else:
                await update.message.reply_text(
                    "❓ متوجه نشدم! لطفاً از دکمه‌های منو استفاده کنید.",
                    reply_markup=main_keyboard()
                )
    
    except Exception as e:
        logger.error(f"Error in handle_message: {e}")
        await update.message.reply_text(
            "❌ خطایی رخ داد! لطفاً دوباره تلاش کنید.",
            reply_markup=main_keyboard()
        )

# ==================== ADMIN STATES ====================
async def handle_admin_states(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin states"""
    state = context.user_data.get('admin_state')
    text = update.message.text
    
    if state == 'awaiting_broadcast':
        # Send broadcast message
        session = get_session()
        try:
            users = session.query(User).all()
            success = 0
            fail = 0
            
            for user in users:
                try:
                    await context.bot.send_message(
                        chat_id=user.user_id,
                        text=f"📢 پیام از طرف مدیریت:\n\n{text}",
                        parse_mode='HTML'
                    )
                    success += 1
                except Exception as e:
                    logger.error(f"Failed to send to {user.user_id}: {e}")
                    fail += 1
            
            await update.message.reply_text(
                f"✅ پیام همگانی ارسال شد!\n\n"
                f"📊 آمار ارسال:\n"
                f"✅ موفق: {success}\n"
                f"❌ ناموفق: {fail}"
            )
        except Exception as e:
            logger.error(f"Error in broadcast: {e}")
            await update.message.reply_text("❌ خطا در ارسال پیام همگانی!")
        finally:
            session.close()
            context.user_data['admin_state'] = None
    
    elif state == 'awaiting_user_message':
        try:
            parts = text.split('|', 1)
            if len(parts) == 2:
                target_user_id = int(parts[0].strip())
                message = parts[1].strip()
                
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=f"📨 پیام از طرف مدیریت:\n\n{message}",
                    parse_mode='HTML'
                )
                
                await update.message.reply_text(f"✅ پیام به کاربر {target_user_id} ارسال شد!")
            else:
                await update.message.reply_text("❌ فرمت اشتباه! مثال: 123456789|سلام")
        except Exception as e:
            logger.error(f"Error sending user message: {e}")
            await update.message.reply_text("❌ خطا در ارسال پیام! ممکن است کاربر ربات را بلاک کرده باشد.")
        finally:
            context.user_data['admin_state'] = None
    
    elif state == 'awaiting_balance_change':
        try:
            parts = text.split()
            if len(parts) == 2:
                user_id = int(parts[0])
                amount = float(parts[1])
                
                session = get_session()
                user = session.query(User).filter_by(user_id=user_id).first()
                
                if user:
                    user.wallet_balance += amount
                    session.commit()
                    
                    await update.message.reply_text(
                        f"✅ موجودی کاربر {user_id} تغییر کرد!\n"
                        f"💰 موجودی فعلی: {user.wallet_balance:,.0f} تومان\n"
                        f"📊 تغییر: {amount:+,.0f} تومان"
                    )
                    
                    # Notify user
                    try:
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=f"💰 ادمین موجودی شما را تغییر داد!\n"
                                 f"📊 تغییر: {amount:+,.0f} تومان\n"
                                 f"💵 موجودی فعلی: {user.wallet_balance:,.0f} تومان"
                        )
                    except:
                        pass
                else:
                    await update.message.reply_text("❌ کاربر یافت نشد!")
                
                session.close()
            else:
                await update.message.reply_text("❌ فرمت اشتباه! مثال: 123456789 50000")
        except ValueError:
            await update.message.reply_text("❌ لطفاً اعداد معتبر وارد کنید!")
        finally:
            context.user_data['admin_state'] = None
    
    elif state == 'awaiting_points_change':
        try:
            parts = text.split()
            if len(parts) == 2:
                user_id = int(parts[0])
                points = int(parts[1])
                
                session = get_session()
                user = session.query(User).filter_by(user_id=user_id).first()
                
                if user:
                    user.referral_points += points
                    session.commit()
                    
                    await update.message.reply_text(
                        f"✅ امتیاز کاربر {user_id} تغییر کرد!\n"
                        f"⭐ امتیاز فعلی: {user.referral_points}\n"
                        f"📊 تغییر: {points:+}"
                    )
                else:
                    await update.message.reply_text("❌ کاربر یافت نشد!")
                
                session.close()
            else:
                await update.message.reply_text("❌ فرمت اشتباه! مثال: 123456789 5")
        except ValueError:
            await update.message.reply_text("❌ لطفاً اعداد معتبر وارد کنید!")
        finally:
            context.user_data['admin_state'] = None

# ==================== SHOW FUNCTIONS ====================
async def show_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show products for purchase"""
    session = get_session()
    try:
        products = session.query(Product).filter_by(is_active=True).all()
        
        if products:
            text = "🛍 <b>محصولات موجود:</b>\n\n"
            keyboard = []
            
            for product in products:
                text += f"🔹 <b>{product.name}</b>\n"
                text += f"💰 قیمت: {product.price:,.0f} تومان\n"
                text += f"📝 {product.description}\n\n"
                
                keyboard.append([
                    InlineKeyboardButton(
                        f"🛒 خرید {product.name} - {product.price:,.0f} تومان",
                        callback_data=f'buy_{product.id}'
                    )
                ])
            
            keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='back_main')])
            
            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(
                "❌ متاسفانه در حال حاضر محصولی موجود نیست!\n"
                "لطفاً بعداً مراجعه کنید."
            )
    except Exception as e:
        logger.error(f"Error showing products: {e}")
        await update.message.reply_text("❌ خطا در نمایش محصولات!")
    finally:
        session.close()

async def show_products_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show products list"""
    session = get_session()
    try:
        products = session.query(Product).filter_by(is_active=True).all()
        
        if products:
            text = "📦 <b>لیست محصولات:</b>\n\n"
            
            for product in products:
                text += f"🔹 <b>{product.name}</b>\n"
                text += f"💰 قیمت: {product.price:,.0f} تومان\n"
                text += f"📝 توضیحات: {product.description}\n"
                text += "➖➖➖➖➖➖➖➖➖➖\n"
            
            await update.message.reply_text(
                text,
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🛍 رفتن به خرید", callback_data='show_buy')]
                ])
            )
        else:
            await update.message.reply_text("❌ محصولی موجود نیست!")
    except Exception as e:
        logger.error(f"Error showing products list: {e}")
        await update.message.reply_text("❌ خطا در نمایش لیست محصولات!")
    finally:
        session.close()

async def show_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user wallet"""
    user_id = update.effective_user.id
    session = get_session()
    
    try:
        user = session.query(User).filter_by(user_id=user_id).first()
        
        if user:
            text = (
                f"💰 <b>کیف پول شما:</b>\n\n"
                f"💵 موجودی: {user.wallet_balance:,.0f} تومان\n"
                f"⭐ امتیاز: {user.referral_points}\n"
                f"🎁 کد دعوت: <code>{user.referral_code}</code>\n"
                f"🛍 تعداد خرید: {session.query(Purchase).filter_by(user_id=user_id).count()}"
            )
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 افزایش موجودی", callback_data='add_balance')],
                [InlineKeyboardButton("📊 تاریخچه خرید", callback_data='purchase_history')],
                [InlineKeyboardButton("🔙 بازگشت", callback_data='back_main')]
            ])
            
            await update.message.reply_text(text, reply_markup=keyboard, parse_mode='HTML')
        else:
            await update.message.reply_text("❌ کاربر یافت نشد!")
    
    except Exception as e:
        logger.error(f"Error showing wallet: {e}")
        await update.message.reply_text("❌ خطا در نمایش کیف پول!")
    finally:
        session.close()

async def show_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show referral information"""
    user_id = update.effective_user.id
    session = get_session()
    
    try:
        user = session.query(User).filter_by(user_id=user_id).first()
        
        if user:
            bot_username = (await context.bot.get_me()).username
            referral_link = f"https://t.me/{bot_username}?start={user.referral_code}"
            
            # Count referrals
            referrals_count = session.query(User).filter_by(referred_by=user_id).count()
            
            text = (
                f"👥 <b>سیستم دعوت دوستان:</b>\n\n"
                f"🎁 با دعوت هر دوست، <b>{REFERRAL_POINTS} امتیاز</b> بگیرید!\n"
                f"⭐ امتیاز شما: <b>{user.referral_points}</b>\n"
                f"👤 تعداد دعوت‌ها: <b>{referrals_count}</b>\n\n"
                f"🔗 لینک دعوت شما:\n"
                f"<code>{referral_link}</code>\n\n"
                f"🎲 با <b>{DICE_POINTS_COST} امتیاز</b> می‌تونید تاس بندازید و گیگ رایگان ببرید!\n"
                f"🎯 هر عدد تاس = همونقدر گیگ رایگان!"
            )
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📤 اشتراک‌گذاری لینک دعوت", switch_inline_query=f"Join me! {referral_link}")],
                [InlineKeyboardButton("🔙 بازگشت", callback_data='back_main')]
            ])
            
            await update.message.reply_text(text, reply_markup=keyboard, parse_mode='HTML')
    
    except Exception as e:
        logger.error(f"Error showing referral: {e}")
        await update.message.reply_text("❌ خطا در نمایش اطلاعات دعوت!")
    finally:
        session.close()

async def show_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show support information"""
    support_text = (
        "📞 <b>پشتیبانی:</b>\n\n"
        "🆔 آیدی پشتیبانی: @Support_Username\n"
        "📧 ایمیل: support@example.com\n"
        "⏰ ساعات پاسخگویی: ۹ صبح تا ۹ شب\n\n"
        "💡 <b>راهنمایی:</b>\n"
        "در صورت بروز هرگونه مشکل، لطفاً پیام دهید تا کارشناسان ما در اسرع وقت پاسخگو باشند."
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📞 تماس با پشتیبان", url="https://t.me/Support_Username")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data='back_main')]
    ])
    
    await update.message.reply_text(support_text, reply_markup=keyboard, parse_mode='HTML')

async def show_card_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show card information"""
    card_text = (
        "💳 <b>اطلاعات کارت بانکی:</b>\n\n"
        f"🏦 شماره کارت:\n"
        f"<code>{CARD_NUMBER}</code>\n\n"
        f"👤 به نام: {CARD_HOLDER}\n\n"
        "⚠️ <b>نکات مهم:</b>\n"
        "• لطفاً پس از واریز، رسید را به پشتیبانی ارسال کنید.\n"
        "• موجودی شما پس از تایید افزایش می‌یابد.\n"
        "• در صورت تاخیر با پشتیبانی تماس بگیرید."
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📞 ارسال رسید به پشتیبانی", url="https://t.me/Support_Username")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data='back_main')]
    ])
    
    await update.message.reply_text(card_text, reply_markup=keyboard, parse_mode='HTML')

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show statistics for admin"""
    if not is_admin(update.effective_user.id):
        return
    
    session = get_session()
    try:
        total_users = session.query(User).count()
        total_purchases = session.query(Purchase).count()
        total_revenue = session.query(Purchase).with_entities(
            func.sum(Purchase.amount)
        ).scalar() or 0
        active_discounts = session.query(DiscountCode).filter_by(is_active=True).count()
        
        stats_text = (
            "📊 <b>آمار ربات:</b>\n\n"
            f"👥 کل کاربران: {total_users}\n"
            f"🛍 کل خریدها: {total_purchases}\n"
            f"💰 مجموع درآمد: {total_revenue:,.0f} تومان\n"
            f"🎁 کدهای تخفیف فعال: {active_discounts}\n"
            f"⏰ تاریخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        
        await update.message.reply_text(stats_text, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Error showing stats: {e}")
        await update.message.reply_text("❌ خطا در نمایش آمار!")
    finally:
        session.close()

async def show_purchase_history(query, user_id):
    """Show purchase history"""
    session = get_session()
    try:
        purchases = session.query(Purchase).filter_by(user_id=user_id).order_by(
            Purchase.created_at.desc()
        ).limit(10).all()
        
        if purchases:
            text = "📊 <b>تاریخچه خرید:</b>\n\n"
            
            for purchase in purchases:
                product = session.query(Product).filter_by(id=purchase.product_id).first()
                product_name = product.name if product else "محصول حذف شده"
                
                text += f"🛍 {product_name}\n"
                text += f"💰 {purchase.amount:,.0f} تومان\n"
                text += f"📅 {purchase.created_at.strftime('%Y-%m-%d %H:%M')}\n"
                text += f"🔐 کانفیگ: <code>{purchase.config}</code>\n"
                text += "➖➖➖➖➖➖➖➖➖➖\n"
            
            await query.message.reply_text(text, parse_mode='HTML')
        else:
            await query.message.reply_text("📊 شما هنوز خریدی انجام نداده‌اید!")
    
    except Exception as e:
        logger.error(f"Error showing purchase history: {e}")
        await query.message.reply_text("❌ خطا در نمایش تاریخچه!")
    finally:
        session.close()

# ==================== PURCHASE FUNCTIONS ====================
async def buy_product(query, user_id, product_id):
    """Process product purchase"""
    session = get_session()
    
    try:
        product = session.query(Product).filter_by(id=product_id, is_active=True).first()
        user = session.query(User).filter_by(user_id=user_id).first()
        
        if not product:
            await query.message.reply_text("❌ محصول ناموجود است!")
            return
        
        if not user:
            await query.message.reply_text("❌ کاربر یافت نشد! /start را بزنید.")
            return
        
        # Calculate final price with discount
        final_price = product.price
        discount_percentage = 0
        
        # Check if user has active discount in context
        if hasattr(query, 'message') and hasattr(query.message, 'chat'):
            # Check context for discount
            discount_info = context_user_data.get(f'discount_{user_id}')
            if discount_info:
                discount_percentage = discount_info.get('percentage', 0)
                final_price = product.price * (1 - discount_percentage / 100)
        
        # Check wallet balance
        if user.wallet_balance < final_price:
            await query.message.reply_text(
                f"❌ موجودی کافی نیست!\n\n"
                f"💰 قیمت محصول: {final_price:,.0f} تومان\n"
                f"💵 موجودی شما: {user.wallet_balance:,.0f} تومان\n"
                f"📊 کسری: {(final_price - user.wallet_balance):,.0f} تومان\n\n"
                f"💡 لطفاً کیف پول خود را شارژ کنید.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💳 افزایش موجودی", callback_data='add_balance')]
                ])
            )
            return
        
        # Process purchase
        user.wallet_balance -= final_price
        
        # Generate config
        config = f"VPN_CONFIG_{user_id}_{product_id}_{int(datetime.now().timestamp())}"
        
        # If product has config template, use it
        if product.config_template:
            config = product.config_template.replace('{user_id}', str(user_id))
        
        # Create purchase record
        purchase = Purchase(
            user_id=user_id,
            product_id=product_id,
            config=config,
            amount=final_price,
            status='completed'
        )
        
        session.add(purchase)
        session.commit()
        
        # Send config to user
        success_text = (
            f"✅ <b>خرید موفق!</b>\n\n"
            f"📦 محصول: <b>{product.name}</b>\n"
            f"💰 مبلغ: {final_price:,.0f} تومان\n"
            f"💵 موجودی باقی‌مانده: {user.wallet_balance:,.0f} تومان\n\n"
            f"🔐 <b>کانفیگ شما:</b>\n"
            f"<code>{config}</code>\n\n"
            f"⚠️ لطفاً کانفیگ را ذخیره کنید!\n"
            f"📞 در صورت مشکل با پشتیبانی تماس بگیرید."
        )
        
        await query.message.reply_text(success_text, parse_mode='HTML')
        
        # Record discount usage
        if discount_percentage > 0:
            discount_code = context_user_data.get(f'discount_{user_id}', {}).get('code')
            if discount_code:
                discount = session.query(DiscountCode).filter_by(code=discount_code).first()
                if discount:
                    discount.used_count += 1
                    
                    usage = DiscountUsage(
                        user_id=user_id,
                        code_id=discount.id
                    )
                    session.add(usage)
                    session.commit()
                    
                    # Clear discount from context
                    context_user_data.pop(f'discount_{user_id}', None)
        
        # Notify admin
        try:
            admin_msg = (
                f"🔔 <b>فروش جدید!</b>\n\n"
                f"👤 کاربر: {user.full_name}\n"
                f"🆔 آیدی: <code>{user_id}</code>\n"
                f"📦 محصول: {product.name}\n"
                f"💰 مبلغ: {final_price:,.0f} تومان\n"
                f"🎁 تخفیف: {discount_percentage}%\n"
                f"⏰ زمان: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            await query.bot.send_message(
                chat_id=ADMIN_USER_ID,
                text=admin_msg,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Could not notify admin: {e}")
    
    except Exception as e:
        logger.error(f"Error in purchase: {e}")
        await query.message.reply_text("❌ خطا در پردازش خرید! لطفاً دوباره تلاش کنید.")
    finally:
        session.close()

# ==================== DICE GAME ====================
async def play_dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Play dice game"""
    user_id = update.effective_user.id
    session = get_session()
    
    try:
        user = session.query(User).filter_by(user_id=user_id).first()
        
        if not user:
            await update.message.reply_text("❌ کاربر یافت نشد!")
            return
        
        if user.referral_points < DICE_POINTS_COST:
            await update.message.reply_text(
                f"❌ امتیاز کافی ندارید!\n\n"
                f"🎲 هزینه هر بار تاس: <b>{DICE_POINTS_COST} امتیاز</b>\n"
                f"⭐ امتیاز شما: <b>{user.referral_points}</b>\n"
                f"📊 کسری: <b>{DICE_POINTS_COST - user.referral_points} امتیاز</b>\n\n"
                f"💡 با دعوت دوستان امتیاز جمع کنید!",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("👥 دعوت دوستان", callback_data='show_referral')]
                ])
            )
            return
        
        # Deduct points
        user.referral_points -= DICE_POINTS_COST
        session.commit()
        
        # Send dice
        await update.message.reply_text(
            f"🎲 در حال پرتاب تاس...\n"
            f"⭐ {DICE_POINTS_COST} امتیاز کسر شد\n"
            f"⭐ امتیاز باقی‌مانده: {user.referral_points}"
        )
        
        dice_message = await update.message.reply_dice(emoji='🎲')
        dice_value = dice_message.dice.value
        
        # Award GB (1-6 GB based on dice)
        gb_amount = dice_value
        
        # Add to wallet or give bonus
        user.wallet_balance += gb_amount * 10000  # Each GB = 10000 toman
        
        # Add points for winning
        if dice_value >= 5:
            bonus_points = 1
            user.referral_points += bonus_points
        else:
            bonus_points = 0
        
        session.commit()
        
        # Result message
        result_text = (
            f"🎲 <b>نتیجه تاس:</b> {dice_value}\n\n"
            f"🎉 <b>مبارکه! {gb_amount} گیگ برنده شدی!</b>\n"
            f"💰 معادل {gb_amount * 10000:,} تومان به کیف پولت اضافه شد!\n"
            f"💵 موجودی کیف پول: {user.wallet_balance:,.0f} تومان\n"
        )
        
        if bonus_points > 0:
            result_text += f"🎁 امتیاز جایزه: +{bonus_points}\n"
        
        result_text += f"⭐ امتیاز باقی‌مانده: {user.referral_points}"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎲 تاس دوباره", callback_data='play_dice_again')],
            [InlineKeyboardButton("🔙 بازگشت", callback_data='back_main')]
        ])
        
        await update.message.reply_text(result_text, reply_markup=keyboard, parse_mode='HTML')
    
    except Exception as e:
        logger.error(f"Error in dice game: {e}")
        await update.message.reply_text("❌ خطا در بازی تاس! لطفاً دوباره تلاش کنید.")
    finally:
        session.close()

# ==================== DISCOUNT FUNCTIONS ====================
async def apply_discount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Apply discount code"""
    context.user_data['awaiting_discount'] = True
    
    await update.message.reply_text(
        "🎁 لطفاً کد تخفیف خود را وارد کنید:\n\n"
        "برای انصراف، روی دکمه زیر کلیک کنید.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 انصراف", callback_data='cancel_discount')]
        ])
    )

async def validate_discount_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Validate and apply discount code"""
    code = update.message.text.strip().upper()
    user_id = update.effective_user.id
    session = get_session()
    
    try:
        discount = session.query(DiscountCode).filter_by(
            code=code,
            is_active=True
        ).first()
        
        if not discount:
            await update.message.reply_text(
                "❌ کد تخفیف نامعتبر است!\n"
                "لطفاً کد صحیح را وارد کنید یا از منو خارج شوید.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 انصراف", callback_data='cancel_discount')]
                ])
            )
            return
        
        # Check expiration
        if discount.created_at:
            expiry_date = discount.created_at + timedelta(days=discount.days_valid)
            if datetime.utcnow() > expiry_date:
                await update.message.reply_text("❌ این کد تخفیف منقضی شده است!")
                return
        
        # Check usage count
        if discount.used_count >= discount.max_usage:
            await update.message.reply_text("❌ این کد تخفیف به حداکثر استفاده رسیده است!")
            return
        
        # Check if user already used this code
        usage = session.query(DiscountUsage).filter_by(
            user_id=user_id,
            code_id=discount.id
        ).first()
        
        if usage:
            await update.message.reply_text("❌ شما قبلاً از این کد استفاده کرده‌اید!")
            return
        
        # Apply discount
        context.user_data['active_discount'] = {
            'code': discount.code,
            'percentage': discount.percentage,
            'code_id': discount.id
        }
        
        context.user_data['awaiting_discount'] = False
        
        await update.message.reply_text(
            f"✅ <b>کد تخفیف اعمال شد!</b>\n\n"
            f"🎁 کد: <code>{discount.code}</code>\n"
            f"📊 درصد تخفیف: <b>{discount.percentage}%</b>\n"
            f"⏰ اعتبار: <b>{discount.days_valid} روز</b>\n\n"
            f"💡 حالا می‌تونید با تخفیف خرید کنید!\n"
            f"🛍 برای خرید به بخش محصولات بروید.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛍 رفتن به محصولات", callback_data='show_buy')],
                [InlineKeyboardButton("🔙 بازگشت", callback_data='back_main')]
            ])
        )
    
    except Exception as e:
        logger.error(f"Error validating discount: {e}")
        await update.message.reply_text("❌ خطا در اعمال کد تخفیف!")
    finally:
        session.close()

# ==================== CALLBACK HANDLER ====================
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all callback queries"""
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    
    try:
        if data.startswith('buy_'):
            product_id = int(data.split('_')[1])
            await buy_product(query, user_id, product_id)
        
        elif data == 'add_balance':
            await query.message.reply_text(
                f"💳 <b>افزایش موجودی:</b>\n\n"
                f"🏦 شماره کارت:\n<code>{CARD_NUMBER}</code>\n"
                f"👤 به نام: {CARD_HOLDER}\n\n"
                f"⚠️ پس از واریز، رسید را به پشتیبانی ارسال کنید.\n"
                f"💰 موجودی شما پس از تایید افزایش می‌یابد.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📞 ارسال رسید", url="https://t.me/Support_Username")],
                    [InlineKeyboardButton("🔙 بازگشت", callback_data='back_main')]
                ])
            )
        
        elif data == 'purchase_history':
            await show_purchase_history(query, user_id)
        
        elif data == 'show_buy':
            await show_products_for_callback(query)
        
        elif data == 'show_referral':
            await show_referral_callback(query, user_id)
        
        elif data == 'play_dice_again':
            await play_dice_callback(query, user_id)
        
        elif data == 'back_main':
            await query.message.reply_text(
                "🏠 منوی اصلی:",
                reply_markup=main_keyboard()
            )
        
        elif data == 'cancel_discount':
            context.user_data['awaiting_discount'] = False
            context.user_data.pop('active_discount', None)
            await query.message.reply_text(
                "❌ عملیات لغو شد.",
                reply_markup=main_keyboard()
            )
        
        elif data.startswith('admin_'):
            if not is_admin(user_id):
                await query.message.reply_text("⛔ دسترسی غیرمجاز!")
                return
            await handle_admin_callback(query, context, data)
        
        elif data == 'back_admin':
            await query.message.reply_text(
                "👑 پنل مدیریت:",
                reply_markup=admin_panel_inline()
            )
    
    except Exception as e:
        logger.error(f"Error in callback: {e}")
        await query.message.reply_text("❌ خطایی رخ داد! لطفاً دوباره تلاش کنید.")

# ==================== ADMIN CALLBACKS ====================
async def handle_admin_callback(query, context, data):
    """Handle admin callback queries"""
    
    if data == 'admin_products':
        # Show product management
        session = get_session()
        products = session.query(Product).all()
        session.close()
        
        text = "📦 <b>مدیریت محصولات:</b>\n\n"
        if products:
            for p in products:
                status = "✅ فعال" if p.is_active else "❌ غیرفعال"
                text += f"🔹 {p.name} - {p.price:,.0f} تومان ({status})\n"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ افزودن محصول", callback_data='admin_add_product')],
            [InlineKeyboardButton("❌ حذف محصول", callback_data='admin_remove_product')],
            [InlineKeyboardButton("🔙 بازگشت", callback_data='back_admin')]
        ])
        
        await query.message.reply_text(text, reply_markup=keyboard, parse_mode='HTML')
    
    elif data == 'admin_change_balance':
        context.user_data['admin_state'] = 'awaiting_balance_change'
        await query.message.reply_text(
            "💰 <b>تغییر موجودی کاربر:</b>\n\n"
            "فرمت: <code>user_id amount</code>\n"
            "مثال: <code>123456789 50000</code>\n\n"
            "برای کسر موجودی از عدد منفی استفاده کنید.\n"
            "برای لغو، /cancel را بفرستید.",
            parse_mode='HTML'
        )
    
    elif data == 'admin_discount':
        await query.message.reply_text(
            "🎁 <b>مدیریت کد تخفیف:</b>",
            reply_markup=discount_management_keyboard(),
            parse_mode='HTML'
        )
    
    elif data == 'add_discount':
        context.user_data['admin_state'] = 'add_discount_days'
        await query.message.reply_text(
            "🎁 <b>افزودن کد تخفیف جدید:</b>\n\n"
            "مرحله 1: چند روز اعتبار داشته باشد؟\n"
            "لطفاً عدد وارد کنید:",
            parse_mode='HTML'
        )
    
    elif data == 'remove_discount':
        session = get_session()
        discounts = session.query(DiscountCode).filter_by(is_active=True).all()
        session.close()
        
        if discounts:
            keyboard = []
            for d in discounts:
                keyboard.append([
                    InlineKeyboardButton(
                        f"❌ {d.code} - {d.percentage}%",
                        callback_data=f'delete_discount_{d.id}'
                    )
                ])
            keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='admin_discount')])
            
            await query.message.reply_text(
                "🎁 کد تخفیف مورد نظر برای حذف را انتخاب کنید:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await query.message.reply_text("❌ کد تخفیف فعالی وجود ندارد!")
    
    elif data == 'list_discounts':
        session = get_session()
        discounts = session.query(DiscountCode).all()
        session.close()
        
        if discounts:
            text = "📋 <b>لیست کدهای تخفیف:</b>\n\n"
            for d in discounts:
                status = "✅ فعال" if d.is_active else "❌ غیرفعال"
                text += f"🎫 <code>{d.code}</code>\n"
                text += f"📊 {d.percentage}% | ⏰ {d.days_valid} روز\n"
                text += f"👥 {d.used_count}/{d.max_usage} استفاده\n"
                text += f"📌 وضعیت: {status}\n"
                text += "➖➖➖➖➖➖➖➖➖➖\n"
            
            await query.message.reply_text(text, parse_mode='HTML')
        else:
            await query.message.reply_text("❌ کد تخفیفی وجود ندارد!")
    
    elif data.startswith('delete_discount_'):
        discount_id = int(data.split('_')[2])
        session = get_session()
        discount = session.query(DiscountCode).filter_by(id=discount_id).first()
        
        if discount:
            discount.is_active = False
            session.commit()
            await query.message.reply_text(f"✅ کد تخفیف {discount.code} غیرفعال شد!")
        else:
            await query.message.reply_text("❌ کد تخفیف یافت نشد!")
        
        session.close()
    
    elif data == 'admin_config':
        await query.message.reply_text(
            "⚙️ <b>تغییر کانفیگ:</b>\n\n"
            "این بخش برای تغییر تنظیمات کانفیگ است.\n"
            "برای تغییر، به دیتابیس مراجعه کنید.",
            parse_mode='HTML'
        )
    
    elif data == 'admin_menu':
        await query.message.reply_text(
            "📝 <b>تغییر منو:</b>\n\n"
            "برای تغییر منو، کد را ویرایش کنید.\n"
            "در نسخه‌های بعدی این قابلیت اضافه می‌شود.",
            parse_mode='HTML'
        )
    
    elif data == 'admin_button':
        await query.message.reply_text(
            "🔘 <b>تغییر دکمه:</b>\n\n"
            "برای تغییر دکمه‌ها، کد را ویرایش کنید.\n"
            "در نسخه‌های بعدی این قابلیت اضافه می‌شود.",
            parse_mode='HTML'
        )
    
    elif data == 'admin_points':
        context.user_data['admin_state'] = 'awaiting_points_change'
        await query.message.reply_text(
            "⭐ <b>تغییر امتیاز کاربر:</b>\n\n"
            "فرمت: <code>user_id points</code>\n"
            "مثال: <code>123456789 10</code>\n\n"
            "برای کسر امتیاز از عدد منفی استفاده کنید.",
            parse_mode='HTML'
        )
    
    elif data == 'admin_referral_stats':
        session = get_session()
        # Top referrers
        top_referrers = session.query(
            User,
            func.count(User.user_id).label('count')
        ).join(
            User, User.user_id == User.referred_by
        ).group_by(User.user_id).order_by(
            func.count(User.user_id).desc()
        ).limit(10).all()
        
        session.close()
        
        if top_referrers:
            text = "👥 <b>برترین دعوت‌کنندگان:</b>\n\n"
            for i, (user, count) in enumerate(top_referrers, 1):
                text += f"{i}. {user.full_name} - {count} دعوت\n"
            
            await query.message.reply_text(text, parse_mode='HTML')
        else:
            await query.message.reply_text("❌ آمار دعوت موجود نیست!")

# ==================== ADMIN MESSAGE HANDLERS ====================
async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin text messages for states"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        return
    
    text = update.message.text
    state = context.user_data.get('admin_state')
    
    if state == 'add_discount_days':
        try:
            days = int(text)
            if days > 0:
                context.user_data['discount_days'] = days
                context.user_data['admin_state'] = 'add_discount_percentage'
                await update.message.reply_text(
                    "🎁 مرحله 2: چند درصد تخفیف؟\n"
                    "لطفاً عدد بین 1 تا 100 وارد کنید:"
                )
            else:
                await update.message.reply_text("❌ لطفاً عدد مثبت وارد کنید!")
        except ValueError:
            await update.message.reply_text("❌ لطفاً عدد معتبر وارد کنید!")
    
    elif state == 'add_discount_percentage':
        try:
            percentage = int(text)
            if 1 <= percentage <= 100:
                context.user_data['discount_percentage'] = percentage
                context.user_data['admin_state'] = 'add_discount_usage'
                await update.message.reply_text(
                    "🎁 مرحله 3: چند بار قابل استفاده باشد؟\n"
                    "لطفاً عدد وارد کنید:"
                )
            else:
                await update.message.reply_text("❌ لطفاً عدد بین 1 تا 100 وارد کنید!")
        except ValueError:
            await update.message.reply_text("❌ لطفاً عدد معتبر وارد کنید!")
    
    elif state == 'add_discount_usage':
        try:
            max_usage = int(text)
            if max_usage > 0:
                days = context.user_data.get('discount_days')
                percentage = context.user_data.get('discount_percentage')
                
                # Generate discount code
                code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
                
                session = get_session()
                
                # Ensure unique code
                while session.query(DiscountCode).filter_by(code=code).first():
                    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
                
                discount = DiscountCode(
                    code=code,
                    percentage=percentage,
                    max_usage=max_usage,
                    days_valid=days,
                    is_active=True
                )
                
                session.add(discount)
                session.commit()
                session.close()
                
                await update.message.reply_text(
                    f"✅ <b>کد تخفیف ساخته شد!</b>\n\n"
                    f"🎫 کد: <code>{code}</code>\n"
                    f"📊 درصد: {percentage}%\n"
                    f"⏰ اعتبار: {days} روز\n"
                    f"👥 تعداد استفاده: {max_usage} بار\n\n"
                    f"💡 کد را برای کاربران ارسال کنید.",
                    parse_mode='HTML'
                )
                
                # Clear states
                context.user_data['admin_state'] = None
                context.user_data.pop('discount_days', None)
                context.user_data.pop('discount_percentage', None)
            else:
                await update.message.reply_text("❌ لطفاً عدد مثبت وارد کنید!")
        except ValueError:
            await update.message.reply_text("❌ لطفاً عدد معتبر وارد کنید!")

# ==================== CANCEL COMMAND ====================
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel current operation"""
    context.user_data.clear()
    await update.message.reply_text(
        "❌ عملیات لغو شد.",
        reply_markup=main_keyboard() if not is_admin(update.effective_user.id) else admin_panel_inline()
    )

# ==================== ERROR HANDLER ====================
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Update {update} caused error {context.error}")
    
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ خطایی رخ داد! لطفاً دوباره تلاش کنید.\n"
                "اگر مشکل ادامه داشت، با پشتیبانی تماس بگیرید."
            )
    except:
        pass

# ==================== MAIN ====================
def main():
    """Main function to run the bot"""
    try:
        # Create application
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Command handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("admin", admin_command))
        application.add_handler(CommandHandler("Elias.core", elias_core))
        application.add_handler(CommandHandler("cancel", cancel))
        
        # Message handlers
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        ))
        
        # Admin text handler (for states)
        application.add_handler(MessageHandler(
            filters.TEXT & filters.User(user_id=ADMIN_USER_ID),
            handle_admin_text
        ))
        
        # Callback query handler
        application.add_handler(CallbackQueryHandler(handle_callback))
        
        # Error handler
        application.add_error_handler(error_handler)
        
        # Start bot
        print("🤖 Bot is starting...")
        print(f"👑 Admin ID: {ADMIN_USER_ID}")
        print("✅ Bot is running!")
        
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    main()