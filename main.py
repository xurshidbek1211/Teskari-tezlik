import logging
import os
import json
import random
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from fastapi import FastAPI, Request

# --- Atrof-muhit o‘zgaruvchilar ---
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
    if not isinstance(questions, list):
        questions = []
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
    if "current" not in state:
        return

    if state.get("answered_by") is not None:
        return

    user_answer = normalize_answer(message.text)
    correct_raw = state["current"]["javob"]

    if isinstance(correct_raw, list):
        correct_list = [normalize_answer(j) for j in correct_raw]
    else:
        correct_list = [normalize_answer(correct_raw)]

    if user_answer in correct_list:
        state["answered_by"] = user_id
        states[chat_id] = state
        save_json(STATE_FILE, states)

        scores = load_json(SCORE_FILE)
        if chat_id not in scores:
            scores[chat_id] = {}
        scores[chat_id][user_id] = scores[chat_id].get(user_id, 0) + 1
        save_json(SCORE_FILE, scores)

        # --- Reyting ---
        top = sorted(scores[chat_id].items(), key=lambda x: x[1], reverse=True)[:10]
        reyting = ""
        for i, (uid, ball) in enumerate(top):
            try:
                user = await bot.get_chat(int(uid))
                name = user.first_name
            except:
                name = "👤 Nomaʼlum"
            reyting += f"{i+1}. {name} - {ball} ball\n"

        javob_text = (
            "\n".join(correct_raw) if isinstance(correct_raw, list) else correct_raw
        )
        await message.answer(
            f"🎯 To‘g‘ri javob: {javob_text}\n"
            f"🎉 {message.from_user.full_name} 1 ball oldi!\n\n"
            f"🏆 Guruhdagi eng yaxshi 10 ta foydalanuvchi:\n{reyting}"
        )

        await send_new_question(message.chat.id)

# --- Faqat bir marta ishlaydigan tabriklash funksiyasi ---
async def congratulate_daily_winner_once():
    scores = load_json(SCORE_FILE)
    new_scores = {}

    for chat_id, users in scores.items():
        if not users:
            continue

        winner_id, max_score = max(users.items(), key=lambda x: x[1])
        try:
            user = await bot.get_chat(int(winner_id))
            name = user.first_name
        except:
            name = "👤 Nomaʼlum"

        congrat_msg = f"""🌟🌸 TABRIKLAYMIZ! 🌸🌟

🥇 Bugungi kunning G‘OLIBI: {name}!
🎉 1-o‘rinni egallaganingiz bilan chin dildan tabriklaymiz! 🎉

🌷 Ilmingiz yana-da ziyoda bo‘lsin,
🌼 Zukkoligingiz yanada charog‘on bo‘lsin,
🌺 Har bir yutuq sizga ilhom bersin!

💫 Siz kabi bilimdonlar bizning botimizning faxridir!
Doimo yuksalishda bo‘ling! 🚀"""

        await bot.send_message(int(chat_id), congrat_msg)
        new_scores[chat_id] = {}  # Har bir guruh uchun ballarni 0 ga tushuramiz

    save_json(SCORE_FILE, new_scores)

# --- /tabrik komandasi (faqat bot egasiga) ---
@dp.message_handler(commands=["tabrik"])
async def manual_congratulation(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("❌ Sizda bu buyruqni ishlatish huquqi yo‘q.")
        return

    await congratulate_daily_winner_once()
    await message.reply("✅ Barcha guruhlarda g‘oliblar tabriklandi va ballar yangilandi.")

# --- Har kuni 00:00 da tabriklash ---
async def schedule_daily_congratulations():
    while True:
        now = datetime.now()
        tomorrow = now + timedelta(days=1)
        run_time = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 0, 0, 0)
        wait_seconds = (run_time - now).total_seconds()

        logging.info(f"⏳ Keyingi tabriklash {run_time} da ishga tushadi.")
        await asyncio.sleep(wait_seconds)

        logging.info("🏆 Kunlik g‘olibni tabriklash boshlandi.")
        await congratulate_daily_winner_once()

# --- Webhook startup ---
@app.on_event("startup")
async def on_startup():
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"✅ Webhook o‘rnatildi: {WEBHOOK_URL}")

    # Kunlik tabriklashni rejalashtirish
    asyncio.create_task(schedule_daily_congratulations())

# --- Webhookni qabul qilish ---
@app.post(WEBHOOK_PATH)
async def process_webhook(request: Request):
    data = await request.body()
    update = types.Update(**json.loads(data))
    await dp.process_update(update)
    return {"status": "ok"}

# --- Render tirikligini ko‘rsatish uchun root endpoint ---
@app.get("/")
async def root():
    return {"status": "Bot tirik va ishlayapti ✅"}
