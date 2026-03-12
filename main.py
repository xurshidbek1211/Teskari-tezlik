import logging
import os
import json
import random
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage

from fastapi import FastAPI, Request

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

# ---------- ENV ----------
API_TOKEN = os.getenv("API_TOKEN")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")

WEBHOOK_PATH = f"/webhook/{API_TOKEN}"
WEBHOOK_URL = f"{RENDER_EXTERNAL_URL}{WEBHOOK_PATH}"

ADMIN_ID = 1899194677
RUXSAT_ETILGANLAR = [ADMIN_ID]

# ---------- BOT ----------
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

Bot.set_current(bot)
Dispatcher.set_current(dp)

app = FastAPI()
logging.basicConfig(level=logging.INFO)

# ---------- FILES ----------
TESKARI_FILE = "teskari_tezlik_savollar.json"
SCORE_FILE = "user_scores.json"
STATE_FILE = "user_states.json"
WINNER_FILE = "winner_count.json"

# ---------- JSON ----------
def load_json(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ---------- NORMALIZE ----------
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

# ---------- ADMIN CHECK ----------
async def check_bot_admin(message: types.Message):
    if message.chat.type == "private":
        return True

    try:
        bot_member = await bot.get_chat_member(message.chat.id, (await bot.get_me()).id)
        return bot_member.is_chat_admin()
    except:
        return False

# ---------- SEND QUESTION ----------
async def send_new_question(chat_id):

    questions = load_json(TESKARI_FILE)
    states = load_json(STATE_FILE)

    used = states.get(str(chat_id), {}).get("used", [])

    available = [q for q in questions if q["savol"] not in used]

    if not available:
        used = []
        available = questions

    question = random.choice(available)
    used.append(question["savol"])

    states[str(chat_id)] = {
        "current": question,
        "answered_by": None,
        "chat_id": chat_id,
        "start_time": datetime.now().timestamp(),
        "used": used
    }

    save_json(STATE_FILE, states)

    await bot.send_message(chat_id, f"🔄 Toping:\n{question['savol']}")

# ---------- /boshla ----------
@dp.message_handler(commands=["boshla"])
async def boshla(message: types.Message):

    if not await check_bot_admin(message):
        await message.answer("❌ Botni admin qiling.")
        return

    await send_new_question(message.chat.id)

# ---------- /add ----------
@dp.message_handler(commands=["add"])
async def add_question(message: types.Message):

    if message.from_user.id not in RUXSAT_ETILGANLAR:
        await message.answer("❌ Sizda huquq yo‘q.")
        return

    text = message.text[4:].strip()

    if "||" not in text:
        await message.answer("Format: /add savol || javob")
        return

    savol, javob = map(str.strip, text.split("||", 1))

    questions = load_json(TESKARI_FILE)

    if not isinstance(questions, list):
        questions = []

    questions.append({
        "savol": savol,
        "javob": javob
    })

    save_json(TESKARI_FILE, questions)

    await message.answer("✅ Savol qo‘shildi")

# ---------- ANSWER CHECK ----------
@dp.message_handler()
async def check_answer(message: types.Message):

    if not await check_bot_admin(message):
        return

    states = load_json(STATE_FILE)
    chat_id = str(message.chat.id)
    user_id = str(message.from_user.id)

    if chat_id not in states:
        return

    state = states[chat_id]

    if state.get("answered_by"):
        return

    user_answer = normalize_answer(message.text)
    correct = normalize_answer(state["current"]["javob"])

    if user_answer == correct:

        seconds = int(datetime.now().timestamp() - state["start_time"])

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
                name = "👤"

            reyting += f"{i+1}. {name} — {ball}\n"

        await message.answer(
            f"""🎯 To‘g‘ri javob: {state['current']['javob']}

⚡ {message.from_user.full_name} {seconds} soniyada topdi
🎉 1 ball qo‘shildi

🏆 Reyting
{reyting}
"""
        )

        await send_new_question(message.chat.id)

# ---------- DAILY WINNER ----------
async def daily_reset():

    scores = load_json(SCORE_FILE)
    winner_count = load_json(WINNER_FILE)

    for chat_id, users in scores.items():

        if not users:
            continue

        winner_id, max_score = max(users.items(), key=lambda x: x[1])

        try:
            name = (await bot.get_chat(int(winner_id))).first_name
        except:
            name = "👤"

        msg = f"""
🌙✨ KUN BILIMDONI ✨🌙

🥇 G‘olib: {name}
🏆 Ball: {max_score}

🎉 Tabriklaymiz!
"""

        await bot.send_message(int(chat_id), msg)

        winner_count[str(winner_id)] = winner_count.get(str(winner_id), 0) + 1

    save_json(WINNER_FILE, winner_count)

    save_json(SCORE_FILE, {})

# ---------- STARTUP ----------
@app.on_event("startup")
async def startup():

    Bot.set_current(bot)
    Dispatcher.set_current(dp)

    await bot.set_webhook(WEBHOOK_URL)

    scheduler = AsyncIOScheduler(
        timezone=pytz.timezone("Asia/Tashkent")
    )

    scheduler.add_job(
        daily_reset,
        CronTrigger(hour=0, minute=0)
    )

    scheduler.start()

# ---------- WEBHOOK ----------
@app.post(WEBHOOK_PATH)
async def webhook(request: Request):

    Bot.set_current(bot)
    Dispatcher.set_current(dp)

    data = await request.json()

    update = types.Update(**data)

    await dp.process_update(update)

    return {"ok": True}

# ---------- ROOT ----------
@app.get("/")
async def root():
    return {"status": "Bot ishlayapti"}
