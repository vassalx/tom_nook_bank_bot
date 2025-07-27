import os
import json
import logging # NEW: Import logging module
import sys # NEW: Import sys for logging

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.enums import ChatType, ContentType
from aiogram.types import ChatPermissions
from aiogram.utils.markdown import hbold
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

# NEW IMPORTS for webhook server
from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler

# Load environment variables from .env file (for local development)
load_dotenv()

# Assuming your database.py handles external, persistent storage
import database

# --- CONFIGURATION (Environment Variables) ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))  # Ensure this is an integer

# Webhook configuration for Render
WEB_SERVER_HOST = "0.0.0.0"  # Listen on all available interfaces
# Render provides the PORT environment variable
WEB_SERVER_PORT = int(os.getenv("PORT", 8080))

# This is the path Telegram will send updates to. Keep it secret!
# Using BOT_TOKEN makes it unique, but a truly random string is more secure.
# For this fix, we'll keep your original logic.
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"

# Build the full webhook URL. RENDER_EXTERNAL_URL is provided by Render.
WEBHOOK_URL = os.getenv("RENDER_EXTERNAL_URL") + WEBHOOK_PATH

# --- Logging Setup ---
# Configure logging to output to stdout, which Render captures
logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Bot and Dispatcher Initialization ---
# Initialize bot outside the function for "warm" instances
bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# --- Your Existing Bot Logic (Handlers) ---
def get_daily_amount(coins):
    return 10 + coins // 100

@dp.message(Command("balance"), F.chat.id == GROUP_ID)
async def balance(message: types.Message):
    user_id = message.from_user.id
    database.add_user(user_id)
    coins, _ = database.get_user(user_id)
    logger.info(f"User {user_id} requested balance: {coins}") # Added log
    await message.reply(f"💰 Your balance: {coins} coins")

@dp.message(Command("send"), F.chat.id == GROUP_ID)
async def send_coins(message: types.Message):
    args = message.text.split()
    if len(args) != 3:
        await message.reply("Usage: /send @username amount")
        return

    target_username = args[1].lstrip("@")
    try:
        amount = int(args[2])
    except ValueError:
        await message.reply("Amount must be a number.")
        return

    user_id = message.from_user.id
    database.add_user(user_id)
    coins, _ = database.get_user(user_id)

    if amount <= 0 or coins < amount:
        await message.reply("Not enough coins.")
        return

    try:
        members = await bot.get_chat_administrators(GROUP_ID)
        target_user = None
        for m in members:
            if m.user.username and m.user.username.lower() == target_username.lower():
                target_user = m.user
                break
        if target_user is None:
            raise Exception("User not found or not an admin in the group.")
        target_user_id = target_user.id
    except Exception as e:
        logger.error(f"Error finding target user {target_username}: {e}") # Added log
        await message.reply(f"User not found in group or error: {e}")
        return

    database.update_coins(user_id, -amount)
    database.add_user(target_user_id)
    database.update_coins(target_user_id, amount)
    logger.info(f"User {user_id} sent {amount} coins to {target_user_id}") # Added log
    await message.reply(f"✅ Sent {amount} coins to @{target_username}.")

@dp.message(Command("sit"), F.chat.id == GROUP_ID)
async def sit_on_user(message: types.Message):
    args = message.text.split()
    if len(args) != 2:
        await message.reply("Usage: /sit @username")
        return

    target_username = args[1].lstrip("@")
    user_id = message.from_user.id
    database.add_user(user_id)
    user_coins, _ = database.get_user(user_id)

    top_users = database.get_top_users()
    top_20_percent = top_users[:max(1, len(top_users)//5)]
    immune_ids = [u[0] for u in top_20_percent]

    try:
        members = await bot.get_chat_administrators(GROUP_ID)
        target_user = None
        for m in members:
            if m.user.username and m.user.username.lower() == target_username.lower():
                target_user = m.user
                break
        if target_user is None:
            raise Exception("User not found or not an admin in the group.")
        target_user_id = target_user.id
    except Exception as e:
        logger.error(f"Error finding target user {target_username}: {e}") # Added log
        await message.reply(f"User not found in group or error: {e}")
        return

    if target_user_id in immune_ids:
        await message.reply("🚫 This user is in the top 20% and is immune.")
        return

    database.add_user(target_user_id)
    target_coins, _ = database.get_user(target_user_id)

    if user_coins <= target_coins:
        await message.reply("You need to have more coins than the user to sit on them.")
        return

    try:
        await bot.restrict_chat_member(
            GROUP_ID,
            target_user_id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=datetime.now(timezone.utc) + timedelta(minutes=5)
        )
        logger.info(f"User {user_id} sat on {target_user_id}, muted for 5 mins.") # Added log
        await message.reply(f"🍑 You sat on @{target_username}! Muted for 5 minutes.")
    except Exception as e:
        logger.error(f"Failed to restrict user {target_user_id}: {e}") # Added log
        await message.reply(f"Failed to restrict user: {e}")

@dp.message(Command("leaderboard"), F.chat.id == GROUP_ID)
async def leaderboard(message: types.Message):
    top_users = database.get_top_users(limit=10)
    if not top_users:
        await message.reply("No one has any coins yet. Get chatting to earn some!")
        return

    text = "🏆 " + hbold("Tom Nook's Leaderboard") + " 🏆\n\n"
    for idx, (user_id, coins) in enumerate(top_users, 1):
        try:
            member = await bot.get_chat_member(GROUP_ID, user_id)
            name = member.user.first_name
            if member.user.username:
                name = f"@{member.user.username}"
        except Exception:
            name = f"[unknown user {user_id}]"
        text += f"{idx}. {name} — {coins} coins\n"
    logger.info("Leaderboard requested and sent.") # Added log
    await message.reply(text, parse_mode="HTML")

@dp.message(F.chat.id == GROUP_ID)
async def handle_messages(message: types.Message):
    user_id = message.from_user.id
    database.add_user(user_id)
    coins, last_claim = database.get_user(user_id)

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if last_claim != today_str:
        daily_amount = get_daily_amount(coins)
        database.update_coins(user_id, daily_amount)
        database.set_last_claim(user_id, today_str)
        logger.info(f"User {user_id} claimed daily coins: +{daily_amount}") # Added log
        await message.reply(f"✅ Daily claim: +{daily_amount} coins! Your balance: {coins + daily_amount}")

    if coins == 0 and message.content_type in [ContentType.STICKER, ContentType.PHOTO, ContentType.VIDEO, ContentType.ANIMATION]:
        await message.delete()
        logger.info(f"Deleted content from user {user_id} due to 0 coins.") # Added log

    if message.content_type == ContentType.STICKER:
        if coins > 0:
            database.update_coins(user_id, -1)
            coins -= 1
            logger.info(f"User {user_id} sent sticker, -1 coin. Balance: {coins}") # Added log
            await message.reply(f"😼 Sent a sticker, -1 coin! Your balance: {coins}")
        else:
            await message.delete()
            logger.info(f"Deleted sticker from user {user_id} due to 0 coins.") # Added log

# --- NEW: Webhook Setup for Render ---
async def on_startup(dispatcher: Dispatcher, bot: Bot):
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await bot.set_webhook(WEBHOOK_URL)
        logger.info(f"Webhook set to: {WEBHOOK_URL}")
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")

async def on_shutdown(dispatcher: Dispatcher, bot: Bot):
    """
    This function will be called when the bot is shutting down.
    It's good practice to delete the webhook from Telegram.
    """
    try:
        await bot.delete_webhook()
        logger.info("Webhook deleted.") # Changed print to logger.info
    except Exception as e:
        logger.error(f"Failed to delete webhook: {e}") # Log any errors

    # Close database connections if your database.py has a global connection pool
    # Or ensure connections are closed per request.

import asyncio

if __name__ == "__main__":
    logger.info("Bot application starting...")

    app = web.Application()

    # Register webhook handler
    SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=BOT_TOKEN).register(app, path=WEBHOOK_PATH)

    async def start():
        # --- Explicitly call your startup logic here ---
        await on_startup(dp, bot)

        # Run the web server
        logger.info(f"Starting web server on {WEB_SERVER_HOST}:{WEB_SERVER_PORT}")
        logger.info(f"Expected webhook URL: {WEBHOOK_URL}")
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host=WEB_SERVER_HOST, port=WEB_SERVER_PORT)
        await site.start()

        # Keep the app alive
        while True:
            await asyncio.sleep(3600)

    asyncio.run(start())
