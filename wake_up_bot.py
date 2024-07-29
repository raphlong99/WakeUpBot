import os
import psycopg2
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv('TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL')

if TOKEN is None or DATABASE_URL is None:
    raise ValueError("No token or database URL provided! Please set the TOKEN and DATABASE_URL environment variables.")

# Connect to PostgreSQL database
try:
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cur = conn.cursor()
    logger.info("Successfully connected to the PostgreSQL database.")
except Exception as e:
    logger.error(f"Failed to connect to the PostgreSQL database: {e}")
    raise

# Create table for user points if it doesn't exist
cur.execute("""
CREATE TABLE IF NOT EXISTS user_points (
    user_id BIGINT PRIMARY KEY,
    username TEXT NOT NULL,
    points INT DEFAULT 0,
    last_awake_date DATE
);
""")
conn.commit()

# Function to save user data
def save_user(user_id, username, points, last_awake_date):
    cur.execute("""
    INSERT INTO user_points (user_id, username, points, last_awake_date)
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (user_id)
    DO UPDATE SET username = EXCLUDED.username, points = EXCLUDED.points, last_awake_date = EXCLUDED.last_awake_date;
    """, (user_id, username, points, last_awake_date))
    conn.commit()

# Function to load user data
def load_user(user_id):
    cur.execute("SELECT user_id, username, points, last_awake_date FROM user_points WHERE user_id = %s;", (user_id,))
    return cur.fetchone()

# Asynchronous function to start the bot
async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text('Welcome! Send your wake-up message containing "awake" between 6:00 AM and 6:30 AM to earn points.')

# Asynchronous function to create a new user
async def create_user(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    username = update.message.from_user.username

    if load_user(user_id) is None:
        save_user(user_id, username, 0, None)
        logger.info(f"Created new user: {username} (ID: {user_id}) with 0 points.")
        await update.message.reply_text(f'User {username} created with 0 points.')
    else:
        await update.message.reply_text(f'User {username} already exists.')

# Asynchronous function to check wake-up time and message content
async def check_wake_up(update: Update, context: CallbackContext) -> None:
    if update.message is None:
        logger.warning("Received an update without a message.")
        return

    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    message_text = update.message.text.lower()
    now = datetime.now()

    logger.info(f"Received message at {now}. Chat ID: {chat_id}, User ID: {user_id}, Username: {username}")

    if chat_id == -1002211346895:  # Replace with your actual group chat ID
        user_data = load_user(user_id)
        if user_data is None:
            await update.message.reply_text(f'User {username} does not exist. Please register using /createuser.')
            return

        _, _, points, last_awake_date = user_data
        today = now.date()

        if now.hour == 6 and now.minute < 31:
            if 'awake' in message_text:
                if last_awake_date != today:
                    points += 1
                    save_user(user_id, username, points, today)
                    logger.info(f"User {username} ({user_id}) earned a point. Total: {points}")
                    await update.message.reply_text(f'Great job {username}! Your current points: {points}')
                else:
                    await update.message.reply_text(f'You have already earned a point today, {username}!')
            else:
                logger.info(f"Message from {username} ({user_id}) does not contain the keyword 'awake'.")
                await update.message.reply_text('Are you sure you are awake?')
        else:
            logger.info(f"Message from {username} ({user_id}) is outside the allowed time window.")
            await update.message.reply_text('Too late or too early! Try again between 6:00 AM and 6:30 AM.')
    else:
        logger.warning(f"Message from unexpected chat ID: {chat_id}")

# Asynchronous function to display the leaderboard
async def leaderboard(update: Update, context: CallbackContext) -> None:
    cur.execute("SELECT username, points FROM user_points ORDER BY points DESC;")
    users = cur.fetchall()
    leaderboard_message = "Leaderboard:\n"
    for username, points in users:
        leaderboard_message += f"{username}: {points} points\n"
        logger.info(f"User on leaderboard: {username} with {points} points.")
    await update.message.reply_text(leaderboard_message)

# Asynchronous function to get chat ID (for setup purposes)
async def get_chat_id(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    await update.message.reply_text(f'Chat ID: {chat_id}')

# Test command to check database connection
async def test_db(update: Update, context: CallbackContext) -> None:
    try:
        cur.execute("SELECT 1;")
        result = cur.fetchone()
        if result:
            await update.message.reply_text("Database connection is working!")
        else:
            await update.message.reply_text("Database connection test failed.")
    except Exception as e:
        await update.message.reply_text(f"Database connection error: {e}")

def main() -> None:
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("createuser", create_user))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("getchatid", get_chat_id))  # Remove this line after getting the chat ID
    app.add_handler(CommandHandler("testdb", test_db))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_wake_up))

    app.run_polling()

if __name__ == '__main__':
    main()