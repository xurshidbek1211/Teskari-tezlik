import json
import random
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.utils import executor
from fastapi import FastAPI
import uvicorn
import nest_asyncio

API_TOKEN = "BOT_TOKEN"  # ← bu yerga bot tokeningizni yozing
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

app = FastAPI()
nest_asyncio.apply()

TESKARI_FILE = "teskari_tezlik_savollar.json"
STATE_FILE = "state.json"
SCORES_FILE = "scores.json"


def load_json(filename):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@dp.message_handler(commands=["boshla"])  # "start" o‘rniga "boshla"
async def start_handler(message: Message):
    await send_new_question(message.chat.id)


async def send_new_question(chat_id):
    questions = load_json(TESKARI_FILE)
    if not questions:
        await bot.send_message(chat_id, "Savollar mavjud emas.")
        return

    question = random.choice(questions)
    state = {
        "current": question,
        "answered_by": None,
        "chat_id": chat_id
    }
    save_json(STATE_FILE, state)

    msg = f"Toping: {question['savol']}\n\n🤖 Botni guruhga qo‘shish: https://t.me/Turli_Savollarbot?startgroup=true"
    await bot.send_message(chat_id, msg)


@dp.message_handler()
async def answer_handler(message: Message):
    state = load_json(STATE_FILE)
    if not state or str(state["chat_id"]) != str(message.chat.id):
        return

    if state.get("answered_by"):
        return

    correct_answer = state["current"]["javob"].lower()
    if message.text.lower() == correct_answer:
        state["answered_by"] = message.from_user.id
        save_json(STATE_FILE, state)

        scores = load_json(SCORES_FILE)
        chat_id_str = str(message.chat.id)
        user_id_str = str(message.from_user.id)

        if chat_id_str not in scores:
            scores[chat_id_str] = {}

        if user_id_str not in scores[chat_id_str]:
            scores[chat_id_str][user_id_str] = {
                "name": message.from_user.full_name,
                "score": 0
            }

        scores[chat_id_str][user_id_str]["score"] += 1
        save_json(SCORES_FILE, scores)

        await message.reply(f"✅ To‘g‘ri javob!\n\n🏆 {message.from_user.full_name} - {scores[chat_id_str][user_id_str]['score']} ball")
        await show_leaderboard(message.chat.id)
        await send_new_question(message.chat.id)


async def show_leaderboard(chat_id):
    scores = load_json(SCORES_FILE)
    chat_scores = scores.get(str(chat_id), {})

    if not chat_scores:
        return

    leaderboard = sorted(chat_scores.items(), key=lambda x: x[1]["score"], reverse=True)
    msg = "📊 Reyting:\n"
    for i, (user_id, data) in enumerate(leaderboard[:10], 1):
        msg += f"{i}. {data['name']} – {data['score']} ball\n"

    await bot.send_message(chat_id, msg)


@app.get("/")
async def root():
    return {"message": "Bot ishga tushdi"}


def start():
    import threading
    threading.Thread(target=lambda: uvicorn.run(app, host="0.0.0.0", port=8000)).start()
    executor.start_polling(dp, skip_updates=True)

if __name__ == "__main__":
    start()
