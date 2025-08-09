import os
import time
import json
import logging
import random
import requests
from io import BytesIO
from datetime import datetime, timedelta
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    ContextTypes, CallbackQueryHandler
)
from g4f.client import Client  # Бесплатный ИИ

# ----------------- ЛОГИ -----------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ----------------- НАСТРОЙКИ -----------------
TOKEN = os.getenv("TOKEN")  # Токен бота
OWNER_ID = os.getenv("OWNER_ID", "1282820065")  # Твой Telegram ID
KASPI_LINK = "https://pay.kaspi.kz/pay/sav8emzy"
PAYPAL_LINK = "https://www.paypal.com/paypalme/yourpaypal/1usd"

client = Client()
user_free_queries = {}
user_paid_until = {}
cached_results = {}

# ----------------- ВЫБОР ЯЗЫКА -----------------
LANGS = {
    "ru": "🇷🇺 Русский",
    "kk": "🇰🇿 Қазақша",
    "en": "🇬🇧 English"
}
user_lang = {}

MESSAGES = {
    "start": {
        "ru": "Выберите язык:",
        "kk": "Тілді таңдаңыз:",
        "en": "Choose a language:"
    },
    "ask_query": {
        "ru": "Опишите, какое место хотите найти (атмосфера, цены, музыка):",
        "kk": "Қандай орынды іздегіңіз келетінін сипаттаңыз:",
        "en": "Describe the place you want to find:"
    },
    "free_used": {
        "ru": f"Ваш бесплатный запрос использован. Оплатите, чтобы продолжить:\n🇰🇿 Kaspi: {KASPI_LINK} (300₸)\n🌍 PayPal: {PAYPAL_LINK} ($1)",
        "kk": f"Тегін сұранысыңыз пайдаланылды. Жалғастыру үшін төлеңіз:\n🇰🇿 Kaspi: {KASPI_LINK} (300₸)\n🌍 PayPal: {PAYPAL_LINK} ($1)",
        "en": f"Your free request is used. Please pay to continue:\n🇰🇿 Kaspi: {KASPI_LINK} (300₸)\n🌍 PayPal: {PAYPAL_LINK} ($1)"
    },
    "paid_success": {
        "ru": "✅ Оплата подтверждена! Доступ активирован на 48 часов.",
        "kk": "✅ Төлем расталды! 48 сағатқа қол жеткізу берілді.",
        "en": "✅ Payment confirmed! Access granted for 48 hours."
    }
}

# ----------------- СТАРТ -----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [
        [InlineKeyboardButton(name, callback_data=f"lang_{code}")]
        for code, name in LANGS.items()
    ]
    await update.message.reply_text(
        MESSAGES["start"]["ru"],
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ----------------- ВЫБОР ЯЗЫКА -----------------
async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang_code = query.data.split("_")[1]
    user_lang[query.from_user.id] = lang_code
    await query.message.reply_text(MESSAGES["ask_query"][lang_code])

# ----------------- ПОИСК ЗАВЕДЕНИЙ -----------------
async def search_places(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    lang = user_lang.get(user_id, "ru")

    # Проверка оплаты
    if user_id not in user_paid_until or user_paid_until[user_id] < datetime.now():
        if user_free_queries.get(user_id, 0) >= 1:
            await update.message.reply_text(MESSAGES["free_used"][lang])
            return
        else:
            user_free_queries[user_id] = user_free_queries.get(user_id, 0) + 1

    query_text = update.message.text

    # Кеш
    if query_text in cached_results:
        await update.message.reply_media_group(cached_results[query_text])
        return

    await update.message.reply_text("🔍 Ищу подходящие места...")

    # ИИ-подбор
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": f"Подбери 3 заведения: {query_text}, с адресом, атмосферой, средним возрастом, отзывами и ценой"}]
    )
    ai_text = response.choices[0].message.content

    # Генерация фейковых фото и карты (пример)
    photos = [
        InputMediaPhoto(media="https://source.unsplash.com/600x400/?bar"),
        InputMediaPhoto(media="https://source.unsplash.com/600x400/?restaurant")
    ]

    cached_results[query_text] = photos
    await update.message.reply_media_group(photos)
    await update.message.reply_text(ai_text)

# ----------------- ФЕЙКОВОЕ ПОДТВЕРЖДЕНИЕ -----------------
async def fake_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    lang = user_lang.get(user_id, "ru")
    await update.message.reply_text("⏳ Проверяю оплату...")
    time.sleep(30)
    user_paid_until[user_id] = datetime.now() + timedelta(hours=48)
    await update.message.reply_text(MESSAGES["paid_success"][lang])

# ----------------- MAIN -----------------
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(set_language, pattern="^lang_"))
    app.add_handler(CommandHandler("pay", fake_payment))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_places))

    app.run_polling()
