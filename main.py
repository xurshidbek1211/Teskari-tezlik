import json
import logging
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message
import random

# --- SOZLAMALAR ---
BOT_TOKEN = "7265238026:AAE4n-lQd--ViqQgyFhB51XnURFcRdM8Cp8"
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"https://turli-savollarbot.onrender.com{WEBHOOK_PATH}"  # Render URL ni o‘zingiznikiga moslang
SCORE_FILE = "scores.json"
QUESTIONS_FILE = "teskari_tezlik_savollar.json"

# --- BOT VA FASTAPI ---
bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher(storage=MemoryStorage())
app = FastAPI()

# --- YORDAMCHI FUNKSIYALAR ---
def load_json(filename):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_random_question():
    questions = load_json(QUESTIONS_FILE)
    return random.choice(questions)

# --- GLOBAL HOLAT SAQLASH ---
state = {}

# --- /boshla ---
@dp.message(commands=["boshla"])
async def cmd_start(message: Message, state_fsm: FSMContext):
    state["chat_id"] = message.chat.id
    state["current"] = get_random_question()
    await message.answer(f"♻️ So‘z: <b>{state['current']['savol']}</b>")

# --- JAVOBNI QABUL QILISH ---
@dp.message()
async def handle_answer(message: Message, state_fsm: FSMContext):
    if "current" not in state:
        return

    if message.text.lower().strip() == state["current"]["javob"].lower():
        scores = load_json(SCORE_FILE)
        user_id = str(message.from_user.id)
        chat_id = str(message.chat.id)

        if chat_id not in scores:
            scores[chat_id] = {}
        scores[chat_id][user_id] = scores[chat_id].get(user_id, 0) + 1
        save_json(SCORE_FILE, scores)

        # Reyting tayyorlash
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
            f"🎉 {message.from_user.full_name} 1 ball oldi!\n\n"
            f"🏆 Guruh reytingi:\n{reyting}"
        )

        state["current"] = get_random_question()
        await message.answer(f"♻️ Yangi so‘z: <b>{state['current']['savol']}</b>")

# --- WEBHOOK STARTUP ---
@app.on_event("startup")
async def on_startup():
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"✅ Webhook o‘rnatildi: {WEBHOOK_URL}")

# --- WEBHOOK QABUL QILISH ---
@app.post(WEBHOOK_PATH)
async def process_webhook(request: Request):
    data = await request.body()
    update = types.Update(**json.loads(data))
    await dp.process_update(update)
    return {"status": "ok"}
