import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from datetime import datetime
import json
import logging

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv('TOKEN')

if TOKEN is None:
    raise ValueError("No token provided! Please set the TOKEN environment variable.")

# Load or initialize user points
try:
    with open('points.json', 'r') as file:
        user_points = json.load(file)
except FileNotFoundError:
    user_points = {}

# Function to save user points to file
def save_points():
    with open('points.json', 'w') as file:
        json.dump(user_points, file)

# Asynchronous function to start the bot
async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text('Welcome! Send your wake-up message containing "awake" between 6:00 AM and 6:30 AM to earn points.')

# Asynchronous function to create a new user
async def create_user(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    user_name = update.message.from_user.username

    if user_id not in user_points:
        user_points[user_id] = {'points': 0, 'username': user_name, 'last_awake_date': None}
        save_points()
        logger.info(f"Created new user: {user_name} (ID: {user_id}) with 0 points.")
        await update.message.reply_text(f'User {user_name} created with 0 points.')
    else:
        await update.message.reply_text(f'User {user_name} already exists.')

# Asynchronous function to check wake-up time and message content
async def check_wake_up(update: Update, context: CallbackContext) -> None:
    if update.message is None:
        logger.warning("Received an update without a message.")
        return

    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    user_name = update.message.from_user.username
    message_text = update.message.text.lower()
    now = datetime.now()

    # Debug: print current time and chat ID
    logger.info(f"Received message at {now}. Chat ID: {chat_id}, User ID: {user_id}, Username: {user_name}")

    # Ensure message is from the specific group chat
    if chat_id == -1002211346895:  # Replace with your actual group chat ID
        if user_id not in user_points:
            await update.message.reply_text(f'User {user_name} does not exist. Please register using /createuser.')
            return

        last_awake_date = user_points[user_id]['last_awake_date']
        today = now.date().isoformat()

        if now.hour == 6 and now.minute < 31:
            if 'awake' in message_text:
                if last_awake_date != today:
                    user_points[user_id]['points'] += 1
                    user_points[user_id]['last_awake_date'] = today
                    save_points()
                    logger.info(f"User {user_name} ({user_id}) earned a point. Total: {user_points[user_id]['points']}")
                    await update.message.reply_text(f'Great job {user_name}! Your current points: {user_points[user_id]["points"]}')
                else:
                    await update.message.reply_text(f'You have already earned a point today, {user_name}!')
            else:
                logger.info(f"Message from {user_name} ({user_id}) does not contain the keyword 'awake'.")
                await update.message.reply_text('Are you sure you are awake?')
        else:
            logger.info(f"Message from {user_name} ({user_id}) is outside the allowed time window.")
            await update.message.reply_text('Too late or too early! Try again between 6:00 AM and 6:30 AM.')
    else:
        logger.warning(f"Message from unexpected chat ID: {chat_id}")

# Asynchronous function to display the leaderboard
async def leaderboard(update: Update, context: CallbackContext) -> None:
    leaderboard_message = "Leaderboard:\n"
    sorted_users = sorted(user_points.values(), key=lambda x: x['points'], reverse=True)
    for user in sorted_users:
        leaderboard_message += f"{user['username']}: {user['points']} points\n"
        logger.info(f"User on leaderboard: {user['username']} with {user['points']} points.")
    await update.message.reply_text(leaderboard_message)

# Asynchronous function to get chat ID (for setup purposes)
async def get_chat_id(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    await update.message.reply_text(f'Chat ID: {chat_id}')

def main() -> None:
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("createuser", create_user))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("getchatid", get_chat_id))  # Remove this line after getting the chat ID
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_wake_up))

    app.run_polling()

if __name__ == '__main__':
    main()