import telebot
from telebot import types
from datetime import datetime, timedelta
import time

TOKEN = "7760443699:AAGEi7qztEljEku-q5a-0JiRD4LCivCz5sE"
bot = telebot.TeleBot(TOKEN)

users = {}

languages = {
    "ru": {
        "welcome": "Привет! Я ИИ-помощник для поиска мест отдыха. Выбери язык:",
        "ask_description": "Опиши, куда ты хочешь пойти (напр. бар с живой музыкой в Астане)",
        "trial_used": "Вы уже использовали пробный запрос. Оплатите 300₸ за 48 часов доступа.\nПришлите чек или скриншот Kaspi.",
        "checking_payment": "Проверяю чек... Пожалуйста, подождите 30 секунд ⏳",
        "access_granted": "Оплата подтверждена ✅. Вам открыт доступ на 48 часов!",
        "trial_reply": "Вот пример ответа от ИИ 🔍\n\n➡️ Заведение: RockBar\n➡️ Адрес: Астана, улица Весёлая 12\n➡️ Средний чек: 5000₸\n➡️ Атмосфера: Живая музыка, 25+ аудитория",
        "access_active": "У вас активен доступ. Отправьте запрос 👇",
        "invalid": "Пожалуйста, опишите, куда вы хотите пойти",
        "lang_selected": "Язык выбран: Русский 🇷🇺"
    },
    "kz": {
        "welcome": "Сәлем! Мен демалыс орындарын іздейтін AI көмекшімін. Тілді таңдаңыз:",
        "ask_description": "Қайда барғыңыз келетінін сипаттаңыз (мысалы: Астанада тірі музыкасы бар бар)",
        "trial_used": "Сіз сынақ сұрауын қолдандыңыз. 48 сағатқа кіру үшін 300₸ төлеңіз.\nKaspi түбіртегін жіберіңіз.",
        "checking_payment": "Түбіртекті тексеріп жатырмын... 30 секунд күтіңіз ⏳",
        "access_granted": "Төлем расталды ✅. Сізге 48 сағаттық қол жеткізу ашылды!",
        "trial_reply": "AI жауабының үлгісі 🔍\n\n➡️ Мекеме: RockBar\n➡️ Мекенжайы: Астана, Көңілді көшесі 12\n➡️ Орташа чек: 5000₸\n➡️ Атмосфера: Тірі музыка, 25+ аудитория",
        "access_active": "Сізде белсенді қол жеткізу бар. Сұранысыңызды жіберіңіз 👇",
        "invalid": "Қайда барғыңыз келетінін сипаттаңыз",
        "lang_selected": "Тіл таңдалды: Қазақша 🇰🇿"
    },
    "en": {
        "welcome": "Hello! I'm an AI assistant for finding places to relax. Choose your language:",
        "ask_description": "Describe where you'd like to go (e.g. a bar with live music in Astana)",
        "trial_used": "You already used your free trial. Pay 300₸ for 48 hours access.\nSend the Kaspi receipt or screenshot.",
        "checking_payment": "Checking receipt... Please wait 30 seconds ⏳",
        "access_granted": "Payment confirmed ✅. You now have access for 48 hours!",
        "trial_reply": "Example AI result 🔍\n\n➡️ Place: RockBar\n➡️ Address: Astana, Vesyolaya St. 12\n➡️ Avg. bill: 5000₸\n➡️ Vibe: Live music, 25+ audience",
        "access_active": "You already have access. Please send a request 👇",
        "invalid": "Please describe where you want to go",
        "lang_selected": "Language selected: English 🇬🇧"
    }
}


def get_lang(user_id):
    return users.get(user_id, {}).get("lang", "ru")


def has_access(user_id):
    user = users.get(user_id, {})
    return user.get("access_until", datetime.min) > datetime.now()


@bot.message_handler(commands=["start"])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Русский 🇷🇺", "Қазақша 🇰🇿", "English 🇬🇧")
    bot.send_message(message.chat.id, "🌐 Выберите язык / Тілді таңдаңыз / Choose language:", reply_markup=markup)


@bot.message_handler(func=lambda m: m.text in ["Русский 🇷🇺", "Қазақша 🇰🇿", "English 🇬🇧"])
def set_language(message):
    lang_code = "ru" if "Русский" in message.text else "kz" if "Қазақша" in message.text else "en"
    users[message.chat.id] = {"lang": lang_code, "used_trial": False}
    bot.send_message(message.chat.id, languages[lang_code]["lang_selected"], reply_markup=types.ReplyKeyboardRemove())
    bot.send_message(message.chat.id, languages[lang_code]["ask_description"])


@bot.message_handler(content_types=["text"])
def handle_text(message):
    user_id = message.chat.id
    text = message.text.strip()

    if not text or len(text) < 5:
        bot.send_message(user_id, languages[get_lang(user_id)]["invalid"])
        return

    user = users.get(user_id, {})
    lang = get_lang(user_id)

    if has_access(user_id):
        bot.send_message(user_id, languages[lang]["access_active"])
        bot.send_message(user_id, languages[lang]["trial_reply"])
    elif not user.get("used_trial", False):
        users[user_id]["used_trial"] = True
        bot.send_message(user_id, languages[lang]["trial_reply"])
    else:
        bot.send_message(user_id, languages[lang]["trial_used"])


@bot.message_handler(content_types=["photo", "document"])
def handle_payment_check(message):
    user_id = message.chat.id
    lang = get_lang(user_id)
    bot.send_message(user_id, languages[lang]["checking_payment"])
    time.sleep(30)
    users[user_id]["access_until"] = datetime.now() + timedelta(hours=48)
    bot.send_message(user_id, languages[lang]["access_granted"])


print("Бот запущен...")
bot.infinity_polling()
