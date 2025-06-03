import os
import time
import json
from datetime import datetime, timedelta
from collections import defaultdict, deque
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext
import requests
import docx
import logging

USER_AI_STATUS = defaultdict(bool)
TOKEN = os.environ['TELEGRAM_TOKEN']
ADMIN_CHAT_ID = 1234567890 # your telegram ID 

REFERRALS = defaultdict(list)

MODEL_NAME = "CubikAI/TinyCubik-v1.1.2"
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForCausalLM.from_pretrained(MODEL_NAME)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = model.to(device)

# bot version
CV = "v1.0"

LIMITS_FILE = "limits.json"
HISTORY_FILE = "chat_history.json"

MAX_HISTORY_ITEMS = 20 # max remembers the history of dialogues in chat_history.json
MAX_DISPLAYED_HISTORY = 10 # number of displays from the file (recent)
MAX_MEMORY_MESSAGES = 50 # AI memory number of messages 

MAX_REQUESTS_PER_MINUTE = 5
MAX_REQUESTS_PER_WEEK = 75
WHITELISTED_USERS = {1010101010, 1234567890} # premium users

USER_RATE_LIMIT = defaultdict(list)
USER_WEEKLY_LIMIT = defaultdict(list)
USER_MESSAGE_HISTORY = defaultdict(lambda: deque(maxlen=MAX_MEMORY_MESSAGES))
USER_DOCUMENTS = defaultdict(str)

# online rules that will work in every dialog
CUBIK_RULES = f"""[You are Cubik, a multilingual assistant. Your rules:
1. Respond in the user's detected language
2. ...
3. ...
4. ...
]"""

# generating responses from AI
def generate_tinycubik_response(user_text: str, user_id: int, context: CallbackContext) -> str:
    document_context = ""
    if USER_DOCUMENTS.get(user_id):
        document_context = f"\n\n[USER_DOCUMENT CONTENT]:\n{USER_DOCUMENTS[user_id][:2000]}"

    messages = build_message_history(user_id, user_text, document_context)
    
    chat = []
    for msg in messages:
        if msg['role'] == 'system':
            chat.append({"role": "system", "content": msg['content']})
        else:
            chat.append({"role": msg['role'], "content": msg['content']})
    
    # Generate response
    try:
        input_ids = tokenizer.apply_chat_template(
            chat,
            add_generation_prompt=True,
            return_tensors="pt"
        ).to(device)
        
        outputs = model.generate(
            input_ids,
            max_new_tokens=512,
            do_sample=True,
            temperature=0.7,
            top_p=0.9,
            pad_token_id=tokenizer.eos_token_id
        )
        
        response = tokenizer.decode(outputs[0][input_ids.shape[-1]:], skip_special_tokens=True)
        return response.strip()
    
    except Exception as e:
        print(f"Error generating response: {e}")
        return "Technical issues. Please try again later."

def show_premium_features(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id

    text = (
            "Gold Features:\n\n"
            "• Unlimited requests\n"
            "• DOCX file analysis\n"
            "• Priority access\n"
            "• No ads\n\n\n"
            "Standart Features:\n\n"
            f"• {MAX_REQUESTS_PER_WEEK} requests/week\n"
            f"• Basic AI models\n"
            f"• Standard speed\n\n"
        )

    keyboard = [
        [InlineKeyboardButton("Main Menu", callback_data="main_menu")]
    ]

    query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def load_chat_history():
    if Path(HISTORY_FILE).exists():
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"History load error: {e}")
            return {}
    return {}

def save_chat_history(history):
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"History save error: {e}")

def update_chat_history(user_id: int, user_message: str, bot_response: str):
    history = load_chat_history()

    if str(user_id) not in history:
        history[str(user_id)] = []

    history[str(user_id)].append({
        "timestamp": datetime.now().isoformat(),
        "user": user_message,
        "bot": bot_response
    })

    history[str(user_id)] = history[str(user_id)][-MAX_HISTORY_ITEMS:]
    save_chat_history(history)

def clear_user_history(user_id: int):
    history = load_chat_history()
    if str(user_id) in history:
        del history[str(user_id)]
        save_chat_history(history)
    USER_MESSAGE_HISTORY[user_id].clear()
    USER_DOCUMENTS[user_id] = ""
    return True

def load_history_from_file():
    history = load_chat_history()
    for user_id, messages in history.items():
        for msg in messages:
            USER_MESSAGE_HISTORY[int(user_id)].append(msg['user'])
            USER_MESSAGE_HISTORY[int(user_id)].append(msg['bot'])

def start(update: Update, context: CallbackContext):
        user = update.effective_user
        USER_AI_STATUS[user.id] = True

        if is_whitelisted(user.id):
                text = (
                    f"Main menu\n\nHi {user.first_name}, I'm Cubik, your Premium AI assistant\nI'll help you with anything\n\n"
                    f"DVD-Gold active\n"
                    f"Your referrals: {len(REFERRALS[user.id])}")
                keyboard = [
                 [
                    InlineKeyboardButton("News", url="https://t.me/your_news"),
                    InlineKeyboardButton("Commands", url="https://t.me/your_news/61") # example
                 ],
                 [
                    InlineKeyboardButton("Invite", callback_data="invite")
                  ]
                 ]
                reply_markup = InlineKeyboardMarkup(keyboard)
        else:
                remaining = MAX_REQUESTS_PER_WEEK - len([t for t in USER_WEEKLY_LIMIT[user.id] 
                                                      if t > datetime.now() - timedelta(weeks=1)])
                text = (
                    f"Main Menu\n\nHi {user.first_name}, I'm Cubik, your AI assistant in your little problems\nWhat are we going to talk about?\n\n💿You have \"DVD-Standart\" plan {MAX_REQUESTS_PER_WEEK} requests per week\n"
                    f"Requests left: {remaining}/{MAX_REQUESTS_PER_WEEK}\n\n"
                    f"Invite friends: /ref")

                keyboard = [
                    [
            InlineKeyboardButton("News", url="https://t.me/your_news"),
            InlineKeyboardButton("Commands", url="https://t.me/your_news/61")
                    ],
                    [
            InlineKeyboardButton("Invite", callback_data="invite"),
                    ],
                    [
            InlineKeyboardButton("Buy Gold", callback_data="unlimited"),

            InlineKeyboardButton("Features", callback_data="show_premium_features")
                    ]
                  ]
                reply_markup = InlineKeyboardMarkup(keyboard)


        if update.message:
                update.message.reply_text(text, reply_markup=reply_markup)
        elif update.callback_query:
                update.callback_query.edit_message_text(text, reply_markup=reply_markup)

def stop_ai(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    USER_AI_STATUS[user_id] = False

    keyboard = [[InlineKeyboardButton("Activate AI", callback_data="activate_ai")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text(
        "Cubik: AI functionality disabled \n"
        "You can activate it anytime:",
        reply_markup=reply_markup
    )

# processing of docx documents 
def handle_document(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id

    if not is_whitelisted(user_id):
        update.message.reply_text("DOCX analysis is available only in Gold plan!\n\n"
                                "Upgrade to Gold to unlock this feature:",
                                reply_markup=InlineKeyboardMarkup([
                                    [InlineKeyboardButton("Buy Gold", callback_data="unlimited")]
                                ]))
        return

    file = update.message.document

    if file.file_name.endswith('.docx'):
        try:
            file_path = file.get_file().download()

            doc = docx.Document(file_path)
            text = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])

            USER_DOCUMENTS[user_id] = text[:15000]

            os.remove(file_path)

            update.message.reply_text(
                "Document loaded successfully! You can now ask questions about it.\n"
                "Example questions:\n"
                "• What is this document about?\n"
                "• Summarize the key points\n"
                "• Explain section 3"
            )
        except Exception as e:
            update.message.reply_text(f"Error processing document: {str(e)}")
    else:
        update.message.reply_text("Please send a .docx file for analysis")

def handle_message(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    user_text = update.message.text

    USER_MESSAGE_HISTORY[user_id].append(user_text)

    if not USER_AI_STATUS.get(user_id, True):
        keyboard = [[InlineKeyboardButton("Activate AI", callback_data="activate_ai")]]
        update.message.reply_text("AI is disabled. Activate it?", 
                                reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if is_whitelisted(user_id):
        response = generate_groq_response(user_text, user_id, context)
        USER_MESSAGE_HISTORY[user_id].append(response)
        update_chat_history(user_id, user_text, response)
        update.message.reply_text(f"{response}")
        return

    if check_weekly_limit(user_id):
        keyboard = [[InlineKeyboardButton("Buy", callback_data="unlimited")]]
        update.message.reply_text("Cubik: You've used all weekly requests (0 left)!\nNew requests available in a week\n\nBuy Gold to get unlimited requests",
        reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if is_rate_limited(user_id):
        keyboard = [[InlineKeyboardButton("Buy Gold", callback_data="unlimited")]]
        update.message.reply_text("Cubik: Please wait 60 seconds, I'm tired...",
        reply_markup=InlineKeyboardMarkup(keyboard))
        return

    USER_WEEKLY_LIMIT[user_id].append(datetime.now())
    response = generate_groq_response(user_text, user_id, context)
    USER_MESSAGE_HISTORY[user_id].append(response)
    update_chat_history(user_id, user_text, response)

    remaining = MAX_REQUESTS_PER_WEEK - len([t for t in USER_WEEKLY_LIMIT[user_id] 
                                          if t > datetime.now() - timedelta(weeks=1)])
    update.message.reply_text(f"Cubik: {response}\n\nRequests left: {remaining}/{MAX_REQUESTS_PER_WEEK}\nCreator: @cubik_news\nCubik - {CV}")

def clear_history(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if clear_user_history(user_id):
        update.message.reply_text("History cleared")
    else:
        update.message.reply_text("History clear")

def show_history(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    history = load_chat_history().get(str(user_id), [])

    if not history:
        update.message.reply_text("Your last 10 requests:\n\nHistory empty")
        return

    messages = []
    for i, item in enumerate(history[-MAX_DISPLAYED_HISTORY:], 1):
        messages.append(
         available {i}. [{item['timestamp'][:10]}]\n"
            f"You: {item['user'][:50]}{'...' if len(item['user']) > 50 else ''}\n"
            f"Bot: {item['bot'][:50]}{'...' if len(item['bot']) > 50 else ''}\n"
        )

    keyboard = [[InlineKeyboardButton("Clear History", callback_data="clear_history")]]
    update.message.reply_text(
        "Your last 10 requests:\n\n" + "\n".join(messages),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id

    if query.data == "unlimited":
        query.edit_message_text(
            f"Gold - 1$\n\nAdvantages of premium:\n" premium price 
            "- advantages1\n"
            "- advantages2\n"
            "- advantages3\n- And more\n\n"
            f"Do not forget to provide your ID during the purchase: {query.from_user.id}\n"
            "If you have any questions, please contact @support",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Buy", url="https://buy/gold")],
                [InlineKeyboardButton("Back", callback_data="main_menu")]
            ])
        )
    elif query.data == "invite":
        user_id = update.effective_user.id
        bot_username = context.bot.username
        ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
        query.edit_message_text(
            "*Referral Program*\n\n"
            f"Invite your friends via the link:\n`{ref_link}`\n\n"
            f"Your invited guests: {len(REFERRALS[user_id])}",
            reply_markup=InlineKeyboardMarkup([
            [
            InlineKeyboardButton("« Back", callback_data="main_menu")
            ]
        ])
    )
    elif query.data == "my_history":
        show_history(update, context)
    elif query.data == "clear_history":
        if clear_user_history(user_id):
            query.edit_message_text("History cleared")
        else:
            query.edit_message_text("History clear")
    elif query.data == "main_menu":
        start(update, context)
    elif query.data == "features":
        show_premium_features(update, context)
    elif query.data == "activate_ai":
        USER_AI_STATUS[user_id] = True
        start(update, context)

def build_message_history(user_id: int, user_text: str, document_context: str = "") -> list:
    messages = [{"role": "system", "content": CUBIK_RULES + document_context}]
    history = list(USER_MESSAGE_HISTORY[user_id])

    for i, msg in enumerate(history):
        role = "user" if i % 2 == 0 else "assistant"
        messages.append({"role": role, "content": msg})

    messages.append({"role": "user", "content": user_text})
    return messages

def process_response(response_json: dict) -> str:
    return response_json['choices'][0]['message']['content']

def is_whitelisted(user_id: int) -> bool:
    return user_id in WHITELISTED_USERS

def is_rate_limited(user_id: int) -> bool:
    if is_whitelisted(user_id):
        return False

    now = time.time()
    USER_RATE_LIMIT[user_id] = [t for t in USER_RATE_LIMIT[user_id] if now - t < 60]
    if len(USER_RATE_LIMIT[user_id]) >= MAX_REQUESTS_PER_MINUTE:
        return True
    USER_RATE_LIMIT[user_id].append(now)
    return False

def check_weekly_limit(user_id: int) -> bool:
    if is_whitelisted(user_id):
        return False

    now = datetime.now()
    USER_WEEKLY_LIMIT[user_id] = [t for t in USER_WEEKLY_LIMIT[user_id] if t > now - timedelta(weeks=1)]
    return len(USER_WEEKLY_LIMIT[user_id]) >= MAX_REQUESTS_PER_WEEK

def rotate_api_key():
    global current_key_index
    current_key_index = (current_key_index + 1) % len(GROQ_API_KEYS)
    print(f"Rotated to API key index: {current_key_index}")

def show_premium_info(update: Update, context: CallbackContext):
    user = update.effective_user
    update.message.reply_text(
        f"Gold - 1$\n\nAdvantages of premium:\n"
        "- advantages1\n"
        "- advantages2\n"
        "- advantages3\n- And more\n\n"
        f"Do not forget to provide your ID during the purchase: {user.id}\n"
        "If you have any questions, please contact @support",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Buy", url="https://buy/gold")],
            [InlineKeyboardButton("Main menu", callback_data="main_menu")]
        ])
    )

def restart(update: Update, context: CallbackContext):
    user = update.effective_user
    clear_user_history(user.id)
    USER_AI_STATUS[user.id] = False

    update.message.reply_text(
        "BOT HAS RESET ALL LOCAL FILES\n\nWhat has been save:\nYour remaining requests\nYour plan premium\n\nWhat has been delete:\nYour history\nLocal commands\nLocal bot history\nAI is disabled",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Restart", callback_data="main_menu")]
        ])
    )

def fdocx(update: Update, context: CallbackContext):
    user = update.effective_user
    update.message.reply_text(
        "Your Docx file:",     
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("« Menu", callback_data="main_menu")]
        ])
    )

def show_referral_info(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    bot_username = context.bot.username
    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"

    update.message.reply_text(
        "*Referral Program*\n\n"
        f"Invite your friends via the link:\n`{ref_link}`\n\n"
        f"Your invited guests: {len(REFERRALS[user_id])}",
        reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("Share", url=f"tg://msg_url?url={ref_link}&text=Hi!%20Test%20cool%20bot%20CubikAI")]
        ])
    )

def main():
    load_history_from_file()
    updater = Updater(TOKEN)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler('start', start))
    dp.add_handler(CommandHandler('fd', fdocx))
    dp.add_handler(CommandHandler('restart', restart))
    dp.add_handler(CommandHandler('stopai', stop_ai))
    dp.add_handler(CommandHandler('history', show_history))
    dp.add_handler(CommandHandler('clear', clear_history))
    dp.add_handler(CommandHandler('ref', show_referral_info))
    dp.add_handler(CallbackQueryHandler(button_handler))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    dp.add_handler(MessageHandler(Filters.document, handle_document))
    dp.add_handler(CallbackQueryHandler(show_premium_features, pattern="^features$"))

    print("Bot is running!")
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
