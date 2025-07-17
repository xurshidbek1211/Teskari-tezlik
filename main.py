import logging
import os
import json
import random
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from fastapi import FastAPI, Request
from aiogram.utils.executor import start_webhook

API_TOKEN = os.getenv("API_TOKEN")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")

WEBHOOK_PATH = f"/webhook/{API_TOKEN}"
WEBHOOK_URL = f"{RENDER_EXTERNAL_URL}{WEBHOOK_PATH}"

ADMIN_ID = 1899194677
RUXSAT_ETILGANLAR = [ADMIN_ID]

bot = Bot(token=API_TOKEN)
Bot.set_current(bot)
dp = Dispatcher(bot, storage=MemoryStorage())
app = FastAPI()

logging.basicConfig(level=logging.INFO)

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

async def send_new_question(chat_id):
    questions = load_json(TESKARI_FILE)
    if not questions:
        await bot.send_message(chat_id, "❌ Savollar mavjud emas.")
        return
    question = random.choice(questions)
    states = load_json(STATE_FILE)
    states[str(chat_id)] = {
        "current": question,
        "answered_by": None,
        "chat_id": chat_id
    }
    save_json(STATE_FILE, states)
    await bot.send_message(chat_id, f"🔄 Toping: {question['savol']}")

@dp.message_handler(commands=["boshla"])
async def boshla(message: types.Message):
    await send_new_question(message.chat.id)

@dp.message_handler(commands=["add"])
async def add_question(message: types.Message):
    if message.from_user.id not in RUXSAT_ETILGANLAR:
        await message.reply("❌ Sizda savol qo‘shish huquqi yo‘q.")
        return
    text = message.text[4:].strip()
    if "||" not in text:
        await message.reply("❗️ Format: /add savol || javob")
        return
    savol, javob = map(str.strip, text.split("||", maxsplit=1))
    if not savol or not javob:
        await message.reply("❗️ Savol va javob bo‘sh bo‘lishi mumkin emas.")
        return
    questions = load_json(TESKARI_FILE)
    questions.append({"savol": savol, "javob": javob})
    save_json(TESKARI_FILE, questions)
    await message.reply("✅ Savol qo‘shildi!")

@dp.message_handler(commands=["ball"])
async def show_score(message: types.Message):
    scores = load_json(SCORE_FILE)
    chat_id = str(message.chat.id)
    user_id = str(message.from_user.id)
    chat_scores = scores.get(chat_id, {})
    user_score = chat_scores.get(user_id, 0)
    await message.answer(f"📊 Sizning guruhdagi umumiy balingiz: {user_score}")

@dp.message_handler()
async def check_answer(message: types.Message):
    states = load_json(STATE_FILE)
    chat_id = str(message.chat.id)
    user_id = str(message.from_user.id)

    if chat_id not in states:
        return
    state = states[chat_id]

    if "current" not in state or state.get("answered_by") is not None:
        return

    correct = state["current"]["javob"]
    user_answer = message.text.strip()

    if user_answer == correct:
        state["answered_by"] = user_id
        states[chat_id] = state
        save_json(STATE_FILE, states)

        scores = load_json(SCORE_FILE)
        if chat_id not in scores:
            scores[chat_id] = {}
        scores[chat_id][user_id] = scores[chat_id].get(user_id, 0) + 1
        save_json(SCORE_FILE, scores)

        top = sorted(scores[chat_id].items(), key=lambda x: x[1], reverse=True)[:10]
        reyting = ""
        for i, (uid, ball) in enumerate(top):
            try:
                user = await bot.get_chat(int(uid))
                name = user.first_name
            except:
                name = "👤 Nomaʼlum"
            reyting += f"{i+1}. {name} - {ball} ball\n"

        await message.answer(
            f"🎯 To‘g‘ri javob: {state['current']['javob']}\n"
            f"🎉 {message.from_user.full_name} 1 ball oldi!\n\n"
            f"🏆 Guruhdagi eng yaxshi 10 ta foydalanuvchi:\n{reyting}"
        )

        await send_new_question(message.chat.id)

# ✅ Har kuni soat 00:00 da g‘olibni aniqlab tabriklash
async def daily_congratulations():
    while True:
        now = datetime.now()
        tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        wait_seconds = (tomorrow - now).total_seconds()
        await asyncio.sleep(wait_seconds)

        scores = load_json(SCORE_FILE)
        for chat_id, user_scores in scores.items():
            if not user_scores:
                continue
            top_user_id = max(user_scores, key=user_scores.get)
            top_score = user_scores[top_user_id]

            try:
                user = await bot.get_chat(int(top_user_id))
                name = user.first_name
            except:
                name = "👤 Nomaʼlum"

            message = (
                f"🎉 Kun g‘olibi: {name}!\n"
                f"🏆 Ballar: {top_score}\n"
                f"🥳 Tabriklaymiz! Ajoyib natija!\n\n"
                f"🕛 Yangi kun boshlandi – bugun yana bellashamiz!"
            )
            await bot.send_message(int(chat_id), message)

@app.on_event("startup")
async def on_startup():
    await bot.set_webhook(WEBHOOK_URL)
    asyncio.create_task(daily_congratulations())
    logging.info(f"✅ Webhook o‘rnatildi: {WEBHOOK_URL}")

@app.post(WEBHOOK_PATH)
async def process_webhook(request: Request):
    data = await request.body()
    update = types.Update(**json.loads(data))
    await dp.process_update(update)
    return {"status": "ok"}

@app.get("/")
async def root():
    return {"status": "Bot tirik va ishlayapti ✅"}
