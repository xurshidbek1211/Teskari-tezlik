import logging
import os
import json
import random

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from fastapi import FastAPI, Request

API_TOKEN = os.getenv("API_TOKEN")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")
WEBHOOK_PATH = f"/webhook/{API_TOKEN}"
WEBHOOK_URL = f"{RENDER_EXTERNAL_URL}{WEBHOOK_PATH}"

ADMIN_ID = 1899194677
RUXSAT_ETILGANLAR = [ADMIN_ID]

TESKARI_FILE = 'teskari_tezlik_savollar.json'
SCORE_FILE = 'user_scores.json'
USER_STATE_FILE = 'user_states.json'

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
app = FastAPI()

logging.basicConfig(level=logging.INFO)

# --- JSON fayl funksiyalari ---
def load_json(filename):
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_json(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def normalize_answer(text: str) -> str:
    text = text.lower()
    text = text.replace("ʼ", "'").replace("`", "'").replace("´", "'").replace("‘", "'").replace("’", "'")
    return text.strip()

# --- /boshla ---
@dp.message_handler(commands=['boshla'])
async def boshla(message: types.Message):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🄀 Teskari tezlik", callback_data="teskari"))
    kb.add(InlineKeyboardButton("📜 O'yin qoidasi", callback_data="qoidalar"))
    await message.answer("Qaysi kategoriyani tanlaysiz?", reply_markup=kb)

# --- O'yin qoidalari ---
@dp.callback_query_handler(lambda c: c.data == "qoidalar")
async def send_rules(callback_query: types.CallbackQuery):
    rules_text = (
        "📌 Teskari tezlik o‘yini qoidalari:\n"
        "- So‘zlar teskari yozilgan bo‘ladi.\n"
        "- Har kim birinchi to‘g‘ri topib yozsa, 1 ball oladi.\n"
        "- Har javobdan keyin avtomatik yangi savol yuboriladi.\n"
        "- Reytingda eng faol o‘yinchilar ko‘rsatiladi.\n"
        "📝 Taklif va shikoyatlar uchun: @Xurshidbek_1211"
    )
    await bot.send_message(callback_query.message.chat.id, rules_text)
    await callback_query.answer()

# --- Teskari o'yin boshlanishi ---
@dp.callback_query_handler(lambda c: c.data == "teskari")
async def send_teskari(callback_query: types.CallbackQuery):
    questions = load_json(TESKARI_FILE)
    if not questions:
        await bot.send_message(callback_query.message.chat.id, "Savollar mavjud emas.")
        await callback_query.answer()
        return

    question = random.choice(questions)
    user_state = {
        "current": question,
        "answered_by": None
    }
    save_json(USER_STATE_FILE, user_state)

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📖 To‘g‘ri javob", callback_data="javob"))
    await bot.send_message(callback_query.message.chat.id, f"🧠 Toping: {question['savol']}", reply_markup=kb)
    await callback_query.answer()

# --- To‘g‘ri javobni ko‘rsatish ---
@dp.callback_query_handler(lambda c: c.data == "javob")
async def show_answer(callback_query: types.CallbackQuery):
    user_state = load_json(USER_STATE_FILE)
    if "current" in user_state:
        await bot.send_message(callback_query.message.chat.id, f"✅ To‘g‘ri javob: {user_state['current']['javob']}")
    else:
        await bot.send_message(callback_query.message.chat.id, "⛔ Savol topilmadi.")
    await callback_query.answer()

# --- Ball ko‘rsatish ---
@dp.message_handler(commands=['ball'])
async def show_ball(message: types.Message):
    scores = load_json(SCORE_FILE)
    score = scores.get(str(message.from_user.id), 0)
    await message.answer(f"📊 Sizning umumiy balingiz: {score}")

# --- Savol qo‘shish (/add) ---
@dp.message_handler(commands=['add'])
async def add_question(message: types.Message):
    if message.from_user.id not in RUXSAT_ETILGANLAR:
        await message.reply("⛔ Sizda savol qo‘shish huquqi yo‘q.")
        return

    text = message.text[4:].strip()
    if '||' not in text:
        await message.reply("❗ Format: /add savol || javob")
        return

    savol, javob = map(str.strip, text.split('||', maxsplit=1))
    if not savol or not javob:
        await message.reply("⛔ Savol yoki javob bo‘sh bo‘lishi mumkin emas.")
        return

    questions = load_json(TESKARI_FILE)
    questions.append({"savol": savol, "javob": javob})
    save_json(TESKARI_FILE, questions)
    await message.reply(f"✅ Savol qo‘shildi:\nSavol: {savol}\nJavob: {javob}")

# --- Guruhda javobni tekshirish ---
@dp.message_handler()
async def javobni_tekshir(message: types.Message):
    if message.chat.type not in ("group", "supergroup"):
        return

    user_id = str(message.from_user.id)
    user_state = load_json(USER_STATE_FILE)

    if "current" not in user_state or user_state.get("answered_by"):
        return

    current = user_state["current"]
    foydalanuvchi_javobi = normalize_answer(message.text)
    togri_javob = normalize_answer(current['javob'])

    if foydalanuvchi_javobi == togri_javob:
        # Ball qo‘shish
        scores = load_json(SCORE_FILE)
        scores[user_id] = scores.get(user_id, 0) + 1
        save_json(SCORE_FILE, scores)

        user_state["answered_by"] = user_id
        save_json(USER_STATE_FILE, user_state)

        user_fullname = message.from_user.full_name
        text = f"✅ To‘g‘ri javob: {current['javob']}\n🎉 {user_fullname} ga 1 ball qo‘shildi."

        # TOP 10 reyting
        top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:10]
        statistik = ""
        for i, (uid, score) in enumerate(top, start=1):
            try:
                user = await bot.get_chat(int(uid))
                statistik += f"{i}. {user.first_name} - {score} ball\n"
            except:
                statistik += f"{i}. ID {uid} - {score} ball\n"

        text += f"\n\n🏆 Top 10 reyting:\n{statistik}"
        await message.answer(text)

        # Yangi savol avtomatik yuborish
        questions = load_json(TESKARI_FILE)
        if not questions:
            await message.answer("❗ Yangi savollar mavjud emas.")
            return

        new_question = random.choice(questions)
        user_state = {
            "current": new_question,
            "answered_by": None
        }
        save_json(USER_STATE_FILE, user_state)

        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📖 To‘g‘ri javob", callback_data="javob"))
        await message.answer(f"🧠 Yangi savol: {new_question['savol']}", reply_markup=kb)

# --- FastAPI Webhook ---
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
