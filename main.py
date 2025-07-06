import logging
import os
import json
import random

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from fastapi import FastAPI, Request
from aiogram.utils.executor import start_webhook

API_TOKEN = os.getenv("API_TOKEN")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")
WEBHOOK_PATH = f"/webhook/{API_TOKEN}"
WEBHOOK_URL = f"{RENDER_EXTERNAL_URL}{WEBHOOK_PATH}"
ADMIN_ID = 1899194677
RUXSAT_ETILGANLAR = [ADMIN_ID]

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
Bot.set_current(bot)  # Muhim: kontekstda bot ni o‘rnatish
dp = Dispatcher(bot, storage=MemoryStorage())
app = FastAPI()

TESKARI_FILE = "teskari_tezlik_savollar.json"
SCORE_FILE = "user_scores.json"
STATE_FILE = "user_states.json"

def load_json(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def normalize_answer(text):
    text = text.lower()
    text = text.replace("ʼ", "'").replace("`", "'").replace("´", "'").replace("‘", "'").replace("’", "'")
    return text.strip()

async def send_new_question(chat_id):
    questions = load_json(TESKARI_FILE)
    if not questions:
        await bot.send_message(chat_id, "Savollar mavjud emas.")
        return

    question = random.choice(questions)
    state = {
        "current": question,
        "answered_by": None,
        "chat_id": chat_id
    }
    save_json(STATE_FILE, state)

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📖 To‘g‘ri javob", callback_data="javob"))
    await bot.send_message(chat_id, f"Toping: {question['savol']}", reply_markup=kb)

@dp.message_handler(commands=["boshla"])
async def boshla(message: types.Message):
    await send_new_question(message.chat.id)

@dp.callback_query_handler(lambda c: c.data == "javob")
async def show_answer(callback_query: types.CallbackQuery):
    state = load_json(STATE_FILE)
    if "current" in state:
        await bot.send_message(callback_query.message.chat.id, f"✅ To‘g‘ri javob: {state['current']['javob']}")
    else:
        await bot.send_message(callback_query.message.chat.id, "Savol topilmadi.")
    await callback_query.answer()

@dp.message_handler(commands=["ball"])
async def show_score(message: types.Message):
    scores = load_json(SCORE_FILE)
    user_score = scores.get(str(message.from_user.id), 0)
    await message.answer(f"📊 Sizning umumiy balingiz: {user_score}")

@dp.message_handler(commands=["add"])
async def add_question(message: types.Message):
    if message.from_user.id not in RUXSAT_ETILGANLAR:
        await message.reply("Sizda savol qo‘shish huquqi yo‘q.")
        return
    text = message.text[4:].strip()
    if "||" not in text:
        await message.reply("Format: /add savol || javob")
        return
    savol, javob = map(str.strip, text.split("||", maxsplit=1))
    if not savol or not javob:
        await message.reply("Savol va javob bo‘sh bo‘lishi mumkin emas.")
        return
    questions = load_json(TESKARI_FILE)
    questions.append({"savol": savol, "javob": javob})
    save_json(TESKARI_FILE, questions)
    await message.reply("✅ Savol qo‘shildi.")

@dp.message_handler()
async def check_answer(message: types.Message):
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
        user_id = str(message.from_user.id)
        scores[user_id] = scores.get(user_id, 0) + 1
        save_json(SCORE_FILE, scores)

        top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:10]
        reyting = "\n".join(
            [f"{i+1}. {await bot.get_chat(int(uid)).first_name} - {score} ball" for i, (uid, score) in enumerate(top)]
        )

        await message.answer(
            f"✅ To‘g‘ri javob: {state['current']['javob']}\n🎉 {message.from_user.full_name} 1 ball oldi!\n\n📊 Reyting:\n{reyting}"
        )

        await send_new_question(state["chat_id"])

@app.on_event("startup")
async def on_startup():
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"Webhook o‘rnatildi: {WEBHOOK_URL}")

@app.post(WEBHOOK_PATH)
async def process_webhook(request: Request):
    data = await request.body()
    update = types.Update(**json.loads(data))
    await dp.process_update(update)
    return {"status": "ok"}
