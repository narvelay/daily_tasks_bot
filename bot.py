# bot.py
import asyncio
import logging
import requests
from datetime import datetime, timedelta

from telegram import (
    Update,
    KeyboardButton,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from database import init_db, get_session
from models import User, Invoice
from tasks import generate_daily_task

# ---------------------------
# НАСТРОЙКИ
# ---------------------------

ADMINS = [5238729809]  # ← Твой Telegram ID

PRICE_PACKS = {
    "pack1": {"name": "100 монет", "coins": 100, "ton": 0.05},
    "pack2": {"name": "300 монет", "coins": 300, "ton": 0.12},
    "pack3": {"name": "1000 монет", "coins": 1000, "ton": 0.35},
}

CRYPTO_API_URL = "https://pay.crypt.bot/api/"

# ---------------------------
# ЛОГИ
# ---------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------
# УТИЛИТЫ
# ---------------------------

def create_main_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📋 Мои задания"), KeyboardButton("💰 Баланс")],
            [KeyboardButton("💸 Купить монеты"), KeyboardButton("ℹ Помощь")],
        ],
        resize_keyboard=True
    )

# ---------------------------
# ПРОВЕРКА ИЛИ СОЗДАНИЕ ПОЛЬЗОВАТЕЛЯ
# ---------------------------

async def get_or_create_user(update: Update):
    session = get_session()
    user = session.query(User).filter_by(id=update.effective_user.id).first()
    if not user:
        user = User(
            id=update.effective_user.id,
            username=update.effective_user.username,
            fullname=update.effective_user.full_name,
            balance=0
        )
        session.add(user)
        session.commit()
    return user

# ---------------------------
# КОМАНДЫ
# ---------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await get_or_create_user(update)
    await update.message.reply_text(
        "Привет! Я — бот ежедневных заданий 💪\nВыбирай команду:",
        reply_markup=create_main_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📘 Команды:\n"
        "/start — начать\n"
        "/balance — баланс\n"
        "/shop — магазин монет\n"
        "/task — ежедневное задание\n"
        "/admin — меню администратора"
    )

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = get_session()
    user = session.query(User).filter_by(id=update.effective_user.id).first()
    await update.message.reply_text(f"💰 Баланс: {user.balance} монет")

async def task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = get_session()
    user = await get_or_create_user(update)
    task_text = generate_daily_task()
    await update.message.reply_text(f"📋 Твоё случайное задание:\n\n{task_text}")

# ---------------------------
# МАГАЗИН
# ---------------------------

async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [
        [InlineKeyboardButton(f"{data['name']} — {data['ton']} TON", callback_data=pack_id)]
        for pack_id, data in PRICE_PACKS.items()
    ]
    markup = InlineKeyboardMarkup(buttons)

    await update.message.reply_text("💸 Выбери пакет монет:", reply_markup=markup)

# ---------------------------
# СОЗДАНИЕ INVOICE
# ---------------------------

def create_invoice(amount_ton: float, payload: str, api_token: str):
    headers = {"Crypto-Pay-API-Token": api_token}
    data = {
        "asset": "TON",
        "amount": str(amount_ton),
        "payload": payload,
        "description": "Покупка монет в DailyTasksBot",
    }
    r = requests.post(CRYPTO_API_URL + "createInvoice", json=data, headers=headers).json()
    return r

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    pack_id = query.data
    pack = PRICE_PACKS[pack_id]

    session = get_session()
    user_id = query.from_user.id

    payload = f"buy_{user_id}_{pack_id}"
    invoice_data = create_invoice(pack["ton"], payload, context.bot_data["crypto_token"])

    if "result" not in invoice_data:
        await query.message.reply_text("Ошибка создания счёта.")
        return

    inv = invoice_data["result"]
    session.add(Invoice(
        invoice_id=inv["invoice_id"],
        user_id=user_id,
        pack_id=pack_id,
        status="pending"
    ))
    session.commit()

    await query.message.reply_text(
        f"💳 Ссылка на оплату:\n{inv['pay_url']}\n\n"
        f"После оплаты монеты начислятся автоматически."
    )

# ---------------------------
# ПРОВЕРКА СТАТУСА INVOICE
# ---------------------------

def check_invoice_status(invoice_id: int, api_token: str):
    headers = {"Crypto-Pay-API-Token": api_token}
    r = requests.get(CRYPTO_API_URL + f"getInvoices?invoice_ids={invoice_id}", headers=headers).json()
    return r

async def invoice_checker(app: Application):
    while True:
        session = get_session()
        pending = session.query(Invoice).filter_by(status="pending").all()

        for inv in pending:
            info = check_invoice_status(inv.invoice_id, app.bot_data["crypto_token"])

            if "result" in info and len(info["result"]) > 0:
                status = info["result"][0]["status"]

                if status == "paid":
                    pack = PRICE_PACKS[inv.pack_id]
                    user = session.query(User).filter_by(id=inv.user_id).first()
                    user.balance += pack["coins"]
                    inv.status = "paid"
                    session.commit()

                    try:
                        await app.bot.send_message(user.id, f"🎉 Платёж подтверждён! +{pack['coins']} монет!")
                    except:
                        pass

        await asyncio.sleep(30)

# ---------------------------
# ОСНОВНОЙ ЗАПУСК
# ---------------------------

async def main():
    init_db()

    from os import getenv
    TELEGRAM_TOKEN = getenv("TELEGRAM_TOKEN")
    CRYPTO_API_TOKEN = getenv("CRYPTO_API_TOKEN")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.bot_data["crypto_token"] = CRYPTO_API_TOKEN

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("shop", shop))
    app.add_handler(CommandHandler("task", task))
    app.add_handler(CallbackQueryHandler(button_handler))

    app.add_handler(MessageHandler(filters.Text("💰 Баланс"), balance))
    app.add_handler(MessageHandler(filters.Text("💸 Купить монеты"), shop))
    app.add_handler(MessageHandler(filters.Text("📋 Мои задания"), task))
    app.add_handler(MessageHandler(filters.Text("ℹ Помощь"), help_command))

    app.job_queue.run_once(lambda *_: asyncio.create_task(invoice_checker(app)), 1)

    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
