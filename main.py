import logging
import os
import json
import random
import datetime
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
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

# --- JSON fayllarni yuklash/saqlash ---
def load_json(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# --- Javoblarni normallashtirish ---
def normalize_answer(text):
    return (
        text.lower()
        .replace("ʼ", "'")
        .replace("`", "'")
        .replace("´", "'")
        .replace("‘", "'")
        .replace("’", "'")
        .strip()
    )

# --- Yangi savol yuborish ---
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

# --- /boshla komandasi ---
@dp.message_handler(commands=["boshla"])
async def boshla(message: types.Message):
    await send_new_question(message.chat.id)

# --- /add komandasi (faqat adminlarga) ---
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

# --- /ball komandasi ---
@dp.message_handler(commands=["ball"])
async def show_score(message: types.Message):
    scores = load_json(SCORE_FILE)
    chat_id = str(message.chat.id)
    user_id = str(message.from_user.id)
    chat_scores = scores.get(chat_id, {})
    user_score = chat_scores.get(user_id, 0)
    await message.answer(f"📊 Sizning guruhdagi umumiy balingiz: {user_score}")

# --- Javoblarni tekshirish ---
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
    correct = normalize_answer(state["current"]["javob"])
    user_answer = normalize_answer(message.text)
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

# --- Kunlik g‘olibni aniqlab tabriklash ---
async def check_daily_winner():
    while True:
        now = datetime.datetime.now()
        if now.hour == 0 and now.minute == 0:
            scores = load_json(SCORE_FILE)
            for chat_id, user_scores in scores.items():
                if not user_scores:
                    continue
                winner_id = max(user_scores, key=user_scores.get)
                try:
                    winner = await bot.get_chat(int(winner_id))
                    name = winner.first_name
                except:
                    name = "👤 Nomaʼlum"
                await bot.send_message(
                    int(chat_id),
                    f"""🌟🌸 TABRIKLAYMIZ! 🌸🌟

🥇 Bugungi kunning G‘OLIBI: {name}!
🎉 1-o‘rinni egallaganingiz bilan chin dildan tabriklaymiz! 🎉

🌷 Ilmingiz yana-da ziyoda bo‘lsin,
🌼 Zukkoligingiz yanada charog‘on bo‘lsin,
🌺 Har bir yutuq sizga ilhom bersin!

💫 Siz kabi bilimdonlar bizning botimizning faxridir!
Doimo yuksalishda bo‘ling! 🚀"""
                )
            await asyncio.sleep(60)
        else:
            await asyncio.sleep(30)

# --- Webhook sozlash ---
@app.on_event("startup")
async def on_startup():
    await bot.set_webhook(WEBHOOK_URL)
    asyncio.create_task(check_daily_winner())
    logging.info(f"✅ Webhook o‘rnatildi: {WEBHOOK_URL}")

# --- Webhookni qabul qilish ---
@app.post(WEBHOOK_PATH)
async def process_webhook(request: Request):
    data = await request.body()
    update = types.Update(**json.loads(data))
    await dp.process_update(update)
    return {"status": "ok"}

# ✅ Render tirikligini saqlab turuvchi endpoint
@app.get("/")
async def root():
    return {"status": "Bot tirik va ishlayapti ✅"}
