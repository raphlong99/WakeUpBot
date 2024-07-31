
import os
import psycopg2
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from datetime import datetime
import logging
import pytz
import openai

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
TOKEN = os.getenv('TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL')
OPENAI_API_KEY = os.getenv('LOUIE_BOT_API_KEY')

if TOKEN is None or DATABASE_URL is None or OPENAI_API_KEY is None:
    raise ValueError("Environment variables TOKEN, DATABASE_URL, and LOUIE_BOT_API_KEY are required!")

# Initialize OpenAI
openai.api_key = OPENAI_API_KEY

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

# Function to load all users
def load_all_users():
    cur.execute("SELECT user_id, username, points FROM user_points;")
    return cur.fetchall()

# Command: /start
async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text('Woof! 🐾 Welcome! Send your wake-up message containing "awake" between 6:00 AM and 6:30 AM to earn points. 🐶\nUse /help to check out all available commands. 🦴')

# Command: /createuser
async def create_user(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    username = update.message.from_user.username

    user_data = load_user(user_id)
    logger.info(f"User data for {username}: {user_data}")

    if user_data is None:
        save_user(user_id, username, 0, None)
        logger.info(f"Created new user: {username} (ID: {user_id}) with 0 points.")
        await update.message.reply_text(f'Woof! 🐶 User {username} created with 0 points. Let’s start fetching points! 🦴')
    else:
        await update.message.reply_text(f'User {username} already exists. 🐕')

# Function to check wake-up message
async def check_wake_up(update: Update, context: CallbackContext) -> None:
    if update.message is None:
        logger.warning("Received an update without a message.")
        return

    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    message_text = update.message.text.lower()
    
    # Check if the message contains "louie" first
    if 'louie' in message_text:
        logger.info("handling louie message")
        await handle_louie_message(update, context)
        return  # Ensure other handlers can process the message
    
    if 'awake' not in message_text:
        logger.info(f"Message from {username} ({user_id}) does not contain the keyword 'awake'. Ignoring.")
        return  # Ensure other handlers can process the message

    # Get current UTC time
    now_utc = datetime.now(pytz.utc)
    
    # Convert to your local timezone (e.g., Asia/Singapore)
    local_tz = pytz.timezone('Asia/Singapore')
    now_local = now_utc.astimezone(local_tz)
    
    logger.info(f"Received message at {now_local}. Chat ID: {chat_id}, User ID: {user_id}, Username: {username}")

    if chat_id == -1002211346895:  # Replace with your actual group chat ID
        user_data = load_user(user_id)
        if user_data is None:
            await update.message.reply_text(f'User {username} does not exist. Please register using /createuser. 🐶')
            return

        _, _, points, last_awake_date = user_data
        today = now_local.date()

        if now_local.hour == 6 and now_local.minute < 31:
            if last_awake_date != today:
                points += 1
                save_user(user_id, username, points, today)
                logger.info(f"User {username} ({user_id}) earned a point. Total: {points}")
                await update.message.reply_text(f'Good job, {username}! You earned a point! 🐾 Your current points: {points} 🏆')
                
                # Check if the message is from feliciaoyf and the date is 1st August 2024
                if username == 'feliciaoyf' and now_local.strftime('%Y-%m-%d') == '2024-08-01':
                    special_message = (
                        "🌸 Good morning, Felicia! 🌸\n\n"
                        "Louie here, wishing the most amazing girlfriend a very Happy National Girlfriend Day! 💖\n"
                        "Did you know? Our first date was exactly 143 days ago! 🥳💕\n"
                        "You are the sunshine in my life, and I cherish every moment we spend together. ☀️🐾\n"
                        "Let's make today as wonderful as you are! 💐✨"
                    )
                    await update.message.reply_text(special_message)
            else:
                await update.message.reply_text(f'You have already earned a point today, {username}! 🐕')
        else:
            logger.info(f"Message from {username} ({user_id}) is outside the allowed time window.")
            await update.message.reply_text('Too late or too early! Try again between 6:00 AM and 6:30 AM. 🕰️')
    else:
        logger.warning(f"Message from unexpected chat ID: {chat_id}")

# Function to handle messages containing "louie"
async def handle_louie_message(update: Update, context: CallbackContext) -> None:
    logger.info(f"Handling message from {update.message.from_user.username}")
    
    if update.message is None:
        logger.warning("Received an update without a message.")
        return

    user_message = update.message.text
    response = get_louie_response(user_message)
    logger.info(f"Response from OpenAI: {response}")
    await update.message.reply_text(response)

# Function to get a response from ChatGPT as Louie the dog
def get_louie_response(user_message):
    messages = [
        {"role": "system", "content": "You are Louie, a cute and friendly dog."},
        {"role": "user", "content": user_message}
    ]
    
    response = openai.ChatCompletion.create(
        model="gpt-4",  # Use "gpt-4" or "gpt-4-turbo" based on your subscription
        messages=messages,
        max_tokens=150,
        n=1,
        temperature=0.7
    )
    
    return response.choices[0].message['content'].strip()

# Command: /leaderboard
async def leaderboard(update: Update, context: CallbackContext) -> None:
    cur.execute("SELECT username, points FROM user_points ORDER BY points DESC;")
    users = cur.fetchall()
    leaderboard_message = "🏆 Leaderboard 🏆\n"
    for username, points in users:
        leaderboard_message += f"{username}: {points} points 🐾\n"
        logger.info(f"User on leaderboard: {username} with {points} points.")
    await update.message.reply_text(leaderboard_message)

# Command: /getchatid (for setup purposes)
async def get_chat_id(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    await update.message.reply_text(f'Chat ID: {chat_id}')

# Command: /testdb (to check database connection)
async def test_db(update: Update, context: CallbackContext) -> None:
    try:
        cur.execute("SELECT 1;")
        result = cur.fetchone()
        if result:
            await update.message.reply_text("Database connection is working! 🐾")
        else:
            await update.message.reply_text("Database connection test failed. 🐶")
    except Exception as e:
        await update.message.reply_text(f"Database connection error: {e} 🐕")

# Command: /whopays
async def who_pays(update: Update, context: CallbackContext) -> None:
    users = load_all_users()
    if len(users) < 2:
        await update.message.reply_text('Not enough players to determine who pays. 🐶')
        return

    user1, user2 = users[:2]  # Ensure only the first two users are considered
    if user1[2] < user2[2]:
        await update.message.reply_text(f'Woof! 🐶 {user1[1]} has fewer points ({user1[2]}) and has to pay! 🐾')
    elif user2[2] < user1[2]:
        await update.message.reply_text(f'Woof! 🐶 {user2[1]} has fewer points ({user2[2]}) and has to pay! 🐾')
    else:
        await update.message.reply_text(f'It’s a tie! Both {user1[1]} and {user2[1]} have the same points ({user1[2]}). You both split the bill! 🐕')

# Command: /forfeit
async def forfeit(update: Update, context: CallbackContext) -> None:
    users = load_all_users()
    if len(users) < 2:
        await update.message.reply_text('Not enough players to determine forfeit status. 🐶')
        return

    user1, user2 = users[:2]  # Ensure only the first two users are considered
    point_difference = abs(user1[2] - user2[2])
    if point_difference >= 14:
        if user1[2] < user2[2]:
            await update.message.reply_text(f'Woof! 🐶 {user1[1]} owes a trip to the next vacation place! 🏝️🐾')
        else:
            await update.message.reply_text(f'Woof! 🐶 {user2[1]} owes a trip to the next vacation place! 🏝️🐾')
    else:
        await update.message.reply_text('Keep up the good work! Good sleep leads to good productivity. 🐾')

# Command: /timenow
async def time_now(update: Update, context: CallbackContext) -> None:
    now_utc = datetime.now(pytz.utc)
    local_tz = pytz.timezone('Asia/Singapore')
    now_local = now_utc.astimezone(local_tz)
    await update.message.reply_text(f'The current local time is: {now_local.strftime("%Y-%m-%d %H:%M:%S %Z%z")} 🕰️')

# Command: /help
async def help(update: Update, context: CallbackContext) -> None:
    help_message = (
        "🐶 Woof! Here are the commands you can use: 🐾\n\n"
        "/start - Start the bot\n"
        "/createuser - Register as a new user\n"
        "/leaderboard - Show the leaderboard\n"
        "/whopays - Determine who has to pay based on points\n"
        "/forfeit - Check if a trip is owed based on points difference\n"
        "/timenow - Check the current local time\n"
        "/help - Show this help message\n"
    )
    await update.message.reply_text(help_message)

# Main function to run the bot
def main() -> None:
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("createuser", create_user))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("getchatid", get_chat_id))  # Remove this line after getting the chat ID
    app.add_handler(CommandHandler("testdb", test_db))
    app.add_handler(CommandHandler("whopays", who_pays))
    app.add_handler(CommandHandler("forfeit", forfeit))
    app.add_handler(CommandHandler("timenow", time_now))
    app.add_handler(CommandHandler("help", help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_wake_up))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_louie_message))

    logger.info("Application started and handlers are set.")
    app.run_polling()

if __name__ == '__main__':
    main()