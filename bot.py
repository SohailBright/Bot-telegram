import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
import logging
from datetime import datetime, timedelta

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Data storage
users = {}  # user_id: {gender, preference, partner, state, skip_count, last_skip_time, ban_until, reports}
waiting_queue = {"male": [], "female": []}

# Bad words list
BAD_WORDS = ["sex", "nude", "porn", "xxx", "dick", "pussy", "chut", "lund", "rand"]

# States
STATE_IDLE = "idle"
STATE_GENDER_SELECT = "gender_select"
STATE_PREFERENCE_SELECT = "preference_select"
STATE_CHATTING = "chatting"
STATE_WAITING = "waiting"

### Helper Functions ###

def is_banned(user_id):
    """Check if user is banned"""
    if user_id in users and users[user_id].get('ban_until'):
        if datetime.now() < users[user_id]['ban_until']:
            return True
        else:
            users[user_id]['ban_until'] = None
    return False

def check_content(text):
    """Check for bad words or links"""
    text_lower = text.lower()
    
    # Check for links
    if 'http://' in text_lower or 'https://' in text_lower or 't.me/' in text_lower or 'www.' in text_lower:
        return "link"
    
    # Check for bad words
    for word in BAD_WORDS:
        if word in text_lower:
            return "bad_word"
    
    return "ok"

def end_chat(user_id):
    """End chat for a user"""
    if user_id in users and users[user_id].get('partner'):
        partner_id = users[user_id]['partner']
        users[user_id]['partner'] = None
        users[user_id]['state'] = STATE_IDLE
        
        if partner_id in users:
            users[partner_id]['partner'] = None
            users[partner_id]['state'] = STATE_IDLE
        
        return partner_id
    return None

def find_match(user_id):
    """Find a match for user"""
    if user_id not in users:
        return None
    
    user_gender = users[user_id]['gender']
    user_pref = users[user_id]['preference']
    
    # Determine which queue to search
    if user_pref == "anyone":
        search_queues = ["male", "female"]
    else:
        search_queues = [user_pref]
    
    # Search for match
    for queue_gender in search_queues:
        for waiting_user in waiting_queue[queue_gender][:]:
            if waiting_user == user_id:
                continue
            
            if waiting_user not in users:
                waiting_queue[queue_gender].remove(waiting_user)
                continue
            
            waiting_pref = users[waiting_user]['preference']
            
            # Check compatibility
            if waiting_pref == "anyone" or waiting_pref == user_gender:
                # Match found!
                waiting_queue[queue_gender].remove(waiting_user)
                return waiting_user
    
    return None

### Command Handlers ###

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    user_id = update.effective_user.id
    
    if is_banned(user_id):
        ban_time = users[user_id]['ban_until']
        remaining = (ban_time - datetime.now()).seconds // 60
        await update.message.reply_text(f"⛔ You are banned for {remaining} more minutes.\nReason: Skip abuse")
        return
    
    # Initialize user
    users[user_id] = {
        'gender': None,
        'preference': None,
        'partner': None,
        'state': STATE_GENDER_SELECT,
        'skip_count': 0,
        'last_skip_time': None,
        'ban_until': None,
        'reports': 0
    }
    
    keyboard = [
        [InlineKeyboardButton("👨 Male", callback_data="gender_male")],
        [InlineKeyboardButton("👩 Female", callback_data="gender_female")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🌍 *Welcome to Anonymous Chat!*\n\n"
        "Connect with random strangers worldwide! 🎭\n\n"
        "📋 *Rules:*\n"
        "• No links allowed 🚫\n"
        "• No 18+ content 🔞\n"
        "• Be respectful ❤️\n"
        "• 3+ skips in 1 min = 5 min ban ⏱️\n\n"
        "*Choose your gender:*",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def find_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Find a chat partner"""
    user_id = update.effective_user.id
    
    if is_banned(user_id):
        ban_time = users[user_id]['ban_until']
        remaining = (ban_time - datetime.now()).seconds // 60
        await update.message.reply_text(f"⛔ You are banned for {remaining} more minutes.")
        return
    
    if user_id not in users or not users[user_id].get('gender'):
        await update.message.reply_text("Please use /start first!")
        return
    
    if users[user_id]['state'] == STATE_CHATTING:
        await update.message.reply_text("❌ You're already chatting! Use /stop to end.")
        return
    
    # Try to find match
    match = find_match(user_id)
    
    if match:
        # Match found!
        users[user_id]['partner'] = match
        users[user_id]['state'] = STATE_CHATTING
        users[match]['partner'] = user_id
        users[match]['state'] = STATE_CHATTING
        
        await context.bot.send_message(user_id, "✅ *Partner found!*\n\nStart chatting! 💬\n\n/next - Find new partner\n/stop - End chat\n/share - Share your ID", parse_mode='Markdown')
        await context.bot.send_message(match, "✅ *Partner found!*\n\nStart chatting! 💬\n\n/next - Find new partner\n/stop - End chat\n/share - Share your ID", parse_mode='Markdown')
    else:
        # Add to queue
        user_gender = users[user_id]['gender']
        if user_id not in waiting_queue[user_gender]:
            waiting_queue[user_gender].append(user_id)
        
        users[user_id]['state'] = STATE_WAITING
        await update.message.reply_text("🔍 *Searching for partner...*\n\nPlease wait ⏳", parse_mode='Markdown')

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop current chat"""
    user_id = update.effective_user.id
    
    if user_id not in users:
        await update.message.reply_text("Use /start first!")
        return
    
    # Remove from queue if waiting
    for queue in waiting_queue.values():
        if user_id in queue:
            queue.remove(user_id)
    
    partner_id = end_chat(user_id)
    
    await update.message.reply_text("❌ *Chat ended!*\n\nUse /find to search again.", parse_mode='Markdown')
    
    if partner_id:
        try:
            await context.bot.send_message(partner_id, "❌ *Partner left the chat!*\n\nUse /find to search again.", parse_mode='Markdown')
        except:
            pass

async def next_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skip to next partner"""
    user_id = update.effective_user.id
    
    if is_banned(user_id):
        ban_time = users[user_id]['ban_until']
        remaining = (ban_time - datetime.now()).seconds // 60
        await update.message.reply_text(f"⛔ You are banned for {remaining} more minutes.")
        return
    
    if user_id not in users or users[user_id]['state'] != STATE_CHATTING:
        await update.message.reply_text("❌ You're not chatting with anyone!")
        return
    
    # Skip abuse protection
    now = datetime.now()
    if users[user_id]['last_skip_time']:
        time_diff = (now - users[user_id]['last_skip_time']).seconds
        if time_diff < 60:  # Within 1 minute
            users[user_id]['skip_count'] += 1
        else:
            users[user_id]['skip_count'] = 1
    else:
        users[user_id]['skip_count'] = 1
    
    users[user_id]['last_skip_time'] = now
    
    # Check skip limit
    if users[user_id]['skip_count'] >= 4:
        users[user_id]['ban_until'] = now + timedelta(minutes=5)
        await update.message.reply_text("⛔ *You are banned for 5 minutes!*\n\nReason: Too many skips", parse_mode='Markdown')
        partner_id = end_chat(user_id)
        if partner_id:
            try:
                await context.bot.send_message(partner_id, "❌ Partner left. Use /find to search again.")
            except:
                pass
        return
    elif users[user_id]['skip_count'] == 3:
        await update.message.reply_text("⚠️ *Warning!* One more skip = 5 min ban", parse_mode='Markdown')
    
    # End current chat and find new
    partner_id = end_chat(user_id)
    if partner_id:
        try:
            await context.bot.send_message(partner_id, "❌ *Partner skipped!*\n\nUse /find to search again.", parse_mode='Markdown')
        except:
            pass
    
    # Auto search for new partner
    await find_command(update, context)

async def share_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Share Telegram ID with partner"""
    user_id = update.effective_user.id
    
    if user_id not in users or users[user_id]['state'] != STATE_CHATTING:
        await update.message.reply_text("❌ You need to be in a chat to share ID!")
        return
    
    partner_id = users[user_id]['partner']
    user = update.effective_user
    
    if not user.username:
        await update.message.reply_text("❌ You don't have a Telegram username!\n\nSet one in Settings → Username")
        return
    
    keyboard = [
        [InlineKeyboardButton("✅ Accept", callback_data=f"share_accept_{user_id}")],
        [InlineKeyboardButton("❌ Reject", callback_data=f"share_reject_{user_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        partner_id,
        f"📱 *Partner wants to share Telegram ID!*\n\nAccept?",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    await update.message.reply_text("📤 *ID share request sent!*\n\nWaiting for response...", parse_mode='Markdown')

async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Report current partner"""
    user_id = update.effective_user.id
    
    if user_id not in users or users[user_id]['state'] != STATE_CHATTING:
        await update.message.reply_text("❌ You're not chatting with anyone!")
        return
    
    partner_id = users[user_id]['partner']
    
    if partner_id in users:
        users[partner_id]['reports'] = users[partner_id].get('reports', 0) + 1
        
        if users[partner_id]['reports'] >= 3:
            users[partner_id]['ban_until'] = datetime.now() + timedelta(hours=24)
            await context.bot.send_message(partner_id, "⛔ *You are banned for 24 hours!*\n\nReason: Multiple reports", parse_mode='Markdown')
        else:
            await context.bot.send_message(partner_id, f"⚠️ *Warning!* You were reported.\n\nReports: {users[partner_id]['reports']}/3", parse_mode='Markdown')
    
    end_chat(user_id)
    await update.message.reply_text("✅ *User reported and chat ended.*\n\nUse /find to search again.", parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all text messages"""
    user_id = update.effective_user.id
    text = update.message.text
    
    if user_id not in users or users[user_id]['state'] != STATE_CHATTING:
        return
    
    # Content moderation
    check = check_content(text)
    if check == "link":
        users[user_id]['ban_until'] = datetime.now() + timedelta(hours=1)
        await update.message.reply_text("⛔ *You are banned for 1 hour!*\n\nReason: Sharing links", parse_mode='Markdown')
        partner_id = end_chat(user_id)
        if partner_id:
            try:
                await context.bot.send_message(partner_id, "❌ Partner was banned. Use /find to search again.")
            except:
                pass
        return
    elif check == "bad_word":
        users[user_id]['ban_until'] = datetime.now() + timedelta(hours=1)
        await update.message.reply_text("⛔ *You are banned for 1 hour!*\n\nReason: 18+ content", parse_mode='Markdown')
        partner_id = end_chat(user_id)
        if partner_id:
            try:
                await context.bot.send_message(partner_id, "❌ Partner was banned. Use /find to search again.")
            except:
                pass
        return
    
    # Forward message to partner
    partner_id = users[user_id]['partner']
    if partner_id:
        try:
            await context.bot.send_message(partner_id, text)
        except:
            await update.message.reply_text("❌ *Partner is unavailable!*\n\nUse /find to search again.", parse_mode='Markdown')
            end_chat(user_id)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button presses"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data.startswith("gender_"):
        gender = data.split("_")[1]
        users[user_id]['gender'] = gender
        users[user_id]['state'] = STATE_PREFERENCE_SELECT
        
        keyboard = [
            [InlineKeyboardButton("👨 Male", callback_data="pref_male")],
            [InlineKeyboardButton("👩 Female", callback_data="pref_female")],
            [InlineKeyboardButton("🌈 Anyone", callback_data="pref_anyone")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"✅ Gender set: *{gender.title()}*\n\n*Who do you want to chat with?*",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    elif data.startswith("pref_"):
        pref = data.split("_")[1]
        users[user_id]['preference'] = pref
        users[user_id]['state'] = STATE_IDLE
        
        await query.edit_message_text(
            f"✅ *Preference set: {pref.title()}*\n\n"
            f"Now use /find to start chatting! 🚀",
            parse_mode='Markdown'
        )
    
    elif data.startswith("share_accept_"):
        requester_id = int(data.split("_")[2])
        
        if user_id not in users or users[user_id]['state'] != STATE_CHATTING:
            await query.edit_message_text("❌ Chat already ended!")
            return
        
        requester_user = await context.bot.get_chat(requester_id)
        current_user = await context.bot.get_chat(user_id)
        
        if requester_user.username and current_user.username:
            await context.bot.send_message(requester_id, f"✅ *ID Shared!*\n\nPartner: @{current_user.username}", parse_mode='Markdown')
            await context.bot.send_message(user_id, f"✅ *ID Shared!*\n\nPartner: @{requester_user.username}", parse_mode='Markdown')
            await query.edit_message_text("✅ *ID shared successfully!*", parse_mode='Markdown')
        else:
            await query.edit_message_text("❌ One of you doesn't have a username!")
    
    elif data.startswith("share_reject_"):
        requester_id = int(data.split("_")[2])
        
        await context.bot.send_message(requester_id, "❌ *Partner rejected ID share request.*", parse_mode='Markdown')
        await query.edit_message_text("❌ *Request rejected.*", parse_mode='Markdown')

def main():
    """Start the bot"""
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("find", find_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("next", next_command))
    app.add_handler(CommandHandler("share", share_command))
    app.add_handler(CommandHandler("report", report_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Start bot
    logger.info("Bot started...")
    app.run_polling()

if __name__ == '__main__':
    main()