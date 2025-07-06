# main.py
import logging
import os
import json
import random

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.executor import start_webhook
from fastapi import FastAPI, Request

API_TOKEN = os.getenv("API_TOKEN")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")
WEBHOOK_PATH = f"/webhook/{API_TOKEN}"
WEBHOOK_URL = f"{RENDER_EXTERNAL_URL}{WEBHOOK_PATH}"

ADMIN_ID = 1899194677
RUXSAT_ETILGANLAR = [ADMIN_ID]

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
Bot.set_current(bot)
dp = Dispatcher(bot, storage=MemoryStorage())
app = FastAPI()

TESKARI_FILE = "teskari_tezlik_savollar.json"
SCORE_FILE = "user_scores.json"
STATE_FILE = "user_states.json"

# Foydali funksiyalar
def load_json(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def normalize_answer(text):
    return text.lower().strip()

# Yangi savol yuborish
async def send_new_question(chat_id):
    questions = load_json(TESKARI_FILE)
    if not questions:
        await bot.send_message(chat_id, "❌ Savollar mavjud emas.")
        return

    question = random.choice(questions)
    state = {
        "current": question,
        "answered_by": None,
        "chat_id": chat_id
    }
    save_json(STATE_FILE, state)

    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("📖 To‘g‘ri javob", callback_data="javob"))
    await bot.send_message(chat_id, f"🧠 Savol: {question['savol']}", reply_markup=kb)

# /boshla buyrug‘i
@dp.message_handler(commands=["boshla"])
async def boshla(message: types.Message):
    await send_new_question(message.chat.id)

# /ball buyrug‘i
@dp.message_handler(commands=["ball"])
async def show_score(message: types.Message):
    scores = load_json(SCORE_FILE)
    user_score = scores.get(str(message.from_user.id), 0)
    await message.answer(f"📊 Sizning balingiz: {user_score}")

# /add buyrug‘i
@dp.message_handler(commands=["add"])
async def add_question(message: types.Message):
    if message.from_user.id not in RUXSAT_ETILGANLAR:
        return await message.reply("⛔ Sizda ruxsat yo‘q.")
    text = message.text[4:].strip()
    if "||" not in text:
        return await message.reply("❗ Format: /add savol || javob")
    savol, javob = map(str.strip, text.split("||", 1))
    if not savol or not javob:
        return await message.reply("❗ Bo‘sh qiymatlar bo‘lishi mumkin emas.")
    questions = load_json(TESKARI_FILE)
    questions.append({"savol": savol, "javob": javob})
    save_json(TESKARI_FILE, questions)
    await message.reply("✅ Savol qo‘shildi.")

# To‘g‘ri javob tugmasi
@dp.callback_query_handler(lambda c: c.data == "javob")
async def show_answer(callback_query: types.CallbackQuery):
    state = load_json(STATE_FILE)
    if "current" in state:
        await bot.send_message(callback_query.message.chat.id, f"✅ Javob: {state['current']['javob']}")
    else:
        await bot.send_message(callback_query.message.chat.id, "❌ Savol topilmadi.")
    await callback_query.answer()

# Foydalanuvchi javobini tekshirish
@dp.message_handler()
async def check_answer(message: types.Message):
    print("✅ Javob tekshirilmoqda:", message.text)
    logging.info(f"Foydalanuvchidan keldi: {message.text}")

    state = load_json(STATE_FILE)
    if not state or "current" not in state:
        return
    if state.get("answered_by"):
        return

    correct = normalize_answer(state["current"]["javob"])
    user_answer = normalize_answer(message.text)

    if user_answer == correct:
        state["answered_by"] = str(message.from_user.id)
        save_json(STATE_FILE, state)

        scores = load_json(SCORE_FILE)
        uid = str(message.from_user.id)
        scores[uid] = scores.get(uid, 0) + 1
        save_json(SCORE_FILE, scores)

        # Reytingni tuzish
        top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:10]
        reyting = "\n".join([
            f"{i+1}. {await bot.get_chat(int(uid)).first_name} - {score} ball"
            for i, (uid, score) in enumerate(top)
        ])

        await message.answer(
            f"✅ To‘g‘ri javob: {state['current']['javob']}\n🎉 {message.from_user.full_name} 1 ball oldi!\n\n🏆 Reyting:\n{reyting}"
        )
        await send_new_question(state["chat_id"])

# Webhook sozlash
@app.on_event("startup")
async def on_startup():
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"🔗 Webhook o‘rnatildi: {WEBHOOK_URL}")

@app.post(WEBHOOK_PATH)
async def process_webhook(request: Request):
    data = await request.body()
    update = types.Update(**json.loads(data))
    await dp.process_update(update)
    return {"status": "ok"}
