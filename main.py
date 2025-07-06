import logging
import os
import json
import random

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from fastapi import FastAPI, Request
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.webhook import get_new_configured_app

# Token va URL
API_TOKEN = os.getenv("API_TOKEN")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")
WEBHOOK_PATH = f"/webhook/{API_TOKEN}"
WEBHOOK_URL = f"{RENDER_EXTERNAL_URL}{WEBHOOK_PATH}"

# Bot, Dispatcher, FastAPI ilovasi
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
app = FastAPI()

# Log sozlamasi
logging.basicConfig(level=logging.INFO)

# Fayllar
TESKARI_FILE = 'teskari_tezlik_savollar.json'
SCORE_FILE = 'user_scores.json'
USER_STATE_FILE = 'user_states.json'

# JSON fayl o‘qish/yozish
def load_json(filename):
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_json(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Start komandasi
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🌀 Teskari tezlik", callback_data="teskari"))
    await message.answer("Qaysi kategoriyani tanlaysiz?", reply_markup=kb)

# Teskari kategoriyasi
@dp.callback_query_handler(lambda c: c.data == "teskari")
async def send_teskari(callback_query: types.CallbackQuery):
    questions = load_json(TESKARI_FILE)
    if questions:
        question = random.choice(questions)
        user_state = load_json(USER_STATE_FILE)
        user_state[str(callback_query.from_user.id)] = question
        save_json(USER_STATE_FILE, user_state)

        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📖 To‘g‘ri javob", callback_data="javob"))
        await bot.send_message(callback_query.from_user.id, f"Toping: {question['savol']}", reply_markup=kb)

# To‘g‘ri javobni ko‘rsatish
@dp.callback_query_handler(lambda c: c.data == "javob")
async def show_answer(callback_query: types.CallbackQuery):
    user_state = load_json(USER_STATE_FILE)
    user_id = str(callback_query.from_user.id)
    if user_id in user_state:
        await bot.send_message(callback_query.from_user.id, f"✅ To‘g‘ri javob: {user_state[user_id]['javob']}")

# Ball ko‘rsatish
@dp.message_handler(commands=['ball'])
async def show_ball(message: types.Message):
    scores = load_json(SCORE_FILE)
    score = scores.get(str(message.from_user.id), 0)
    await message.reply(f"📊 Sizning umumiy balingiz: {score}")

# Javobni tekshirish
@dp.message_handler()
async def javobni_tekshir(message: types.Message):
    user_id = str(message.from_user.id)
    user_state = load_json(USER_STATE_FILE)
    if user_id in user_state:
        togri_javob = user_state[user_id]['javob'].lower()
        if message.text.strip().lower() == togri_javob:
            scores = load_json(SCORE_FILE)
            scores[user_id] = scores.get(user_id, 0) + 1
            save_json(SCORE_FILE, scores)
            del user_state[user_id]
            save_json(USER_STATE_FILE, user_state)
            await message.reply("✅ To‘g‘ri! Sizga 1 ball qo‘shildi.")
        else:
            await message.reply("❌ Noto‘g‘ri. Yana urinib ko‘ring.")

# Webhook sozlash
@app.on_event("startup")
async def on_startup():
    await bot.set_webhook(WEBHOOK_URL)

# Webhook orqali kelgan yangilanishlarni qabul qilish
@app.post(WEBHOOK_PATH)
async def process_webhook(request: Request):
    data = await request.body()
    update = types.Update(**json.loads(data))
    await dp.process_update(update)
    return {"status": "ok"}
