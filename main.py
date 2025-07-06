import json
import logging
import os
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.types import ParseMode
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from dotenv import load_dotenv

load_dotenv()

api_token = os.getenv("API_TOKEN")
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{os.getenv('WEBHOOK_BASE_URL')}{WEBHOOK_PATH}"

bot = Bot(token=api_token, parse_mode=ParseMode.HTML)
dp = Dispatcher(bot, storage=MemoryStorage())
app = FastAPI()

SAVOL_FILE = "teskari_tezlik_savollar.json"
SCORE_FILE = "score.json"
STATE_FILE = "state.json"

def load_json(file):
    try:
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_next_question(chat_id):
    savollar = load_json(SAVOL_FILE)
    state = load_json(STATE_FILE)

    if chat_id not in state:
        state[chat_id] = {"used": []}

    used = state[chat_id]["used"]
    q_list = [s for s in savollar if s["id"] not in used]

    if not q_list:
        state[chat_id]["used"] = []
        q_list = savollar

    question = q_list[0]
    state[chat_id]["current"] = question
    state[chat_id]["used"].append(question["id"])
    save_json(STATE_FILE, state)
    return question

async def send_new_question(chat_id):
    question = get_next_question(str(chat_id))
    matn = f"🧠 <b>Topshiriq:</b>\n{question['savol']}"
    await bot.send_message(chat_id, matn)

@dp.message_handler()
async def handle_answer(message: types.Message):
    state = load_json(STATE_FILE)
    chat_id = str(message.chat.id)
    user_id = str(message.from_user.id)

    if chat_id not in state or "current" not in state[chat_id]:
        await message.answer("❗ Savol hali yuborilmagan.")
        return

    current = state[chat_id]["current"]
    if message.text.strip().lower() == current["javob"].lower():
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
            f"✅ To‘g‘ri javob: <b>{current['javob']}</b>\n"
            f"🎉 {message.from_user.full_name} 1 ball oldi!\n\n"
            f"🏆 <b>Reyting:</b>\n{reyting}"
        )

        await send_new_question(chat_id)
    else:
        await message.answer("❌ Noto‘g‘ri javob. Yana urinib ko‘ring.")

# Webhook sozlash
@app.on_event("startup")
async def on_startup():
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"✅ Webhook o‘rnatildi: {WEBHOOK_URL}")

# Webhookni qabul qilish
@app.post(WEBHOOK_PATH)
async def process_webhook(request: Request):
    data = await request.body()
    update = types.Update(**json.loads(data))
    await dp.process_update(update)
    return {"status": "ok"}
