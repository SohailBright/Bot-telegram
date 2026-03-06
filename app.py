from flask import Flask
import threading
import os
import sys

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_bot():
    import subprocess
    subprocess.run([sys.executable, "bot.py"])

if __name__ == '__main__':
    # Start bot in background
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Start Flask server
    port = int(os.environ.get("PORT", 10000))
    print(f"Starting server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)