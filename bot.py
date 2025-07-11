from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.enums import ChatType, ContentType
from aiogram.types import ChatPermissions
from datetime import datetime, timedelta
from config import BOT_TOKEN, GROUP_ID
import database

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

def get_daily_amount(coins):
    return 10 + coins // 100

@dp.message(F.chat.id == GROUP_ID)
async def handle_messages(message: types.Message):
    user_id = message.from_user.id
    database.add_user(user_id)
    coins, last_claim = database.get_user(user_id)

    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    if last_claim != today_str:
        daily_amount = get_daily_amount(coins)
        database.update_coins(user_id, daily_amount)
        database.set_last_claim(user_id, today_str)
        await message.reply(f"✅ Daily claim: +{daily_amount} coins! Your balance: {coins + daily_amount}")

    if coins == 0 and message.content_type in [ContentType.STICKER, ContentType.PHOTO, ContentType.VIDEO, ContentType.ANIMATION]:
        await message.delete()

@dp.message(Command("balance"))
async def balance(message: types.Message):
    user_id = message.from_user.id
    database.add_user(user_id)
    coins, _ = database.get_user(user_id)
    await message.reply(f"💰 Your balance: {coins} coins")

@dp.message(Command("send"))
async def send_coins(message: types.Message):
    args = message.text.split()
    if len(args) != 3:
        await message.reply("Usage: /send @username amount")
        return

    target_username = args[1].lstrip("@")
    amount = int(args[2])

    user_id = message.from_user.id
    database.add_user(user_id)
    coins, _ = database.get_user(user_id)

    if amount <= 0 or coins < amount:
        await message.reply("Not enough coins.")
        return

    try:
        target_user = await bot.get_chat_member(GROUP_ID, target_username)
        target_user_id = target_user.user.id
    except:
        await message.reply("User not found in group.")
        return

    database.update_coins(user_id, -amount)
    database.add_user(target_user_id)
    database.update_coins(target_user_id, amount)

    await message.reply(f"✅ Sent {amount} coins to @{target_username}.")

@dp.message(Command("sit"))
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
        target_user = await bot.get_chat_member(GROUP_ID, target_username)
        target_user_id = target_user.user.id
    except:
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

    await bot.restrict_chat_member(
        GROUP_ID,
        target_user_id,
        permissions=ChatPermissions(can_send_messages=False),
        until_date=datetime.utcnow() + timedelta(minutes=5)
    )

    await message.reply(f"🍑 You sat on @{target_username}! Muted for 5 minutes.")

if __name__ == "__main__":
    dp.run_polling(bot)
