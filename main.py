import logging
import os
import json
import random
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from fastapi import FastAPI, Request

# --- Atrof-muhit sozlamalari ---
API_TOKEN = os.getenv("API_TOKEN")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")
WEBHOOK_PATH = f"/webhook/{API_TOKEN}"
WEBHOOK_URL = f"{RENDER_EXTERNAL_URL}{WEBHOOK_PATH}"

ADMIN_ID = 1899194677
RUXSAT_ETILGANLAR = [ADMIN_ID]

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

Bot.set_current(bot)
Dispatcher.set_current(dp)

app = FastAPI()
logging.basicConfig(level=logging.INFO)

TESKARI_FILE = "teskari_tezlik_savollar.json"
SCORE_FILE = "user_scores.json"
STATE_FILE = "user_states.json"
WINNER_FILE = "winner_count.json"

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

# --- Adminlik tekshiruvi ---
async def is_admin(chat_id: int, user_id: int) -> bool:
    # Lichka chatida har doim True (adminlik shart emas)
    if chat_id > 0:
        return True
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.is_chat_admin()
    except:
        return False

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

# --- /boshla ---
@dp.message_handler(commands=["boshla"])
async def boshla(message: types.Message):
    # Guruhda adminlik tekshiruvi, lichkada ochiq
    if message.chat.type != "private" and not await is_admin(message.chat.id, message.from_user.id):
        await message.answer("❌ Faqat guruh adminlari botni ishlata oladi.")
        return
    await send_new_question(message.chat.id)

# --- /add ---
@dp.message_handler(commands=["add"])
async def add_question(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        await message.answer("❌ Sizda savol qo‘shish huquqi yo‘q.")
        return
    text = message.text[4:].strip()
    if "||" not in text:
        await message.answer("❗️ Format: /add savol || javob")
        return
    savol, javob = map(str.strip, text.split("||", maxsplit=1))
    if not savol or not javob:
        await message.answer("❗️ Savol va javob bo‘sh bo‘lishi mumkin emas.")
        return
    questions = load_json(TESKARI_FILE)
    if not isinstance(questions, list):
        questions = []
    questions.append({"savol": savol, "javob": javob if isinstance(javob, list) else javob})
    save_json(TESKARI_FILE, questions)
    await message.answer("✅ Savol qo‘shildi!")

# --- /ball ---
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

# --- Kun g‘oliblarini aniqlash ---
async def congratulate_daily_winner_once():
    scores = load_json(SCORE_FILE)
    winner_count = load_json(WINNER_FILE)
    new_scores = {}

    for chat_id, users in scores.items():
        if not users:
            continue

        winner_id, max_score = max(users.items(), key=lambda x: x[1])
        try:
            chat_info = await bot.get_chat(int(chat_id))
            chat_title = chat_info.title
        except:
            chat_title = "Nomaʼlum guruh"

        try:
            user = await bot.get_chat(int(winner_id))
            name = user.first_name
        except:
            name = "👤 Nomaʼlum"

        congrat_msg = f"""🌟🌸 TABRIKLAYMIZ! 🌸🌟

🥇 Bugungi kunning G‘OLIBI: {name}!
🎉 1-o‘rinni egallaganingiz bilan chin dildan tabriklaymiz! 🎉

💫 Siz kabi bilimdonlar bizning botimizning faxridir!
🏆 Guruh: {chat_title}"""

        await bot.send_message(int(chat_id), congrat_msg)

        # Winner count update (kunlik g'oliblar sonini ko‘paytirish, nolga tushmaydi)
        winner_count[str(winner_id)] = winner_count.get(str(winner_id), 0) + 1

        # Kunlik ballarni 0 ga tushuramiz
        new_scores[chat_id] = {}

    save_json(SCORE_FILE, new_scores)
    save_json(WINNER_FILE, winner_count)

# --- /tabrik komandasi ---
@dp.message_handler(commands=["tabrik"])
async def manual_tabrik(message: types.Message):
    # Faqat admin
    if message.from_user.id != ADMIN_ID:
        return
    await congratulate_daily_winner_once()
    await message.answer("✅ Barcha guruhlarda tabrik yuborildi va ballar yangilandi.")

# --- /kun komandasi ---
@dp.message_handler(commands=["kun"])
async def show_top_winners(message: types.Message):
    winner_count = load_json(WINNER_FILE)
    if not winner_count:
        await message.answer("❌ Hali hech kim Kun bilimdoni bo‘lmagan.")
        return

    sorted_winners = sorted(winner_count.items(), key=lambda x: x[1], reverse=True)[:20]
    text = "🏆 *Top 20 Kun Bilimdonlari:*\n\n"

    for idx, (user_id, count) in enumerate(sorted_winners, start=1):
        try:
            user = await bot.get_chat(int(user_id))
            name = user.first_name
        except:
            name = "👤 Nomaʼlum"
        text += f"{idx}. {name} — {count} marta\n"

    await message.answer(text, parse_mode="Markdown")

# --- Scheduler 00:00 ---
async def scheduler():
    while True:
        now = datetime.now()
        target = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        await asyncio.sleep((target - now).total_seconds())
        await congratulate_daily_winner_once()

# --- Webhook sozlash ---
@app.on_event("startup")
async def on_startup():
    asyncio.create_task(scheduler())
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"✅ Webhook o‘rnatildi: {WEBHOOK_URL}")

# --- Webhookni qabul qilish ---
@app.post(WEBHOOK_PATH)
async def process_webhook(request: Request):
    data = await request.body()
    update = types.Update(**json.loads(data))
    await dp.process_update(update)
    return {"status": "ok"}

@app.get("/")
async def root():
    return {"status": "Bot tirik va ishlayapti ✅"}
