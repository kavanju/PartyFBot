from keep_alive import keep_alive

keep_alive()  # Запускает Flask-сервер, чтобы Render не выключил приложение

from flask import Flask
import threading
import os

app = Flask('')

@app.route('/')
def home():
    return "Бот запущен и работает!"

def run():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = threading.Thread(target=run)
    t.start()
