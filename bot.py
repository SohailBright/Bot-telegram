from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
import os
import asyncio
import logging
from datetime import datetime, timedelta

BOT_TOKEN = os.environ.get("BOT_TOKEN")

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Data storage
users = {}
waiting_queue = {"male": [], "female": []}

# Bad words list
BAD_WORDS = ["sex", "nude", "porn", "xxx", "dick", "pussy", "chut", "lund", "rand", "boobs", "fuck", "bhosdike", "madarchod", "behenchod", "gaand"]

# Report reasons
REPORT_REASONS = [
    "Spam / Flooding",
    "18+ / Sexual Content",
    "Harassment / Bullying",
    "Fake Gender",
    "Selling / Advertising",
    "Abusive Language",
    "Sharing Personal Info",
    "Other"
]

# States
STATE_IDLE = "idle"
STATE_GENDER_SELECT = "gender_select"
STATE_PREFERENCE_SELECT = "preference_select"
STATE_CHATTING = "chatting"
STATE_WAITING = "waiting"

### Helper Functions ###

def get_user(user_id):
    """Get or create user data"""
    if user_id not in users:
        users[user_id] = {
            'gender': None,
            'preference': None,
            'partner': None,
            'state': STATE_IDLE,
            'skip_count': 0,
            'last_skip_time': None,
            'ban_until': None,
            'reports': 0,
            'report_reasons': [],
            'likes': 0,
            'total_chats': 0,
            'last_partner': None
        }
    return users[user_id]

def is_banned(user_id):
    """Check if user is banned"""
    user = get_user(user_id)
    if user.get('ban_until'):
        if datetime.now() < user['ban_until']:
            return True
        else:
            user['ban_until'] = None
    return False

def check_content(text):
    """Check for bad words or links"""
    text_lower = text.lower()
    
    if 'http://' in text_lower or 'https://' in text_lower or 't.me/' in text_lower or 'www.' in text_lower or '.com' in text_lower or '.in' in text_lower:
        return "link"
    
    for word in BAD_WORDS:
        if word in text_lower:
            return "bad_word"
    
    return "ok"

def end_chat(user_id):
    """End chat for a user"""
    user = get_user(user_id)
    if user.get('partner'):
        partner_id = user['partner']
        user['last_partner'] = partner_id
        user['partner'] = None
        user['state'] = STATE_IDLE
        user['total_chats'] += 1
        
        if partner_id in users:
            users[partner_id]['last_partner'] = user_id
            users[partner_id]['partner'] = None
            users[partner_id]['state'] = STATE_IDLE
            users[partner_id]['total_chats'] += 1
        
        return partner_id
    return None

def find_match(user_id):
    """Find a match for user"""
    user = get_user(user_id)
    user_gender = user['gender']
    user_pref = user['preference']
    
    if user_pref == "anyone":
        search_queues = ["male", "female"]
    else:
        search_queues = [user_pref]
    
    for queue_gender in search_queues:
        for waiting_user in waiting_queue[queue_gender][:]:
            if waiting_user == user_id:
                continue
            
            if waiting_user not in users:
                waiting_queue[queue_gender].remove(waiting_user)
                continue
            
            waiting_pref = users[waiting_user]['preference']
            
            if waiting_pref == "anyone" or waiting_pref == user_gender:
                waiting_queue[queue_gender].remove(waiting_user)
                return waiting_user
    
    return None

def get_chat_buttons():
    """Buttons shown during chat"""
    keyboard = [
        [
            InlineKeyboardButton("⏭ Next", callback_data="action_next"),
            InlineKeyboardButton("🛑 Stop", callback_data="action_stop")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_search_buttons():
    """Buttons shown during searching"""
    keyboard = [
        [InlineKeyboardButton("🛑 Stop Searching", callback_data="action_stop_search")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_after_chat_buttons():
    """Buttons shown after chat ends"""
    keyboard = [
        [
            InlineKeyboardButton("👍 Like Partner", callback_data="action_like"),
            InlineKeyboardButton("🚨 Report", callback_data="action_report")
        ],
        [
            InlineKeyboardButton("🔍 Find New", callback_data="action_find"),
            InlineKeyboardButton("🏠 Home", callback_data="action_home")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_report_buttons():
    """Report reason buttons"""
    keyboard = []
    for i, reason in enumerate(REPORT_REASONS):
        keyboard.append([InlineKeyboardButton(reason, callback_data=f"report_{i}")])
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="report_cancel")])
    return InlineKeyboardMarkup(keyboard)

def get_idle_buttons():
    """Buttons when user is idle"""
    keyboard = [
        [InlineKeyboardButton("🔍 Find Partner", callback_data="action_find")],
        [InlineKeyboardButton("📊 My Profile", callback_data="action_profile")]
    ]
    return InlineKeyboardMarkup(keyboard)

### Command Handlers ###

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    user_id = update.effective_user.id
    
    if is_banned(user_id):
        ban_time = users[user_id]['ban_until']
        remaining = (ban_time - datetime.now()).seconds // 60
        await update.message.reply_text(f"⛔ You are banned for {remaining} more minutes.\nReason: Violation of rules")
        return
    
    user = get_user(user_id)
    user['gender'] = None
    user['preference'] = None
    user['partner'] = None
    user['state'] = STATE_GENDER_SELECT
    
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
        "⭐ *Features:*\n"
        "• Like your partner if you enjoy chatting 👍\n"
        "• Report bad users 🚨\n"
        "• Share your ID safely 📱\n\n"
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
        await update.message.reply_text("❌ You're already chatting!", reply_markup=get_chat_buttons())
        return
    
    match = find_match(user_id)
    
    if match:
        users[user_id]['partner'] = match
        users[user_id]['state'] = STATE_CHATTING
        users[match]['partner'] = user_id
        users[match]['state'] = STATE_CHATTING
        
        # Get partner likes
        partner_likes_for_user = users[match].get('likes', 0)
        user_likes_for_partner = users[user_id].get('likes', 0)
        
        await context.bot.send_message(
            user_id,
            f"✅ *Partner found!* 🎉\n\n"
            f"Partner's ⭐ Likes: {partner_likes_for_user}\n\n"
            f"Start chatting! 💬\n\n"
            f"Use buttons below or commands:\n"
            f"/next - Find new partner\n"
            f"/stop - End chat\n"
            f"/share - Share your ID",
            reply_markup=get_chat_buttons(),
            parse_mode='Markdown'
        )
        await context.bot.send_message(
            match,
            f"✅ *Partner found!* 🎉\n\n"
            f"Partner's ⭐ Likes: {user_likes_for_partner}\n\n"
            f"Start chatting! 💬\n\n"
            f"Use buttons below or commands:\n"
            f"/next - Find new partner\n"
            f"/stop - End chat\n"
            f"/share - Share your ID",
            reply_markup=get_chat_buttons(),
            parse_mode='Markdown'
        )
    else:
        user_gender = users[user_id]['gender']
        if user_id not in waiting_queue[user_gender]:
            waiting_queue[user_gender].append(user_id)
        
        users[user_id]['state'] = STATE_WAITING
        
        # Count people in queue
        total_waiting = len(waiting_queue['male']) + len(waiting_queue['female'])
        
        await update.message.reply_text(
            f"🔍 *Searching for partner...*\n\n"
            f"👥 People in queue: {total_waiting}\n"
            f"Please wait ⏳",
            reply_markup=get_search_buttons(),
            parse_mode='Markdown'
        )

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop current chat"""
    user_id = update.effective_user.id
    
    if user_id not in users:
        await update.message.reply_text("Use /start first!")
        return
    
    for queue in waiting_queue.values():
        if user_id in queue:
            queue.remove(user_id)
    
    if users[user_id]['state'] == STATE_WAITING:
        users[user_id]['state'] = STATE_IDLE
        await update.message.reply_text(
            "🛑 *Search cancelled!*\n\n"
            "Use /find to search again.",
            reply_markup=get_idle_buttons(),
            parse_mode='Markdown'
        )
        return
    
    partner_id = end_chat(user_id)
    
    await update.message.reply_text(
        "❌ *Chat ended!*\n\n"
        "What would you like to do?",
        reply_markup=get_after_chat_buttons(),
        parse_mode='Markdown'
    )
    
    if partner_id:
        try:
            await context.bot.send_message(
                partner_id,
                "❌ *Partner left the chat!*\n\n"
                "What would you like to do?",
                reply_markup=get_after_chat_buttons(),
                parse_mode='Markdown'
            )
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
    
    now = datetime.now()
    if users[user_id]['last_skip_time']:
        time_diff = (now - users[user_id]['last_skip_time']).seconds
        if time_diff < 60:
            users[user_id]['skip_count'] += 1
        else:
            users[user_id]['skip_count'] = 1
    else:
        users[user_id]['skip_count'] = 1
    
    users[user_id]['last_skip_time'] = now
    
    if users[user_id]['skip_count'] >= 4:
        users[user_id]['ban_until'] = now + timedelta(minutes=5)
        await update.message.reply_text("⛔ *You are banned for 5 minutes!*\n\nReason: Too many skips", parse_mode='Markdown')
        partner_id = end_chat(user_id)
        if partner_id:
            try:
                await context.bot.send_message(
                    partner_id,
                    "❌ *Partner left!*\n\nWhat would you like to do?",
                    reply_markup=get_after_chat_buttons(),
                    parse_mode='Markdown'
                )
            except:
                pass
        return
    elif users[user_id]['skip_count'] == 3:
        await update.message.reply_text("⚠️ *Warning!* One more skip = 5 min ban", parse_mode='Markdown')
    
    partner_id = end_chat(user_id)
    if partner_id:
        try:
            await context.bot.send_message(
                partner_id,
                "❌ *Partner skipped!*\n\nWhat would you like to do?",
                reply_markup=get_after_chat_buttons(),
                parse_mode='Markdown'
            )
        except:
            pass
    
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

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user profile"""
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    gender_emoji = "👨" if user['gender'] == 'male' else "👩" if user['gender'] == 'female' else "❓"
    
    await update.message.reply_text(
        f"📊 *Your Profile*\n\n"
        f"{gender_emoji} Gender: {(user['gender'] or 'Not set').title()}\n"
        f"⭐ Likes: {user.get('likes', 0)}\n"
        f"💬 Total Chats: {user.get('total_chats', 0)}\n"
        f"🚨 Reports: {user.get('reports', 0)}\n\n"
        f"Keep chatting to get more likes! 👍",
        reply_markup=get_idle_buttons(),
        parse_mode='Markdown'
    )
async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Report current partner"""
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if user['state'] == STATE_CHATTING:
        partner_id = end_chat(user_id)
        user['last_partner'] = partner_id
        
        if partner_id:
            try:
                await context.bot.send_message(
                    partner_id,
                    "❌ *Partner left the chat!*\n\nWhat would you like to do?",
                    reply_markup=get_after_chat_buttons(),
                    parse_mode='Markdown'
                )
            except:
                pass
        
        await update.message.reply_text(
            "🚨 *Report User*\n\nSelect a reason:",
            reply_markup=get_report_buttons(),
            parse_mode='Markdown'
        )
    elif user.get('last_partner'):
        await update.message.reply_text(
            "🚨 *Report User*\n\nSelect a reason:",
            reply_markup=get_report_buttons(),
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ No one to report!")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all text messages"""
    
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all text messages"""
    user_id = update.effective_user.id
    text = update.message.text
    
    if user_id not in users or users[user_id]['state'] != STATE_CHATTING:
        if user_id in users and users[user_id].get('gender'):
            await update.message.reply_text(
                "❌ You're not in a chat!\n\nUse /find to start chatting.",
                reply_markup=get_idle_buttons()
            )
        return
    
    check = check_content(text)
    if check == "link":
        users[user_id]['ban_until'] = datetime.now() + timedelta(hours=1)
        await update.message.reply_text("⛔ *You are banned for 1 hour!*\n\nReason: Sharing links", parse_mode='Markdown')
        partner_id = end_chat(user_id)
        if partner_id:
            try:
                await context.bot.send_message(
                    partner_id,
                    "❌ *Partner was banned!*\n\nWhat would you like to do?",
                    reply_markup=get_after_chat_buttons(),
                    parse_mode='Markdown'
                )
            except:
                pass
        return
    elif check == "bad_word":
        users[user_id]['ban_until'] = datetime.now() + timedelta(hours=1)
        await update.message.reply_text("⛔ *You are banned for 1 hour!*\n\nReason: 18+ / Abusive content", parse_mode='Markdown')
        partner_id = end_chat(user_id)
        if partner_id:
            try:
                await context.bot.send_message(
                    partner_id,
                    "❌ *Partner was banned!*\n\nWhat would you like to do?",
                    reply_markup=get_after_chat_buttons(),
                    parse_mode='Markdown'
                )
            except:
                pass
        return
    
    partner_id = users[user_id]['partner']
    if partner_id:
        try:
            await context.bot.send_message(partner_id, text)
        except:
            await update.message.reply_text(
                "❌ *Partner is unavailable!*",
                reply_markup=get_after_chat_buttons(),
                parse_mode='Markdown'
            )
            end_chat(user_id)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all button presses"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    # Gender selection
    if data.startswith("gender_"):
        gender = data.split("_")[1]
        user = get_user(user_id)
        user['gender'] = gender
        user['state'] = STATE_PREFERENCE_SELECT
        
        keyboard = [
            [InlineKeyboardButton("👨 Male", callback_data="pref_male")],
            [InlineKeyboardButton("👩 Female", callback_data="pref_female")],
            [InlineKeyboardButton("🌈 Anyone", callback_data="pref_anyone")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"✅ Gender: *{gender.title()}*\n\n*Who do you want to chat with?*",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    # Preference selection
    elif data.startswith("pref_"):
        pref = data.split("_")[1]
        user = get_user(user_id)
        user['preference'] = pref
        user['state'] = STATE_IDLE
        
        await query.edit_message_text(
            f"✅ *Setup Complete!*\n\n"
            f"👤 Gender: {user['gender'].title()}\n"
            f"🎯 Looking for: {pref.title()}\n\n"
            f"Tap below to start chatting! 🚀",
            reply_markup=get_idle_buttons(),
            parse_mode='Markdown'
        )
    
    # Action: Find
    elif data == "action_find":
        user = get_user(user_id)
        
        if not user.get('gender'):
            await query.edit_message_text("Please use /start first!")
            return
        
        if is_banned(user_id):
            ban_time = user['ban_until']
            remaining = (ban_time - datetime.now()).seconds // 60
            await query.edit_message_text(f"⛔ You are banned for {remaining} more minutes.")
            return
        
        if user['state'] == STATE_CHATTING:
            await query.edit_message_text("❌ You're already chatting!", reply_markup=get_chat_buttons())
            return
        
        match = find_match(user_id)
        
        if match:
            users[user_id]['partner'] = match
            users[user_id]['state'] = STATE_CHATTING
            users[match]['partner'] = user_id
            users[match]['state'] = STATE_CHATTING
            
            partner_likes = users[match].get('likes', 0)
            user_likes = users[user_id].get('likes', 0)
            
            await query.edit_message_text(
                f"✅ *Partner found!* 🎉\n\n"
                f"Partner's ⭐ Likes: {partner_likes}\n\n"
                f"Start chatting! 💬",
                reply_markup=get_chat_buttons(),
                parse_mode='Markdown'
            )
            await context.bot.send_message(
                match,
                f"✅ *Partner found!* 🎉\n\n"
                f"Partner's ⭐ Likes: {user_likes}\n\n"
                f"Start chatting! 💬",
                reply_markup=get_chat_buttons(),
                parse_mode='Markdown'
            )
        else:
            user_gender = user['gender']
            if user_id not in waiting_queue[user_gender]:
                waiting_queue[user_gender].append(user_id)
            
            user['state'] = STATE_WAITING
            total_waiting = len(waiting_queue['male']) + len(waiting_queue['female'])
            
            await query.edit_message_text(
                f"🔍 *Searching for partner...*\n\n"
                f"👥 People in queue: {total_waiting}\n"
                f"Please wait ⏳",
                reply_markup=get_search_buttons(),
                parse_mode='Markdown'
            )
    
    # Action: Stop Search
    elif data == "action_stop_search":
        user = get_user(user_id)
        
        for queue in waiting_queue.values():
            if user_id in queue:
                queue.remove(user_id)
        
        user['state'] = STATE_IDLE
        
        await query.edit_message_text(
            "🛑 *Search cancelled!*\n\n"
            "What would you like to do?",
            reply_markup=get_idle_buttons(),
            parse_mode='Markdown'
        )
    
    # Action: Stop Chat
    elif data == "action_stop":
        user = get_user(user_id)
        
        if user['state'] != STATE_CHATTING:
            await query.edit_message_text(
                "❌ You're not in a chat!",
                reply_markup=get_idle_buttons()
            )
            return
        
        partner_id = end_chat(user_id)
        
        await query.edit_message_text(
            "❌ *Chat ended!*\n\n"
            "What would you like to do?",
            reply_markup=get_after_chat_buttons(),
            parse_mode='Markdown'
        )
        
        if partner_id:
            try:
                await context.bot.send_message(
                    partner_id,
                    "❌ *Partner left the chat!*\n\n"
                    "What would you like to do?",
                    reply_markup=get_after_chat_buttons(),
                    parse_mode='Markdown'
                )
            except:
                pass
    
    # Action: Next
    elif data == "action_next":
        user = get_user(user_id)
        
        if user['state'] != STATE_CHATTING:
            await query.edit_message_text("❌ You're not chatting!", reply_markup=get_idle_buttons())
            return
        
        if is_banned(user_id):
            ban_time = user['ban_until']
            remaining = (ban_time - datetime.now()).seconds // 60
            await query.edit_message_text(f"⛔ Banned for {remaining} more minutes.")
            return
        
        now = datetime.now()
        if user['last_skip_time']:
            time_diff = (now - user['last_skip_time']).seconds
            if time_diff < 60:
                user['skip_count'] += 1
            else:
                user['skip_count'] = 1
        else:
            user['skip_count'] = 1
        
        user['last_skip_time'] = now
        
        if user['skip_count'] >= 4:
            user['ban_until'] = now + timedelta(minutes=5)
            partner_id = end_chat(user_id)
            await query.edit_message_text("⛔ *Banned for 5 minutes!*\n\nReason: Too many skips", parse_mode='Markdown')
            if partner_id:
                try:
                    await context.bot.send_message(
                        partner_id,
                        "❌ *Partner left!*",
                        reply_markup=get_after_chat_buttons(),
                        parse_mode='Markdown'
                    )
                except:
                    pass
            return
        elif user['skip_count'] == 3:
            await context.bot.send_message(user_id, "⚠️ *Warning!* One more skip = 5 min ban", parse_mode='Markdown')
        
        partner_id = end_chat(user_id)
        if partner_id:
            try:
                await context.bot.send_message(
                    partner_id,
                    "❌ *Partner skipped!*\n\nWhat would you like to do?",
                    reply_markup=get_after_chat_buttons(),
                    parse_mode='Markdown'
                )
            except:
                pass
        
        # Auto find new partner
        match = find_match(user_id)
        if match:
            users[user_id]['partner'] = match
            users[user_id]['state'] = STATE_CHATTING
            users[match]['partner'] = user_id
            users[match]['state'] = STATE_CHATTING
            
            partner_likes = users[match].get('likes', 0)
            user_likes = users[user_id].get('likes', 0)
            
            await context.bot.send_message(
                user_id,
                f"✅ *New partner found!* 🎉\n\n"
                f"Partner's ⭐ Likes: {partner_likes}\n\n"
                f"Start chatting! 💬",
                reply_markup=get_chat_buttons(),
                parse_mode='Markdown'
            )
            await context.bot.send_message(
                match,
                f"✅ *Partner found!* 🎉\n\n"
                f"Partner's ⭐ Likes: {user_likes}\n\n"
                f"Start chatting! 💬",
                reply_markup=get_chat_buttons(),
                parse_mode='Markdown'
            )
        else:
            user_gender = user['gender']
            if user_id not in waiting_queue[user_gender]:
                waiting_queue[user_gender].append(user_id)
            user['state'] = STATE_WAITING
            total_waiting = len(waiting_queue['male']) + len(waiting_queue['female'])
            
            await context.bot.send_message(
                user_id,
                f"🔍 *Searching for new partner...*\n\n"
                f"👥 People in queue: {total_waiting}\n"
                f"Please wait ⏳",
                reply_markup=get_search_buttons(),
                parse_mode='Markdown'
            )
    
    # Action: Like
    elif data == "action_like":
        user = get_user(user_id)
        last_partner = user.get('last_partner')
        
        if not last_partner:
            await query.edit_message_text("❌ No partner to like!")
            return
        
        partner = get_user(last_partner)
        partner['likes'] = partner.get('likes', 0) + 1
        user['last_partner'] = None
        
        await query.edit_message_text(
            f"👍 *You liked your partner!*\n\n"
            f"Their total likes: ⭐ {partner['likes']}\n\n"
            f"What would you like to do?",
            reply_markup=get_idle_buttons(),
            parse_mode='Markdown'
        )
        
        try:
            await context.bot.send_message(
                last_partner,
                f"⭐ *Someone liked you!*\n\n"
                f"Your total likes: {partner['likes']} ⭐\n"
                f"Keep being awesome! 🎉"
            )
        except:
            pass
    
    # Action: Report
    elif data == "action_report":
        user = get_user(user_id)
        last_partner = user.get('last_partner')
        
        if not last_partner:
            await query.edit_message_text("❌ No partner to report!")
            return
        
        await query.edit_message_text(
            "🚨 *Report User*\n\n"
            "Select a reason:",
            reply_markup=get_report_buttons(),
            parse_mode='Markdown'
        )
    
    # Report reasons
    elif data.startswith("report_"):
        if data == "report_cancel":
            await query.edit_message_text(
                "❌ *Report cancelled!*\n\n"
                "What would you like to do?",
                reply_markup=get_idle_buttons(),
                parse_mode='Markdown'
            )
            return
        
        reason_index = int(data.split("_")[1])
        reason = REPORT_REASONS[reason_index]
        
        user = get_user(user_id)
        last_partner = user.get('last_partner')
        
        if last_partner and last_partner in users:
            partner = users[last_partner]
            partner['reports'] = partner.get('reports', 0) + 1
            partner['report_reasons'] = partner.get('report_reasons', [])
            partner['report_reasons'].append(reason)
            
            if partner['reports'] >= 3:
                partner['ban_until'] = datetime.now() + timedelta(hours=24)
                try:
                    await context.bot.send_message(
                        last_partner,
                        "⛔ *You are banned for 24 hours!*\n\n"
                        f"Reason: Multiple reports\n"
                        f"Total reports: {partner['reports']}",
                        parse_mode='Markdown'
                    )
                except:
                    pass
            else:
                try:
                    await context.bot.send_message(
                        last_partner,
                        f"⚠️ *Warning!* You were reported.\n\n"
                        f"Reason: {reason}\n"
                        f"Reports: {partner['reports']}/3\n\n"
                        f"3 reports = 24 hour ban!",
                        parse_mode='Markdown'
                    )
                except:
                    pass
        
        user['last_partner'] = None
        
        await query.edit_message_text(
            f"✅ *User reported!*\n\n"
            f"Reason: {reason}\n\n"
            f"Thank you for keeping the community safe! 🙏",
            reply_markup=get_idle_buttons(),
            parse_mode='Markdown'
        )
    
    # Action: Profile
    elif data == "action_profile":
        user = get_user(user_id)
        gender_emoji = "👨" if user['gender'] == 'male' else "👩" if user['gender'] == 'female' else "❓"
        
        await query.edit_message_text(
            f"📊 *Your Profile*\n\n"
            f"{gender_emoji} Gender: {(user['gender'] or 'Not set').title()}\n"
            f"⭐ Likes: {user.get('likes', 0)}\n"
            f"💬 Total Chats: {user.get('total_chats', 0)}\n"
            f"🚨 Reports: {user.get('reports', 0)}\n\n"
            f"Keep chatting to get more likes! 👍",
            reply_markup=get_idle_buttons(),
            parse_mode='Markdown'
        )
    
    # Action: Home
    elif data == "action_home":
        await query.edit_message_text(
            "🏠 *Home*\n\n"
            "What would you like to do?",
            reply_markup=get_idle_buttons(),
            parse_mode='Markdown'
        )
    
    # Share accept/reject
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

async def main():
    """Start the bot"""
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("find", find_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("next", next_command))
    app.add_handler(CommandHandler("share", share_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("report", report_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Start bot
    logger.info("Bot started...")
    
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()

if __name__ == '__main__':
    asyncio.run(main())