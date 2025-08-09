# bot.py
import os
import re
import json
import time
import logging
import asyncio
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    CallbackQueryHandler,
    filters,
)

# try import g4f (free providers). If not installed, code will still work.
try:
    import g4f
    G4F_AVAILABLE = True
except Exception:
    G4F_AVAILABLE = False

from keep_alive import keep_alive

# ---------- Конфиг (ставь в env на Render) ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")  # обязательно
KASPI_LINK = os.getenv("KASPI_LINK", "https://pay.kaspi.kz/pay/sav8emzy")
PAYPAL_LINK = os.getenv("PAYPAL_LINK", "https://paypal.me/yourpaypal/1")
FREE_LIMIT = int(os.getenv("FREE_LIMIT", "1"))

USERS_FILE = "users.json"
CACHE_FILE = "cache.json"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

# ---------- Логирование ----------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- Хранилища ----------
def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except Exception:
        logger.exception("load_json")
        return default

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        logger.exception("save_json")

users = load_json(USERS_FILE, {})   # key = user_id str -> {lang, free_used:int, paid_until: iso str}
cache = load_json(CACHE_FILE, {})   # key = lang||normalized_query -> card dict

# ---------- Текстовые шаблоны (RU/KZ/EN) ----------
TEXT = {
    "choose_lang": {"ru": "Привет! Выберите язык:", "kz": "Сәлем! Тілді таңдаңыз:", "en": "Hi! Choose language:"},
    "ask_desc": {
        "ru": "Опишите место: город, тип (бар/ресторан/клуб), атмосфера, бюджет.",
        "kz": "Орынды сипаттаңыз: қала, тип (бар/ресторан/клуб), атмосфера, бюджет.",
        "en": "Describe the place: city, type (bar/restaurant/club), vibe, budget."
    },
    "free_used": {
        "ru": "У вас использован бесплатный запрос. Чтобы продолжить — оплатите и пришлите чек (скрин):",
        "kz": "Сіздің тегін сұрауыңыз пайдаланылды. Жалғастыру үшін төлеңіз және чектің скриншотын жіберіңіз:",
        "en": "You used your free request. To continue — pay and send the receipt (screenshot):"
    },
    "pay_options": {
        "ru": f"🇰🇿 Kaspi Pay — 300₸ / 48ч: {KASPI_LINK}\n🌍 PayPal — $1 / 48ч: {PAYPAL_LINK}",
        "kz": f"🇰🇿 Kaspi Pay — 300₸ / 48сағ: {KASPI_LINK}\n🌍 PayPal — $1 / 48сағ: {PAYPAL_LINK}",
        "en": f"🇰🇿 Kaspi Pay — 300₸ / 48h: {KASPI_LINK}\n🌍 PayPal — $1 / 48h: {PAYPAL_LINK}"
    },
    "send_receipt": {
        "ru": "После оплаты пришлите скрин чека (фото/документ). Я выполню имитацию проверки (≈30с).",
        "kz": "Төлемнен кейін чектің скриншотын жіберіңіз. Мен тексеруді эмуляциялаймын (≈30с).",
        "en": "After payment send receipt screenshot (photo/doc). I'll fake-check it (≈30s)."
    },
    "checking_receipt": {"ru": "Проверяю чек — подождите 30 секунд...", "kz": "Чекті тексеріп жатырмын — 30 секунд күтіңіз...", "en": "Checking receipt — please wait 30 seconds..."},
    "access_granted": {"ru": "✅ Оплата подтверждена (эмуляция). Доступ на 48 часов.", "kz": "✅ Төлем расталды (эмуляция). 48 сағатқа қол жетімді.", "en": "✅ Payment confirmed (fake). Access for 48 hours."},
    "error": {"ru": "Ошибка, попробуйте позже.", "kz": "Қате, кейінірек көріңіз.", "en": "Error, try later."},
}

# ---------- Вспомогательные функции ----------
def user_key(uid): return str(uid)
def get_lang(uid): return users.get(user_key(uid), {}).get("lang", "ru")

def has_paid(uid):
    u = users.get(user_key(uid))
    if not u: return False
    pu = u.get("paid_until")
    if not pu: return False
    try:
        return datetime.fromisoformat(pu) > datetime.utcnow()
    except Exception:
        return False

def set_paid_48h(uid):
    users.setdefault(user_key(uid), {})
    users[user_key(uid)]["paid_until"] = (datetime.utcnow() + timedelta(hours=48)).isoformat()
    save_json(USERS_FILE, users)

def inc_free_used(uid):
    users.setdefault(user_key(uid), {})
    users[user_key(uid)]["free_used"] = users[user_key(uid)].get("free_used", 0) + 1
    save_json(USERS_FILE, users)

# ---------- DuckDuckGo image (best-effort) ----------
def ddg_image_first(query):
    try:
        headers = {"User-Agent": USER_AGENT}
        r = requests.get("https://duckduckgo.com/", params={"q": query}, headers=headers, timeout=10)
        vqd = re.search(r"vqd='([^']+)'", r.text)
        vqd = vqd.group(1) if vqd else None
        params = {"q": query, "o": "json", "vqd": vqd}
        r2 = requests.get("https://duckduckgo.com/i.js", params=params, headers=headers, timeout=10)
        data = r2.json()
        res = data.get("results", [])
        if res:
            return res[0].get("image")
    except Exception:
        logger.exception("ddg_image_first")
    return None

# ---------- Geocode via OSM Nominatim ----------
def geocode_osm(query):
    try:
        r = requests.get("https://nominatim.openstreetmap.org/search", params={"q": query, "format": "json", "limit": 1}, headers={"User-Agent": USER_AGENT}, timeout=10)
        data = r.json()
        if data:
            return {"display_name": data[0].get("display_name"), "lat": float(data[0]["lat"]), "lon": float(data[0]["lon"])}
    except Exception:
        logger.exception("geocode_osm")
    return None

def osm_static_map_url(lat, lon, w=600, h=300, zoom=15):
    return f"https://staticmap.openstreetmap.de/staticmap.php?center={lat},{lon}&zoom={zoom}&size={w}x{h}&markers={lat},{lon},red-pushpin"

def osm_map_link(lat, lon): return f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=17/{lat}/{lon}"

# ---------- Best-effort отзывы: парсинг Google Search / TripAdvisor / Yelp ----------
def fetch_reviews_best_effort(name, city=None, max_reviews=3):
    headers = {"User-Agent": USER_AGENT}
    reviews = []
    query = f"{name} {city}" if city else name
    # 1) Google 'отзывы' выдача (snippet)
    try:
        r = requests.get("https://www.google.com/search", params={"q": f"{query} отзывы", "hl": "ru"}, headers=headers, timeout=8)
        soup = BeautifulSoup(r.text, "html.parser")
        # собрать короткие текстовые фрагменты
        for div in soup.select("div"):
            txt = div.get_text(separator=" ", strip=True)
            if txt and len(txt) > 40 and "отзыв" not in txt.lower():
                reviews.append(txt.strip())
            if len(reviews) >= max_reviews:
                return reviews[:max_reviews]
    except Exception:
        logger.exception("google search parse")

    # 2) TripAdvisor search page snippets
    try:
        r = requests.get("https://www.tripadvisor.com/Search", params={"q": query}, headers=headers, timeout=8)
        soup = BeautifulSoup(r.text, "html.parser")
        for p in soup.find_all("p"):
            txt = p.get_text(strip=True)
            if txt and len(txt) > 60:
                reviews.append(txt)
            if len(reviews) >= max_reviews:
                return reviews[:max_reviews]
    except Exception:
        logger.exception("tripadvisor parse")

    # 3) Yelp search page snippets (may be limited by region)
    try:
        r = requests.get("https://www.yelp.com/search", params={"find_desc": name, "find_loc": city or ""}, headers=headers, timeout=8)
        soup = BeautifulSoup(r.text, "html.parser")
        for p in soup.find_all("p"):
            txt = p.get_text(strip=True)
            if txt and len(txt) > 40:
                reviews.append(txt)
            if len(reviews) >= max_reviews:
                return reviews[:max_reviews]
    except Exception:
        logger.exception("yelp parse")

    return reviews[:max_reviews]

# ---------- g4f helpers: analyze reviews -> atmosphere/age/summary ----------
def g4f_analyze_text(reviews_text):
    if not G4F_AVAILABLE or not reviews_text:
        return None
    try:
        prompt = (
            f"На основе этих отзывов:\n{reviews_text}\n\n"
            "Сформулируй: 1) Атмосфера (коротко), 2) Средний возраст посетителей (примерно), 3) Одна-две строки summary."
            "Ответь в формате: ATMOSPHERE: ...; AGE: ...; SUMMARY: ..."
        )
        resp = None
        try:
            resp = g4f.ChatCompletion.create(model="gpt-4o-mini", messages=[{"role":"user","content":prompt}])
        except Exception:
            try:
                resp = g4f.chat_completion.create(model="gpt-4o-mini", messages=[{"role":"user","content":prompt}])
            except Exception:
                resp = None
        text = resp if isinstance(resp, str) else (str(resp) if resp else "")
        atm = re.search(r"ATMOSPHERE[:\-]\s*(.+)", text, re.I)
        age = re.search(r"AGE[:\-]\s*(.+)", text, re.I)
        summ = re.search(r"SUMMARY[:\-]\s*(.+)", text, re.I | re.S)
        return {
            "atmosphere": atm.group(1).strip() if atm else None,
            "age": age.group(1).strip() if age else None,
            "summary": summ.group(1).strip() if summ else text.strip()
        }
    except Exception:
        logger.exception("g4f_analyze_text")
        return None

# ---------- Эвристический анализ (если нет g4f) ----------
def heuristic_analysis(query):
    q
