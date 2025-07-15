from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.enums import ChatType, ContentType
from aiogram.types import ChatPermissions
from aiogram.utils.markdown import hbold
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import os
import database

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

def get_daily_amount(coins):
    return 10 + coins // 100

# ✅ Allow commands in group
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
        members = await bot.get_chat_administrators(GROUP_ID)
        target_user = None
        for m in members:
            if m.user.username and m.user.username.lower() == target_username.lower():
                target_user = m.user
                break
        if target_user is None:
            raise Exception("Not found")
        target_user_id = target_user.id
    except Exception:
        await message.reply("User not found in group.")
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
            raise Exception("Not found")
        target_user_id = target_user.id
    except Exception:
        await message.reply("User not found in group.")
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
    top_users = database.get_top_users(limit=10)  # You may add `limit` support if needed
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

# ✅ Always register user and give daily claim on any message in group
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

if __name__ == "__main__":
    dp.run_polling(bot)
