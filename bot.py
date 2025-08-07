import logging
import os
import requests
import re
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

load_dotenv()
TOKEN = os.getenv("TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "123456789"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! 👋 Я ИИ-помощник по заведениям. Просто напиши, куда хочешь сходить!")

def duckduckgo_search(query, max_results=3):
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    url = f"https://html.duckduckgo.com/html/?q={query}+site:2gis.kz"
    try:
        response = requests.get(url, headers=headers, timeout=10)
        matches = re.findall(r'<a rel="nofollow" class="result__a" href="(.*?)">(.*?)</a>', response.text)
        return matches[:max_results]
    except Exception as e:
        logger.error(f"Search error: {e}")
        return []

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.message.chat_id
    await update.message.reply_text(f"🔍 Ищу для тебя лучшие варианты по запросу: {text}...")

    results = duckduckgo_search(text)

    if not results:
        await update.message.reply_text("😔 Не удалось найти подходящие места. Попробуй переформулировать запрос.")
        return

    for url, title in results:
        await update.message.reply_text(f"🏙 {title}\n🔗 {url}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
