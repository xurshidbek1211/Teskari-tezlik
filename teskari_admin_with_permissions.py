
import logging
from aiogram import Bot, Dispatcher, executor, types
import json
import os

API_TOKEN = 'YOUR_BOT_TOKEN_HERE'
ADMIN_ID = 1899194677

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

QUESTIONS_FILE = 'teskari_tezlik_savollar.json'
ALLOWED_USERS_FILE = 'allowed_users.json'

def load_questions():
    if os.path.exists(QUESTIONS_FILE):
        with open(QUESTIONS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_questions(questions):
    with open(QUESTIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)

def load_allowed_users():
    if os.path.exists(ALLOWED_USERS_FILE):
        with open(ALLOWED_USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_allowed_users(users):
    with open(ALLOWED_USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=2)

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.reply("Salom! /teskari bilan boshlash mumkin. Admin esa /add_teskari orqali savol qo‘shadi.")

@dp.message_handler(commands=['add_teskari'])
async def add_teskari_command(message: types.Message):
    user_id = message.from_user.id
    allowed_users = load_allowed_users()
    if user_id == ADMIN_ID or user_id in allowed_users:
        await message.reply("Yangi savolni 'javob | savol' ko‘rinishida yuboring.")
    else:
        await message.reply("❌ Sizda bu amalni bajarish uchun ruxsat yo‘q.")

@dp.message_handler(commands=['allow'])
async def allow_user(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("❌ Siz bu buyruqdan foydalana olmaysiz.")
        return
    try:
        parts = message.text.strip().split()
        if len(parts) != 2:
            await message.reply("Iltimos, foydalanuvchi ID sini quyidagicha yuboring: /allow 123456789")
            return
        new_user_id = int(parts[1])
        allowed_users = load_allowed_users()
        if new_user_id not in allowed_users:
            allowed_users.append(new_user_id)
            save_allowed_users(allowed_users)
            await message.reply(f"✅ {new_user_id} ID ga ruxsat berildi!")
        else:
            await message.reply("⚠️ Bu foydalanuvchi allaqachon ruxsatlangan.")
    except Exception as e:
        await message.reply(f"Xatolik: {e}")

@dp.message_handler(lambda message: '|' in message.text)
async def add_question(message: types.Message):
    user_id = message.from_user.id
    allowed_users = load_allowed_users()
    if user_id != ADMIN_ID and user_id not in allowed_users:
        return  # hech qanday javob bermaydi
    try:
        javob, savol = map(str.strip, message.text.split('|', 1))
        questions = load_questions()
        questions.append({'savol': savol, 'javob': javob})
        save_questions(questions)
        await message.reply("✅ Yangi savol qo‘shildi!")
    except Exception as e:
        await message.reply(f"Xatolik: {e}")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
