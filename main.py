import logging
import os
import json
import random
import pathlib
from datetime import datetime

from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import Command
from aiogram.types import BotCommand, Update

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

# ── Rasm o'yini moduli (rasm_router bu yerda eksport qilinadi) ────────────────
import rasm_oyini

# ---------- ENV ----------
API_TOKEN = os.getenv("API_TOKEN")

def _base_url() -> str:
    url = os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
    if url:
        return url
    dev = os.getenv("REPLIT_DEV_DOMAIN", "").strip()
    return f"https://{dev}" if dev else ""

RENDER_EXTERNAL_URL = _base_url()
WEBHOOK_PATH        = f"/webhook/{API_TOKEN}"
WEBHOOK_URL         = f"{RENDER_EXTERNAL_URL}{WEBHOOK_PATH}"

ADMIN_ID          = 1899194677
RUXSAT_ETILGANLAR = [ADMIN_ID]

# ---------- BOT & DISPATCHER ----------
bot = Bot(token=API_TOKEN)
dp  = Dispatcher()

# ⚠️  TARTIB MUHIM: rasm_router (Command filtrlari) OLDIN,
#     keyin main router (catch-all) ulanishi kerak.
#     Aks holda catch-all /rasm ni ushlaydi.
dp.include_router(rasm_oyini.rasm_router)   # 1-o'rinda — Command("rasm") + callbacklar

main_router = Router()                       # 2-o'rinda — /start, /boshla, /add + catch-all
dp.include_router(main_router)

app = FastAPI()
logging.basicConfig(level=logging.INFO)

# ---------- STATIC ----------
pathlib.Path("static").mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# ---------- FILES ----------
TESKARI_FILE = "teskari_tezlik_savollar.json"
SCORE_FILE   = "user_scores.json"
STATE_FILE   = "user_states.json"
WINNER_FILE  = "winner_count.json"

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
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .strip()
    )

# ---------- ADMIN CHECK ----------
async def check_bot_admin(message: types.Message, bot: Bot) -> bool:
    if message.chat.type == "private":
        return True
    try:
        me     = await bot.get_me()
        member = await bot.get_chat_member(message.chat.id, me.id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False

# ---------- SEND QUESTION ----------
async def send_new_question(chat_id: int, bot: Bot):
    questions = load_json(TESKARI_FILE)
    states    = load_json(STATE_FILE)

    used      = states.get(str(chat_id), {}).get("used", [])
    available = [q for q in questions if q["savol"] not in used]

    if not available:
        used      = []
        available = questions

    question = random.choice(available)
    used.append(question["savol"])

    states[str(chat_id)] = {
        "current":     question,
        "answered_by": None,
        "chat_id":     chat_id,
        "start_time":  datetime.now().timestamp(),
        "used":        used,
    }
    save_json(STATE_FILE, states)
    await bot.send_message(chat_id, f"🔄 Toping:\n{question['savol']}")

# ---------- /start ----------
@main_router.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer(
        "👋 Salom! Men <b>Teskari Tezlik</b> botiman.\n\n"
        "📋 <b>Mavjud komandalar:</b>\n"
        "/boshla — Teskari tezlik o'yinini boshlash\n"
        "/rasm — 🎨 Rasm chizish o'yinini boshlash\n"
        "/ball — Ballaringizni ko'rish\n"
        "/reyting — Reyting ro'yxati\n"
        "/add — Yangi savol qo'shish (admin)\n\n"
        "🎮 <b>Qanday o'ynash:</b>\n"
        "• <b>Teskari tezlik:</b> Teskari yozilgan so'zni toping!\n"
        "• <b>Rasm o'yini:</b> So'zni rasm chizib ko'rsating, boshqalar topsun!",
        parse_mode="HTML",
    )

# ---------- /boshla ----------
@main_router.message(Command("boshla"))
async def boshla(message: types.Message, bot: Bot):
    if not await check_bot_admin(message, bot):
        await message.answer("❌ Botni admin qiling.")
        return
    await send_new_question(message.chat.id, bot)

# ---------- /add ----------
@main_router.message(Command("add"))
async def add_question_cmd(message: types.Message):
    if message.from_user.id not in RUXSAT_ETILGANLAR:
        await message.answer("❌ Sizda huquq yo'q.")
        return

    text = (message.text or "")[4:].strip()
    if "||" not in text:
        await message.answer("Format: /add savol || javob")
        return

    savol, javob = map(str.strip, text.split("||", 1))
    questions    = load_json(TESKARI_FILE)
    if not isinstance(questions, list):
        questions = []

    questions.append({"savol": savol, "javob": javob})
    save_json(TESKARI_FILE, questions)
    await message.answer("✅ Savol qo'shildi")

# ---------- UMUMIY XABAR HANDLER (CATCH-ALL) ----------
# F.text filtri: faqat matn xabarlar (media, sticker emas)
# Command xabarlar (/rasm, /boshla va h.k.) bu yerga TUSHMAYDI —
# chunki rasm_router va main_router'dagi Command handlerlari oldinroq ishlaydi.
@main_router.message(F.text)
async def check_answer(message: types.Message, bot: Bot):
    txt = message.text or ""

    # Qo'shimcha himoya: agar slash bilan boshlansa va noma'lum komanda bo'lsa — o'tkazib yubor
    if txt.startswith("/"):
        return

    # 1) Shaxsiy chatda custom so'z kiritish (rasm o'yini)
    if message.chat.type == "private":
        handled = await rasm_oyini.handle_private_custom_word(message)
        if handled:
            return

    # 2) Rasm o'yini javob tekshiruvi (guruhda)
    if message.chat.type != "private":
        draw_correct = await rasm_oyini.check_drawing_answer(message, bot)
        if draw_correct:
            return

    # 3) Teskari tezlik javob tekshiruvi
    if not await check_bot_admin(message, bot):
        return

    states  = load_json(STATE_FILE)
    chat_id = str(message.chat.id)
    user_id = str(message.from_user.id)

    if chat_id not in states:
        return

    state = states[chat_id]
    if state.get("answered_by"):
        return

    user_answer = normalize_answer(txt)
    correct_raw = state["current"]["javob"]

    correct_list = (
        [normalize_answer(j) for j in correct_raw]
        if isinstance(correct_raw, list)
        else [normalize_answer(correct_raw)]
    )

    if user_answer in correct_list:
        seconds              = int(datetime.now().timestamp() - state["start_time"])
        state["answered_by"] = user_id
        states[chat_id]      = state
        save_json(STATE_FILE, states)

        scores = load_json(SCORE_FILE)
        if chat_id not in scores:
            scores[chat_id] = {}
        scores[chat_id][user_id] = scores[chat_id].get(user_id, 0) + 1
        save_json(SCORE_FILE, scores)

        top     = sorted(scores[chat_id].items(), key=lambda x: x[1], reverse=True)[:10]
        reyting = ""
        for i, (uid, ball) in enumerate(top):
            try:
                member = await bot.get_chat_member(message.chat.id, int(uid))
                name   = member.user.first_name
            except Exception:
                name = "👤 Nomaʼlum"
            reyting += f"{i+1}. {name} — {ball}\n"

        javob_text = "\n".join(correct_raw) if isinstance(correct_raw, list) else correct_raw

        await message.answer(
            f"🎯 To'g'ri javob: {javob_text}\n"
            f"⚡ {message.from_user.full_name} {seconds} soniyada topdi\n"
            f"🎉 1 ball qo'shildi!\n\n"
            f"🏆 Reyting (top 10):\n{reyting}"
        )
        await send_new_question(message.chat.id, bot)

# ---------- DAILY WINNER ----------
async def daily_reset():
    scores       = load_json(SCORE_FILE)
    winner_count = load_json(WINNER_FILE)

    for chat_id, users in scores.items():
        if not users:
            continue
        winner_id, max_score = max(users.items(), key=lambda x: x[1])
        try:
            member = await bot.get_chat_member(int(chat_id), int(winner_id))
            name   = member.user.first_name
        except Exception:
            name = "👤 Nomaʼlum"

        msg = (
            "\n🌙━━━━━━━━━━━━━━━━🌙\n"
            "      🏆 KUN BILIMDONI 🏆\n"
            "🌙━━━━━━━━━━━━━━━━🌙\n\n"
            f"🥇 G'olib: {name}\n"
            f"📊 Ball: {max_score}\n\n"
            "🎉 Tabriklaymiz!\n"
        )
        await bot.send_message(int(chat_id), msg)
        winner_count[str(winner_id)] = winner_count.get(str(winner_id), 0) + 1

    save_json(WINNER_FILE, winner_count)
    save_json(SCORE_FILE, {})

# ---------- STARTUP ----------
@app.on_event("startup")
async def startup():
    # rasm_oyini ga bot havolasini berish va FastAPI routelarini qo'shish
    await rasm_oyini.setup_fastapi(bot=bot, app=app)

    # Bot "/" menyusida ko'rinadigan komandalar
    await bot.set_my_commands([
        BotCommand(command="boshla",    description="Teskari tezlik o'yinini boshlash"),
        BotCommand(command="rasm",      description="🎨 Rasm chizish o'yinini boshlash"),
        BotCommand(command="ball",      description="Ballaringizni ko'rish"),
        BotCommand(command="reyting",   description="Reyting ro'yxati"),
        BotCommand(command="tabrik",    description="Tabriknoma"),
        BotCommand(command="kun",       description="Kun bilimdoni"),
        BotCommand(command="adminadd",  description="Admin qo'shish"),
        BotCommand(command="add",       description="Yangi savol qo'shish (admin)"),
        BotCommand(command="start",     description="Botni ishga tushirish"),
    ])
    # /on, /off, /ruxsat — foydalanuvchi menyusida ko'rsatilmaydi (qo'shilmadi)

    # Webhook
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"Webhook set: {WEBHOOK_URL}")

    # Kunlik scheduler
    scheduler = AsyncIOScheduler(timezone=pytz.timezone("Asia/Tashkent"))
    scheduler.add_job(daily_reset, CronTrigger(hour=0, minute=0))
    scheduler.start()

# ---------- WEBHOOK ----------
@app.post(WEBHOOK_PATH)
async def webhook(request: Request):
    data   = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot=bot, update=update)
    return {"ok": True}

# ---------- ROOT ----------
@app.get("/")
async def root():
    return {"status": "Bot ishlayapti ✅", "commands": ["/boshla", "/rasm", "/ball", "/reyting"]}
