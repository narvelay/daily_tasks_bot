import asyncio
from os import getenv
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from database import get_session, init_db
from models import User
from tasks import get_random_task
import time
from datetime import datetime
import aiohttp

TELEGRAM_TOKEN = getenv("TELEGRAM_TOKEN")
CRYPTO_API_TOKEN = getenv("CRYPTO_API_TOKEN")
ADMINS = getenv("ADMINS", "").split(",")

# ---------- Database init ----------
init_db()


# ---------- Helpers ----------
def get_or_create_user(session, user_id, username, fullname):
    user = session.query(User).filter(User.id == user_id).first()
    if not user:
        user = User(
            id=user_id,
            username=username,
            fullname=fullname,
            balance=0,
            last_reward_time=0
        )
        session.add(user)
        session.commit()
    return user


# ---------- Commands ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = get_session()
    user = update.effective_user

    get_or_create_user(
        session,
        user.id,
        user.username,
        f"{user.first_name or ''} {user.last_name or ''}"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎯 Получить задание", callback_data="get_task")],
        [InlineKeyboardButton("🛒 Магазин", callback_data="shop")],
        [InlineKeyboardButton("💰 Баланс", callback_data="balance")],
    ])

    await update.message.reply_text(
        "Добро пожаловать! Выбирай действие:",
        reply_markup=keyboard
    )


async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = get_session()
    user_id = update.effective_user.id
    user = session.query(User).filter(User.id == user_id).first()
    await update.message.reply_text(f"Ваш баланс: {user.balance} монет")


# ------------- Задания ------------
async def send_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = get_session()
    user_id = update.effective_user.id
    task = get_random_task()

    await update.callback_query.answer()
    await update.callback_query.message.reply_text(f"🎯 Твоё задание:\n{task}")

    # Начисление монет раз в 12 часов
    user = session.query(User).filter(User.id == user_id).first()
    now = int(time.time())
    if now - user.last_reward_time >= 12 * 3600:
        user.balance += 5
        user.last_reward_time = now
        session.commit()
        await update.callback_query.message.reply_text("💰 +5 монет за выполнение!")


# -------- Магазин + покупка --------
async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("100 монет — 1 TON", callback_data="buy_100")],
        [InlineKeyboardButton("500 монет — 5 TON", callback_data="buy_500")],
        [InlineKeyboardButton("Назад", callback_data="menu")],
    ])

    await update.callback_query.message.edit_text(
        "🛒 Магазин монет:",
        reply_markup=keyboard
    )


async def create_invoice(ton_amount: float):
    url = "https://pay.crypt.bot/api/createInvoice"

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            json={"amount": ton_amount, "asset": "TON", "description": "Покупка монет", "hidden_message": "Спасибо!"},
            headers={"Crypto-Pay-API-Token": CRYPTO_API_TOKEN}
        ) as resp:
            return await resp.json()


async def shop_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "menu":
        await start(update, context)
        return

    if query.data == "buy_100":
        invoice = await create_invoice(1)
        await query.message.reply_text(f"Оплатить 1 TON:\n{invoice['result']['pay_url']}")

    if query.data == "buy_500":
        invoice = await create_invoice(5)
        await query.message.reply_text(f"Оплатить 5 TON:\n{invoice['result']['pay_url']}")


# --------- Обработчик кнопок ---------
async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data

    if data == "get_task":
        await send_task(update, context)
    elif data == "shop":
        await shop(update, context)
    elif data.startswith("buy"):
        await shop_handler(update, context)
    elif data == "balance":
        await balance(update, context)


# ---------- MAIN (исправленный) ----------
def main():
    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .concurrent_updates(True)
        .build()
    )

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CallbackQueryHandler(callback_router))

    # JobQueue активируется автоматически (теперь корректно)
    job_queue = app.job_queue

    # Пока можно оставить пустым — мы добавим проверки оплаты позже

    app.run_polling()


# ---------- Start ----------
if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback, sys
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        # Завершаем с кодом 1, чтобы Render увидел падение и логи
        sys.exit(1)


