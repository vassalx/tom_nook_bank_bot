import os
import json
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.enums import ChatType, ContentType
from aiogram.types import ChatPermissions
from aiogram.utils.markdown import hbold
from datetime import datetime, timedelta, timezone
import asyncio # <--- NEW IMPORT for webhook server

# Assuming your database.py handles external, persistent storage
import database 

# --- CONFIGURATION (Environment Variables) ---
# These will be passed to the Cloud Function during deployment (e.g., via --set-env-vars)
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID")) # Ensure this is an integer

# --- Bot and Dispatcher Initialization ---
# Initialize bot outside the function for "warm" instances
bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# --- Your Existing Bot Logic (Handlers) ---
# Keep all your @dp.message(...) decorators as they are.
# These will be registered with the dispatcher.

def get_daily_amount(coins):
    return 10 + coins // 100

@dp.message(Command("balance"), F.chat.id == GROUP_ID)
async def balance(message: types.Message):
    user_id = message.from_user.id
    database.add_user(user_id)
    coins, _ = database.get_user(user_id)
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

    # Find user by username
    try:
        # Note: get_chat_administrators only gets admins. 
        # If the target user is not an admin, this will fail.
        # Consider alternatives if you need to find non-admin users.
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
        await message.reply(f"User not found in group or error: {e}")
        return

    database.update_coins(user_id, -amount)
    database.add_user(target_user_id)
    database.update_coins(target_user_id, amount)

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

    # Find user by username
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
        await message.reply(f"🍑 You sat on @{target_username}! Muted for 5 minutes.")
    except Exception as e:
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
        await message.reply(f"✅ Daily claim: +{daily_amount} coins! Your balance: {coins + daily_amount}")

    if coins == 0 and message.content_type in [ContentType.STICKER, ContentType.PHOTO, ContentType.VIDEO, ContentType.ANIMATION]:
        await message.delete()

    if message.content_type == ContentType.STICKER:
        if coins > 0:
            database.update_coins(user_id, -1)
            coins -= 1
            await message.reply(f"😼 Sent a sticker, -1 coin! Your balance: {coins}")
        else:
            await message.delete()

# --- NEW: Cloud Function Entry Point ---
async def process_telegram_update(request):
    """
    Cloud Function entry point for Telegram webhooks.
    This function will be called by Google Cloud Functions when Telegram sends an update.
    """
    if request.method == "POST":
        # Get the JSON data from the request body
        request_json = await request.get_json(silent=True)
        if not request_json:
            return 'OK', 200 # No JSON body, return OK to avoid Telegram re-sending

        try:
            # Process the update using aiogram's dispatcher
            # This is the core of webhook handling with aiogram
            await dp.feed_raw_update(bot, request_json)
            return 'OK', 200 # Important: Return 200 OK as soon as possible
        except Exception as e:
            # Log any errors for debugging in Cloud Logging
            print(f"Error processing update: {e}")
            return f'Error: {e}', 500
    else:
        # Handle GET requests (e.g., for initial function URL testing)
        return 'This is a Telegram bot webhook endpoint. Please send POST requests with updates.', 200

# --- The 'main' function for Google Cloud Functions ---
# This is the function name you'll provide to `--entry-point` during deployment.
# It acts as a wrapper to allow asynchronous handling.
def webhook(request):
    """
    Wrapper for the async process_telegram_update function.
    Google Cloud Functions expects a synchronous function for Python HTTP triggers,
    but we can run an async function inside it using asyncio.run.
    """
    return asyncio.run(process_telegram_update(request))