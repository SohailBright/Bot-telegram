from flask import Flask
import subprocess
import os
import threading

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running! ✅"

def run_bot():
    """Bot ko background mein chalu karo"""
    subprocess.Popen(["python", "bot.py"])

if __name__ == '__main__':
    # Bot ko background mein chalu karo
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Flask server chalu karo
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)