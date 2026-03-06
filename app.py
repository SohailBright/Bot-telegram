from flask import Flask
import threading
import subprocess

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_bot():
    subprocess.Popen(["python", "bot.py"])

if __name__ == '__main__':
    run_bot()
    app.run(host='0.0.0.0', port=10000)