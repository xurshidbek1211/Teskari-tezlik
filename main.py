import json
import logging
import os
import random
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage

BOT_TOKEN = os.getenv("BOT_TOKEN")  # yoki bevosita yozing
WEBHOOK_URL = "https://your-app-name.onrender.com/webhook"
WEBHOOK_PATH = "/webhook"

SCORE_FILE = "scores.json"
QUESTION_FILE = "questions.json"

ADMINS = [123456789]  # <-- O‘Z TELEGRAM ID'INGIZNI yozing

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
app = FastAPI()

# JSON funksiyalari
def load_json(filename):
    if not os.path.exists(filename):
        return []
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# Bot holati (savollar)
bot_state = {}

async def send_new_question(chat_id):
    questions = load_json(QUESTION_FILE)
    if not questions:
        await bot.send_message(chat_id, "❌ Hozircha savollar mavjud emas.")
        return

    savol = random.choice(questions)
    bot_state[str(chat_id)] = {"current": savol}
    await bot.send_message(chat_id, f"❓ Savol: {savol['savol']}")

@dp.message_handler(commands=["start", "boshlash"])
async def handle_start(message: types.Message):
    await send_new_question(message.chat.id)

@dp.message_handler(commands=["add"])
async def add_question(message: types.Message):
    if message.from_user.id not in ADMINS:
        await message.reply("⛔ Sizga ruxsat yo‘q.")
        return
    try:
        _, savol, javob = message.text.split(";", 2)
        savollar = load_json(QUESTION_FILE)
        savollar.append({"savol": savol.strip(), "javob": javob.strip()})
        save_json(QUESTION_FILE, savollar)
        await message.reply("✅ Savol muvaffaqiyatli qo‘shildi.")
    except:
        await message.reply("❗ Format: /add savol;javob")

@dp.message_handler(content_types=types.ContentTypes.TEXT)
async def handle_answer(message: types.Message):
    if not message.chat.type.endswith("group"):
        return

    chat_id = str(message.chat.id)
    state = bot_state.get(chat_id)
    if not state or 'current' not in state:
        return

    user_javob = message.text.strip().lower()
    togrisi = state['current']['javob'].strip().lower()

    if user_javob != togrisi:
        return

    scores = load_json(SCORE_FILE)
    if chat_id not in scores:
        scores[chat_id] = {}

    user_id = str(message.from_user.id)
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
        f"🎯 To‘g‘ri javob: {tog risi}\n"
        f"🎉 {message.from_user.full_name} 1 ball oldi!\n\n"
        f"🏆 Reyting:\n{reyting}"
    )

    await send_new_question(message.chat.id)

# Webhook sozlash
@app.on_event("startup")
async def on_startup():
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"✅ Webhook o‘rnatildi: {WEBHOOK_URL}")

@app.post(WEBHOOK_PATH)
async def process_webhook(request: Request):
    data = await request.body()
    update = types.Update(**json.loads(data))
    await dp.process_update(update)
    return {"status": "ok"}
