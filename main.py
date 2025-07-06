import nest_asyncio
nest_asyncio.apply()

import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.types import Message
from fastapi import FastAPI
import uvicorn
import random
from collections import defaultdict

API_TOKEN = "7265238026:AAE4n-lQd--ViqQgyFhB51XnURFcRdM8Cp8"

bot = Bot(token=API_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

app = FastAPI()

questions = [
    {"savol": "nobirhe1", "javob": "mehribon"},
    {"savol": "mol‘go1", "javob": "sog‘lom"},
    {"savol": "tamh1r", "javob": "rahmat"},
    {"savol": "movadra1", "javob": "bardavom"},
    {"savol": "taqod1s", "javob": "sadoqat"},
    {"savol": "to1ah", "javob": "hayot"},
    {"savol": "r1hab", "javob": "bahor"},
    {"savol": "il1li", "javob": "ilmli"},
    {"savol": "o1nud", "javob": "dunyo"},
    {"savol": "hsod1‘oy", "javob": "yo‘ldosh"},
    {"savol": "1aloud", "javob": "duolar"},
    {"savol": "oy1ad", "javob": "daryo"},
    {"savol": "adgno1", "javob": "tongda"},
    {"savol": "mu1sabat", "javob": "tabassum"},
    {"savol": "ralhs1y", "javob": "yoshlar"},
    {"savol": "noja1o", "javob": "onajon"},
    {"savol": "a1ala‘g", "javob": "g‘alaba"},
    {"savol": "aqabo1um", "javob": "musobaqa"},
    {"savol": "kilts‘1d", "javob": "do‘stlik"},
    {"savol": "yim1mas", "javob": "samimiy"},
    {"savol": "1irihs", "javob": "shirin"},
    {"savol": "ki1hcnit", "javob": "tinchlik"},
    {"savol": "taros1j", "javob": "jasorat"},
    {"savol": "1s‘od", "javob": "do‘st"},
    {"savol": "1atkam", "javob": "maktab"},
    {"savol": "nit1o", "javob": "oltin"},
    {"savol": "ali1", "javob": "oila"},
    {"savol": "ilr1n", "javob": "nurli"},
    {"savol": "kildo1s", "javob": "shodlik"},
    {"savol": "t1biqo", "javob": "oqibat"},
    {"savol": "hc1ovuq", "javob": "quvonch"},
    {"savol": "m1lib", "javob": "bilim"},
    {"savol": "kill1z‘og", "javob": "go‘zallik"},
    {"savol": "r1zlug", "javob": "gulzor"},
    {"savol": "kaja1ek", "javob": "kelajak"},
    {"savol": "i1nay", "javob": "yangi"},
    {"savol": "anida1", "javob": "madina"},
    {"savol": "firhsa1", "javob": "tashrif"},
    {"savol": "1hem", "javob": "mehr"},
    {"savol": "ig1es", "javob": "sevgi"},
    {"savol": "tal1da", "javob": "adolat"},
    {"savol": "1iblaq", "javob": "qalbim"},
    {"savol": "dn1zraf", "javob": "farzand"},
    {"savol": "azo1", "javob": "toza"},
    {"savol": "zudlu1", "javob": "yulduz"},
    {"savol": "1atav", "javob": "vatan"},
    {"savol": "tn1khsot", "javob": "toshkent"},
    {"savol": "b1tik", "javob": "kitob"},
    {"savol": "fn1s", "javob": "sinf"},
    {"savol": "ad1nis", "javob": "sinfda"}
]

asked_questions = {}
scores = defaultdict(lambda: defaultdict(int))
current_answers = {}

@dp.message(F.text == "/boshla")
async def boshla_handler(message: Message):
    if not message.chat.type.endswith("group"):
        return await message.answer("Iltimos, bu buyruq faqat guruhda ishlaydi.")
    await send_new_question(message.chat.id)

async def send_new_question(chat_id: int):
    question = random.choice(questions)
    asked_questions[chat_id] = question
    current_answers[chat_id] = {'javob': question["javob"].lower(), 'answered': False}

    await bot.send_message(
        chat_id,
        f"🔄 <b>So‘zning teskari shakli:</b>\n<code>{question['savol']}</code>\n\n✅ To‘g‘ri javob bergan foydalanuvchi ball oladi!",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="🤖 Botni guruhga qo‘shish", url="https://t.me/Turli_Savollarbot?startgroup=true")]
            ]
        )
    )

@dp.message()
async def javob_tekshir(message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    username = message.from_user.full_name

    if chat_id not in current_answers or current_answers[chat_id]['answered']:
        return

    if message.text.strip().lower() == current_answers[chat_id]['javob']:
        current_answers[chat_id]['answered'] = True
        scores[chat_id][user_id] += 1

        await message.answer(
            f"🎉 <b>{username}</b> to‘g‘ri javob berdi!\n📊 <b>Ball:</b> {scores[chat_id][user_id]}"
        )

        await asyncio.sleep(3)
        await send_new_question(chat_id)

@app.get("/")
async def home():
    return {"status": "Bot ishlayapti!"}

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    import threading
    threading.Thread(target=lambda: uvicorn.run(app, host="0.0.0.0", port=10000)).start()
    asyncio.run(main())
