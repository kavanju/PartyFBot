# keep_alive.py
from flask import Flask
from threading import Thread
import os

app = Flask("keep_alive")

@app.route("/")
def home():
    return "Bot is running (keep_alive)."

def run():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = Thread(target=run, daemon=True)
    t.start()
