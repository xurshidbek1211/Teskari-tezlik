import logging
import os
import json
import random

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from fastapi import FastAPI, Request
from aiogram.contrib.fsm_storage.memory import MemoryStorage

API_TOKEN = os.getenv("API_TOKEN")
ADMIN_ID = 1899194677  # Sizning Telegram ID
RUXSAT_ETILGANLAR = [ADMIN_ID]  # Savol qo'shish huquqi berilganlar ro'yxati
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")
WEBHOOK_PATH = f"/webhook/{API_TOKEN}"
WEBHOOK_URL = f"{RENDER_EXTERNAL_URL}{WEBHOOK_PATH}"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
Bot.set_current(bot)
dp = Dispatcher(bot, storage=MemoryStorage())
app = FastAPI()

TESKARI_FILE = 'teskari_tezlik_savollar.json'
SCORE_FILE = 'user_scores.json'
USER_STATE_FILE = 'user_states.json'


def load_json(filename):
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_json(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@dp.message_handler(commands=['boshla'])
async def boshla(message: types.Message):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🌀 Teskari tezlik", callback_data="teskari"))
    kb.add(InlineKeyboardButton("📜 O'yin qoidasi", callback_data="qoidalar"))
    await message.answer("Qaysi kategoriyani tanlaysiz?", reply_markup=kb)


@dp.callback_query_handler(lambda c: c.data == "qoidalar")
async def send_rules(callback_query: types.CallbackQuery):
    rules_text = (
        "Assalomu alaykum! Bu bot teskari tezlik o‘yini uchun yaratildi.\n"
        "O‘yinda so‘zlar teskari yozilgan va ba’zi harflar o‘rniga “1” qo‘yilgan.\n"
        "Sizdan so‘zni to‘g‘ri tartibda va harflar to‘liq holda topish talab qilinadi.\n"
        "Talab va takliflar uchun @Xurshidbek_1211 ga murojaat qiling."
    )
    await bot.send_message(callback_query.message.chat.id, rules_text)
    await callback_query.answer()


@dp.callback_query_handler(lambda c: c.data == "teskari")
async def send_teskari(callback_query: types.CallbackQuery):
    questions = load_json(TESKARI_FILE)
    if not questions:
        await bot.send_message(callback_query.message.chat.id, "Savollar hali mavjud emas.")
        await callback_query.answer()
        return
    question = random.choice(questions)
    user_state = load_json(USER_STATE_FILE)
    user_state[str(callback_query.from_user.id)] = question
    save_json(USER_STATE_FILE, user_state)

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📖 To‘g‘ri javob", callback_data="javob"))
    await bot.send_message(callback_query.message.chat.id, f"Toping: {question['savol']}", reply_markup=kb)
    await callback_query.answer()


@dp.callback_query_handler(lambda c: c.data == "javob")
async def show_answer(callback_query: types.CallbackQuery):
    user_state = load_json(USER_STATE_FILE)
    user_id = str(callback_query.from_user.id)
    if user_id in user_state:
        await bot.send_message(callback_query.message.chat.id, f"✅ To‘g‘ri javob: {user_state[user_id]['javob']}")
    else:
        await bot.send_message(callback_query.message.chat.id, "Savol topilmadi. Iltimos, yangi savol oling.")
    await callback_query.answer()


@dp.message_handler(commands=['ball'])
async def show_ball(message: types.Message):
    scores = load_json(SCORE_FILE)
    score = scores.get(str(message.from_user.id), 0)
    await message.answer(f"📊 Sizning umumiy balingiz: {score}")


@dp.message_handler(commands=['add'])
async def add_question(message: types.Message):
    if message.from_user.id not in RUXSAT_ETILGANLAR:
        await message.reply("Sizda savol qo‘shish huquqi yo‘q.")
        return

    # Format: /add savol || javob
    text = message.text[4:].strip()
    if '||' not in text:
        await message.reply("Savol va javobni to‘g‘ri formatda kiriting:\n/add savol || javob")
        return
    savol, javob = map(str.strip, text.split('||', maxsplit=1))
    if not savol or not javob:
        await message.reply("Savol va javob bo‘sh bo‘lishi mumkin emas.")
        return

    questions = load_json(TESKARI_FILE)
    questions.append({"savol": savol, "javob": javob})
    save_json(TESKARI_FILE, questions)
    await message.reply(f"✅ Savol qo‘shildi:\nSavol: {savol}\nJavob: {javob}")


@dp.message_handler()
async def javobni_tekshir(message: types.Message):
    user_id = str(message.from_user.id)
    user_state = load_json(USER_STATE_FILE)

    if user_id in user_state:
        togri_javob = user_state[user_id]['javob'].lower()
        if message.text.strip().lower() == togri_javob:
            scores = load_json(SCORE_FILE)
            scores[user_id] = scores.get(user_id, 0) + 1
            save_json(SCORE_FILE, scores)

            del user_state[user_id]
            save_json(USER_STATE_FILE, user_state)

            await message.answer("✅ To‘g‘ri! Sizga 1 ball qo‘shildi. Yangi savol kelmoqda...")

            questions = load_json(TESKARI_FILE)
            if not questions:
                await message.answer("Savollar bazasi bo‘sh.")
                return
            question = random.choice(questions)
            user_state[user_id] = question
            save_json(USER_STATE_FILE, user_state)

            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("📖 To‘g‘ri javob", callback_data="javob"))
            await bot.send_message(message.chat.id, f"Toping: {question['savol']}", reply_markup=kb)
        else:
            # Xato javobda hech qanday javob bermaydi (jim turadi)
            pass
    else:
        await message.answer("Iltimos, avval kategoriya tanlab, savol oling.")


@app.on_event("startup")
async def on_startup():
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"Webhook o'rnatildi: {WEBHOOK_URL}")


@app.post(WEBHOOK_PATH)
async def process_webhook(request: Request):
    data = await request.body()
    update = types.Update(**json.loads(data))
    await dp.process_update(update)
    return {"status": "ok"}
