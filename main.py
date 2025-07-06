import logging
import os
import json
import random

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from fastapi import FastAPI, Request
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# Token va URL
API_TOKEN = os.getenv("API_TOKEN")
ADMIN_ID = 1899194677  # Sizning admin IDingiz
RUXSAT_ETILGANLAR = [ADMIN_ID]  # Admin va savol qo‘shishga ruxsat berilganlar ro‘yxati

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

# Savollarni random olish funksiyasi
def get_random_question():
    questions = load_json(TESKARI_FILE)
    if questions:
        return random.choice(questions)
    return None

# Inline klaviatura yaratish (savol uchun)
def get_answer_kb():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📖 To‘g‘ri javobni ko‘rsatish", callback_data="javob"))
    return kb

# Inline klaviatura bosh sahifa uchun
def get_main_kb():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🌀 Teskari tezlik", callback_data="teskari"))
    return kb

# /start komandasi
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer("Salom! Qaysi kategoriyani tanlaysiz?", reply_markup=get_main_kb())

# Kategoriya tanlash callback
@dp.callback_query_handler(lambda c: c.data == "teskari")
async def send_teskari(callback_query: types.CallbackQuery):
    question = get_random_question()
    if question is None:
        await bot.send_message(callback_query.from_user.id, "Savollar hali yuklanmagan yoki mavjud emas.")
        return

    # Foydalanuvchi uchun savolni saqlaymiz
    user_state = load_json(USER_STATE_FILE)
    user_state[str(callback_query.from_user.id)] = question
    save_json(USER_STATE_FILE, user_state)

    await bot.send_message(callback_query.from_user.id, f"Toping: {question['savol']}", reply_markup=get_answer_kb())

# To‘g‘ri javobni ko‘rsatish callback
@dp.callback_query_handler(lambda c: c.data == "javob")
async def show_answer(callback_query: types.CallbackQuery):
    user_state = load_json(USER_STATE_FILE)
    user_id = str(callback_query.from_user.id)
    if user_id in user_state:
        javob = user_state[user_id]['javob']
        await bot.send_message(callback_query.from_user.id, f"✅ To‘g‘ri javob: {javob}")
    else:
        await bot.send_message(callback_query.from_user.id, "Savol topilmadi. Iltimos, yangi savol oling.")

# Ballarni ko‘rsatish komandasi
@dp.message_handler(commands=['ball'])
async def show_ball(message: types.Message):
    scores = load_json(SCORE_FILE)
    score = scores.get(str(message.from_user.id), 0)
    await message.reply(f"📊 Sizning umumiy balingiz: {score}")

# Savolga javobni tekshirish (lichka va guruhda ishlaydi)
@dp.message_handler(content_types=['text'])
async def check_answer(message: types.Message):
    user_id = None

    # Guruh yoki kanalda bo‘lsa
    if message.from_user:
        user_id = str(message.from_user.id)
    else:
        # Agar from_user bo‘lmasa, xabarni hisoblamaymiz
        return

    user_state = load_json(USER_STATE_FILE)

    # Foydalanuvchiga savol berilgan bo‘lsa
    if user_id in user_state:
        togri_javob = user_state[user_id]['javob'].lower()
        foydalanuvchi_javobi = message.text.strip().lower()

        if foydalanuvchi_javobi == togri_javob:
            # Ball qo‘shish
            scores = load_json(SCORE_FILE)
            scores[user_id] = scores.get(user_id, 0) + 1
            save_json(SCORE_FILE, scores)

            # Savolni olib tashlash
            del user_state[user_id]
            save_json(USER_STATE_FILE, user_state)

            # Javob to‘g‘ri ekanini bildirish
            await message.reply("✅ To‘g‘ri! Sizga 1 ball qo‘shildi.")

            # Yangi savol berish
            new_question = get_random_question()
            if new_question:
                user_state[user_id] = new_question
                save_json(USER_STATE_FILE, user_state)
                await message.answer(f"Yangi savol: {new_question['savol']}", reply_markup=get_answer_kb())
            else:
                await message.answer("Savollar tugadi yoki mavjud emas.")
        else:
            await message.reply("❌ Noto‘g‘ri javob. Yana urinib ko‘ring.")

# Admin uchun yangi savol qo‘shish komandasi
@dp.message_handler(commands=['addsavol'])
async def add_question(message: types.Message):
    if message.from_user.id not in RUXSAT_ETILGANLAR:
        await message.reply("Sizda yangi savol qo‘shish huquqi yo‘q.")
        return

    # Format: /addsavol savol|javob
    if '|' not in message.text:
        await message.reply("Iltimos, formatga amal qiling:\n/adsavol savol|javob")
        return

    try:
        _, data = message.text.split(' ', 1)
        savol, javob = data.split('|', 1)
        savol = savol.strip()
        javob = javob.strip()

        questions = load_json(TESKARI_FILE)
        if not isinstance(questions, list):
            questions = []

        questions.append({"savol": savol, "javob": javob})
        save_json(TESKARI_FILE, questions)
        await message.reply("Savol muvaffaqiyatli qo‘shildi!")
    except Exception as e:
        await message.reply("Xatolik yuz berdi. Iltimos formatga amal qiling:\n/adsavol savol|javob")

# Webhook sozlash
@app.on_event("startup")
async def on_startup():
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"Webhook o'rnatildi: {WEBHOOK_URL}")

# Webhook orqali kelgan yangilanishlarni qabul qilish
@app.post(WEBHOOK_PATH)
async def process_webhook(request: Request):
    data = await request.body()
    update = types.Update(**json.loads(data))
    await dp.process_update(update)
    return {"status": "ok"}
