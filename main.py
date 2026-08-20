import logging
import os
import json
import random
import asyncio
import pathlib
from datetime import datetime

from aiogram import Bot, Dispatcher, Router, types, F, BaseMiddleware
from aiogram.filters import Command, CommandObject
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

_bot_id: int | None = None   # startup'da to'ldiriladi — har xabarda get_me() chaqirmaslik uchun

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
# Doimiy saqlash uchun: agar Render'da "Persistent Disk" ulangan bo'lsa,
# DATA_DIR shu diskka ishora qiladi va fayllar deploy/restartlarda yo'qolmaydi.
# Disk ulanmagan bo'lsa, joriy papkaga yoziladi (avvalgidek — deployda tozalanadi).
DATA_DIR = os.getenv("DATA_DIR", ".").rstrip("/")
pathlib.Path(DATA_DIR).mkdir(parents=True, exist_ok=True)

import storage

TESKARI_FILE = "teskari_tezlik_savollar.json"          # savollar bazasi — repo bilan birga keladi
ISLOM_FILE   = "islomiy_savollar.json"                  # /islom uchun alohida savollar bazasi
SCORE_FILE   = os.path.join(DATA_DIR, "user_scores.json")
STATE_FILE   = os.path.join(DATA_DIR, "user_states.json")
WINNER_FILE  = os.path.join(DATA_DIR, "winner_count.json")
MEMBERS_FILE = os.path.join(DATA_DIR, "guruh_azolari.json")   # @all/@all uchun bilingan a'zolar
TRACKED_FILE = os.path.join(DATA_DIR, "tekshiruv_royxati.json")  # /tekshir orqali kuzatilayotgan foydalanuvchilar
TABLO_FILE   = os.path.join(DATA_DIR, "tablo_reyting.json")       # /on /off — tablo rejimi holati

# Redis orqali doimiy zaxiralanadigan fayllar (foydalanuvchi ma'lumotlari)
_PERSISTED_FILES = [SCORE_FILE, STATE_FILE, WINNER_FILE, MEMBERS_FILE, TRACKED_FILE, TABLO_FILE]

# ---------- JSON ----------
def load_json(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    if filename in _PERSISTED_FILES:
        storage.backup_file(filename)   # orqa fonda Redis'ga zaxiralash (fire-and-forget)

# ---------- GURUH A'ZOLARI (@all uchun) ----------
# ⚠️ Telegram Bot API orqali guruhning TO'LIQ a'zolar ro'yxatini olib
# bo'lmaydi (faqat adminlar ro'yxati beriladi). Shuning uchun bot
# guruhda xabar yozgan har bir foydalanuvchini shu faylga qayd qilib
# boradi — @all faqat SHU tarzda "ko'rilgan" a'zolarni chaqira oladi,
# guruhning butun (masalan 210 kishilik) tarkibini emas.
def track_member(chat_id: int, user_id: int, name: str):
    try:
        members = load_json(MEMBERS_FILE)
        cid = str(chat_id)
        uid = str(user_id)
        if cid not in members:
            members[cid] = {}
        if members[cid].get(uid) != name:
            members[cid][uid] = name
            save_json(MEMBERS_FILE, members)
    except Exception as e:
        logging.warning(f"track_member xatolik: {e}")

class MemberTrackerMiddleware(BaseMiddleware):
    """Har bir guruh xabaridan jo'natuvchini guruh a'zolari ro'yxatiga qo'shadi
    va agar jo'natuvchi (yoki javob yozilgan kishi) /tekshir orqali kuzatuvda
    bo'lsa, xabarni adminga forward qiladi."""
    async def __call__(self, handler, event: types.Message, data):
        if (
            event.from_user
            and not event.from_user.is_bot
            and event.chat.type in ("group", "supergroup")
        ):
            track_member(event.chat.id, event.from_user.id, event.from_user.full_name)
            await _maybe_forward_tracked(event)
        return await handler(event, data)

async def _maybe_forward_tracked(message: types.Message):
    try:
        tracked = load_json(TRACKED_FILE)
        if not tracked:
            return

        sender_id  = str(message.from_user.id)
        reply_to   = message.reply_to_message
        replied_id = (
            str(reply_to.from_user.id)
            if reply_to and reply_to.from_user
            else None
        )

        is_direct = sender_id in tracked
        is_reply  = replied_id is not None and replied_id in tracked
        if not (is_direct or is_reply):
            return

        group_name  = message.chat.title or "noma'lum guruh"
        sender_name = message.from_user.full_name
        tag = "🔎 Kuzatilayotgan foydalanuvchi xabari" if is_direct else "✉️ Kuzatilayotgan foydalanuvchiga javob"

        header = (
            f"{tag}\n"
            f"👥 Guruh: {group_name}\n"
            f"👤 Kimdan: {sender_name} (id: {sender_id})"
        )
        await bot.send_message(ADMIN_ID, header)
        await bot.forward_message(
            chat_id=ADMIN_ID,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
        )
    except Exception as e:
        logging.warning(f"tekshir forward xatolik: {e}")

# Har bir kelgan xabarni (qaysi handler ushlashidan qat'iy nazar) guruh
# a'zolari ro'yxatiga yozib ketadi — @all funksiyasi shu ro'yxatga tayanadi.
dp.message.middleware(MemberTrackerMiddleware())

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
        global _bot_id
        if _bot_id is None:
            me = await bot.get_me()
            _bot_id = me.id
        member = await bot.get_chat_member(message.chat.id, _bot_id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False

async def is_user_admin(chat_id: int, user_id: int, bot: Bot) -> bool:
    """Xabar yozgan ODAM shu guruhda admin/egasi ekanini tekshiradi (bot emas)."""
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False

# ---------- TABLO REJIMI (/on /off /ball /recount) ----------
def _tablo_mark(text: str):
    """Matn faqat ✅ lardan yoki faqat ➕ lardan iboratmi — shunday boʻlsa
    (belgi_turi, nechta) qaytaradi, aks holda None."""
    t = text.replace(" ", "").strip()
    if not t:
        return None
    chars = set(t)
    if chars == {"✅"}:
        return ("plus", len(t))
    if chars == {"➕"}:
        return ("minus", len(t))
    return None

def _format_tablo_reyting(scores: dict, boshlovchi_name: str) -> str:
    items = sorted(scores.items(), key=lambda x: x[1]["score"], reverse=True)
    lines = [f"Boshlovchi: {boshlovchi_name}", "", "Xozirgi natijalar:", ""]
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    rank, prev_score = 0, None
    for i, (uid, data) in enumerate(items):
        if data["score"] != prev_score:
            rank = i + 1
            prev_score = data["score"]
        prefix = medals.get(rank, str(rank))
        lines.append(f"{prefix}  {data['name']} — {data['score']} ball")
    if not items:
        lines.append("(hali hech kimga ball berilmagan)")
    return "\n".join(lines)

# ---------- SEND QUESTION ----------
async def send_new_question(chat_id: int, bot: Bot, questions_file: str = TESKARI_FILE, label: str = "🔄 Toping"):
    questions = load_json(questions_file)
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
        "file":        questions_file,   # keyingi savol ham shu fayldan berilishi uchun
        "label":       label,
    }
    save_json(STATE_FILE, states)
    await bot.send_message(chat_id, f"{label}:\n{question['savol']}")

# ---------- /start ----------
@main_router.message(Command("start"))
async def start_cmd(message: types.Message, bot: Bot):
    await message.answer(
        "👋 Salom! Men <b>Teskari Tezlik</b> botiman.\n\n"
        "📋 <b>Mavjud komandalar:</b>\n"
        "/boshla — Teskari tezlik o'yinini boshlash\n"
        "/islom — 🕌 Islomiy savollar (Alloh ismlari, suralar va h.k.)\n"
        "/rasm — 🎨 Rasm chizish o'yinini boshlash\n"
        "/ball — Ballaringizni ko'rish\n"
        "/reyting — Global reyting (barcha guruhlar bo'yicha Top 10)\n"
        "/kun — Kun bilimdonlari ro'yxati (kim necha marta g'olib bo'lgan)\n"
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
    await send_new_question(message.chat.id, bot, TESKARI_FILE, "🔄 Toping")

# ---------- /islom ----------
@main_router.message(Command("islom"))
async def islom_cmd(message: types.Message, bot: Bot):
    if not await check_bot_admin(message, bot):
        await message.answer("❌ Botni admin qiling.")
        return
    await send_new_question(message.chat.id, bot, ISLOM_FILE, "🕌 Toping")

# ---------- /stop ----------
@main_router.message(Command("stop"))
async def stop_cmd(message: types.Message, bot: Bot, command: CommandObject):
    # --- Shaxsiy chatda "/stop <id>" — kuzatuvni to'xtatish ---
    if (
        message.chat.type == "private"
        and message.from_user.id == ADMIN_ID
        and command.args
        and command.args.strip().isdigit()
    ):
        uid = command.args.strip()
        tracked = load_json(TRACKED_FILE)
        if uid in tracked:
            del tracked[uid]
            save_json(TRACKED_FILE, tracked)
            await message.answer(f"🛑 {uid} ID'li foydalanuvchini kuzatish to'xtatildi.")
        else:
            await message.answer(f"ℹ️ {uid} hozir kuzatuvda emas edi.")
        return

    # --- aks holda: mavjud rasm o'yinini to'xtatish (guruhda) ---
    user = message.from_user
    chat_id = message.chat.id

    # Admin tekshiruvi: RUXSAT_ETILGANLAR yoki guruh admin
    is_allowed = user.id in RUXSAT_ETILGANLAR
    if not is_allowed and message.chat.type != "private":
        try:
            member = await bot.get_chat_member(chat_id, user.id)
            is_allowed = member.status in ("administrator", "creator")
        except Exception:
            pass

    if not is_allowed:
        await message.answer("❌ Faqat adminlar /stop buyrug'idan foydalana oladi.")
        return

    result = await rasm_oyini.stop_game(chat_id)

    if not result["stopped"]:
        await message.answer("ℹ️ Hozirda faol rasm o'yini yo'q.")
        return

    status_text = {
        "selecting":          "so'z tanlanmoqda edi",
        "custom_word_pending":"so'z kiritilmoqda edi",
        "waiting":            "rasm chizilmoqda edi",
        "submitted":          "javob kutilmoqda edi",
    }.get(result["status"], result["status"])

    word_info = f"\n📝 So'z: <b>{result['word']}</b>" if result.get("word") else ""
    await message.answer(
        f"🛑 <b>Admin tomonidan o'yin to'xtatildi.</b>\n\n"
        f"📊 Holat: {status_text}{word_info}\n\n"
        f"Yangi o'yin uchun /rasm yozing!",
        parse_mode="HTML",
    )

# ---------- /tekshir — foydalanuvchini kuzatish (faqat admin, shaxsiy chatda) ----------
@main_router.message(Command("tekshir"))
async def tekshir_cmd(message: types.Message, command: CommandObject):
    if message.chat.type != "private" or message.from_user.id != ADMIN_ID:
        return   # boshqa hech kimga bu buyruq borligi ham bildirilmaydi

    if not command.args or not command.args.strip().isdigit():
        await message.answer("Foydalanish: /tekshir <user_id>\nTo'xtatish: /stop <user_id>")
        return

    uid = command.args.strip()
    tracked = load_json(TRACKED_FILE)
    tracked[uid] = True
    save_json(TRACKED_FILE, tracked)
    await message.answer(
        f"✅ {uid} ID'li foydalanuvchi endi kuzatilmoqda.\n"
        f"Uning guruhlardagi xabarlari va unga yozilgan javoblar shu yerga forward qilinadi.\n"
        f"To'xtatish uchun: /stop {uid}"
    )

# ---------- /on — tablo rejimini yoqish ----------
@main_router.message(Command("on"))
async def tablo_on_cmd(message: types.Message):
    if message.chat.type not in ("group", "supergroup"):
        await message.answer("⚠️ Bu buyruq faqat guruhlarda ishlaydi.")
        return

    async with _get_tablo_lock(message.chat.id):
        chat_id = str(message.chat.id)
        tablo = load_json(TABLO_FILE)
        state = tablo.get(chat_id)
        if state and state.get("active"):
            await message.answer(
                f"⚠️ Tablo allaqachon faol (boshlovchi: {state.get('boshlovchi_name','?')}).\n"
                f"Avval /off bilan yakunlang."
            )
            return

        tablo[chat_id] = {
            "active": True,
            "boshlovchi_id": message.from_user.id,
            "boshlovchi_name": message.from_user.full_name,
            "boshlovchi_username": message.from_user.username,
            "ball_value": 5,
            "scores": {},
        }
        save_json(TABLO_FILE, tablo)
        boshlovchi_belgi = f'<a href="tg://user?id={message.from_user.id}">{message.from_user.full_name}</a>'
        await message.answer(
            f"📊 <b>Tablo yoqildi!</b>\n"
            f"👑 Boshlovchi: {boshlovchi_belgi}\n\n"
            f"Endi boshlovchi kimningdir xabariga <b>✅</b> (ball qo'shish) yoki "
            f"<b>➕</b> (ball ayirish) bilan javob (reply) qilib turadi.\n"
            f"Bitta belgi = {5} ball. O'zgartirish uchun: /ball <son>",
            parse_mode="HTML",
        )

# ---------- /recount — boshlovchilikni boshqasiga topshirish ----------
@main_router.message(Command("recount"))
async def tablo_recount_cmd(message: types.Message, bot: Bot):
    async with _get_tablo_lock(message.chat.id):
        chat_id = str(message.chat.id)
        tablo = load_json(TABLO_FILE)
        state = tablo.get(chat_id)
        if not state or not state.get("active"):
            await message.answer("ℹ️ Hozir faol tablo yo'q.")
            return

        is_boshlovchi = message.from_user.id == state.get("boshlovchi_id")
        is_admin = await is_user_admin(message.chat.id, message.from_user.id, bot)
        if not (is_boshlovchi or is_admin):
            await message.answer("❌ Faqat hozirgi boshlovchi yoki adminlar boshlovchilikni topshira oladi.")
            return

        if not message.reply_to_message or not message.reply_to_message.from_user:
            await message.answer("ℹ️ Boshlovchilikni kimga topshirmoqchi bo'lsangiz, o'sha kishining xabariga javob (reply) qilib /recount deb yozing.")
            return

        new_user = message.reply_to_message.from_user
        if new_user.is_bot:
            await message.answer("⚠️ Botga boshlovchilikni topshirib bo'lmaydi.")
            return

        state["boshlovchi_id"]   = new_user.id
        state["boshlovchi_name"] = new_user.full_name
        state["boshlovchi_username"] = new_user.username
        tablo[chat_id] = state
        save_json(TABLO_FILE, tablo)
        await message.answer(f"👑 Boshlovchilik endi {new_user.full_name}ga topshirildi.")

# ---------- /off — tablo rejimini yakunlash ----------
@main_router.message(Command("off"))
async def tablo_off_cmd(message: types.Message, bot: Bot):
    async with _get_tablo_lock(message.chat.id):
        chat_id = str(message.chat.id)
        tablo = load_json(TABLO_FILE)
        state = tablo.get(chat_id)
        if not state or not state.get("active"):
            await message.answer("ℹ️ Hozir faol tablo yo'q.")
            return

        is_boshlovchi = message.from_user.id == state.get("boshlovchi_id")
        is_admin = await is_user_admin(message.chat.id, message.from_user.id, bot)
        if not (is_boshlovchi or is_admin):
            await message.answer("❌ Faqat boshlovchi yoki adminlar tabloni yakunlay oladi.")
            return

        scores = state.get("scores", {})
        boshlovchi_name = state.get("boshlovchi_name", "Boshlovchi")

        if scores:
            winner_uid, winner_data = max(scores.items(), key=lambda x: x[1]["score"])
            text = (
                f"🏆 1-O'RIN SOHIBINI TABRIKLAYMIZ! 🥳\n\n"
                f'🥇 <a href="tg://user?id={winner_uid}">{winner_data["name"]}</a> — '
                f'{winner_data["score"]} ball! G\'alabangiz muborak bo\'lsin! '
                f"Bilimingiz va faolligingiz uchun tahsinga loyiqsiz! 👏\n\n"
                f"🎤 Boshlovchimiz <b>{boshlovchi_name}</b>ga o'yinni ajoyib olib borgani uchun, "
                f"barcha qatnashchilarga esa faol ishtiroki uchun katta rahmat! 🤝\n\n"
                f"🌟 Keyingi o'yinlarda barchangizga omad va yanada katta g'alabalar tilaymiz! 🎉"
            )
        else:
            text = (
                f"🛑 <b>Tablo yakunlandi.</b>\n\n"
                f"Bu safar hech kimga ball berilmadi.\n"
                f"🙏 Boshlovchi <b>{boshlovchi_name}</b>ga baribir rahmat!"
            )

        tablo[chat_id] = {"active": False}
        save_json(TABLO_FILE, tablo)
        await message.answer(text, parse_mode="HTML")

# ---------- /ball ----------
@main_router.message(Command("ball"))
async def ball_cmd(message: types.Message, command: CommandObject):
    # --- Guruhda faol tablo bo'lsa va boshlovchi "/ball <son>" yozsa —
    #     bitta ✅ ning qiymatini o'zgartiradi (bu tablo rejimiga xos) ---
    if message.chat.type in ("group", "supergroup") and command.args and command.args.strip().lstrip('-').isdigit():
        async with _get_tablo_lock(message.chat.id):
            chat_id = str(message.chat.id)
            tablo = load_json(TABLO_FILE)
            state = tablo.get(chat_id)
            if state and state.get("active") and message.from_user.id == state.get("boshlovchi_id"):
                val = int(command.args.strip())
                state["ball_value"] = val
                tablo[chat_id] = state
                save_json(TABLO_FILE, tablo)
                await message.answer(
                    f"✅ Endi bitta ✅ = {val} ball bo'ladi.\n"
                    f"(Bu allaqachon berilgan ballarga ta'sir qilmaydi, faqat keyingi belgilashlarga.)"
                )
                return

    if message.chat.type == "private":
        await message.answer("ℹ️ Ballaringizni ko'rish uchun bu buyruqni guruhda yozing.")
        return

    chat_id = str(message.chat.id)
    user_id = str(message.from_user.id)

    scores      = load_json(SCORE_FILE)
    teskari_ball = scores.get(chat_id, {}).get(user_id, 0)

    stars = load_json("drawing_star_scores.json")
    rasm_ball = stars.get(chat_id, {}).get(user_id, 0)

    await message.answer(
        f"📊 <b>{message.from_user.full_name}</b> uchun ballar:\n\n"
        f"⚡ Teskari tezlik: <b>{teskari_ball}</b> ball\n"
        f"🎨 Rasm chizish: <b>{rasm_ball}</b>🌟",
        parse_mode="HTML",
    )


# ---------- /reyting (GLOBAL) ----------
@main_router.message(Command("reyting"))
async def reyting_cmd(message: types.Message, bot: Bot):
    scores = load_json(SCORE_FILE)  # {chat_id: {user_id: ball}}

    # Har bir foydalanuvchining ENG YUQORI natijasini (qaysi guruhda bo'lsa ham) yig'amiz
    best: dict[str, tuple[int, str]] = {}   # user_id -> (ball, chat_id)
    for chat_id, chat_scores in scores.items():
        for user_id, ball in chat_scores.items():
            if user_id not in best or ball > best[user_id][0]:
                best[user_id] = (ball, chat_id)

    if not best:
        await message.answer("📊 Hali hech kim ball to'plamagan.")
        return

    top10  = sorted(best.items(), key=lambda x: x[1][0], reverse=True)[:10]
    medals = ["🥇", "🥈", "🥉"]
    lines  = []

    for i, (user_id, (ball, chat_id)) in enumerate(top10):
        try:
            member = await bot.get_chat_member(int(chat_id), int(user_id))
            name   = member.user.full_name
        except Exception:
            name = "👤 Noma'lum"
        try:
            chat       = await bot.get_chat(int(chat_id))
            group_name = chat.title or "noma'lum guruh"
        except Exception:
            group_name = "noma'lum guruh"

        prefix = medals[i] if i < 3 else "🔹"
        lines.append(
            f"{prefix} <b>{i+1}-o'rin:</b> {name} — <b>{ball}</b> ball "
            f"<i>({group_name} guruhidan)</i>"
        )

    text = (
        "🌍 <b>Global reyting (Top 10)</b>\n"
        "Barcha guruhlar bo'yicha eng kuchlilar:\n"
        "━━━━━━━━━━━━━━━━\n"
        + "\n".join(lines)
    )
    await message.answer(text, parse_mode="HTML")

# ---------- /add ----------
@main_router.message(Command("add"))
async def add_question_cmd(message: types.Message):
    if message.from_user.id not in RUXSAT_ETILGANLAR:
        await message.answer("❌ Sizda huquq yo'q.")
        return

    parts = (message.text or "").split(maxsplit=1)
    text  = parts[1] if len(parts) > 1 else ""
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

# ---------- /kun ----------
# MUHIM: bu handler pastdagi CATCH-ALL (F.text) dan OLDIN ro'yxatdan
# o'tishi shart — aks holda /kun xabari catch-all tomonidan ushlab
# qolinadi va bu yergacha hech qachon yetib kelmaydi.
@main_router.message(Command("kun"))
async def kun_cmd(message: types.Message):
    winner_count = load_json(WINNER_FILE)
    if not winner_count:
        await message.answer("📊 Hali hech kim kun bilimdoni bo'lmagan.")
        return

    def _count(entry):
        return entry.get("count", 0) if isinstance(entry, dict) else (entry or 0)

    def _name(entry):
        return entry.get("name", "👤 Nomaʼlum") if isinstance(entry, dict) else "👤 Nomaʼlum"

    top    = sorted(winner_count.items(), key=lambda x: _count(x[1]), reverse=True)[:15]
    medals = ["🥇", "🥈", "🥉"]
    lines  = []
    for i, (uid, entry) in enumerate(top):
        prefix = medals[i] if i < 3 else "🔹"
        lines.append(f"{prefix} {_name(entry)} — <b>{_count(entry)}</b> marta")

    text = (
        "🏆 <b>Kun bilimdonlari</b>\n"
        "Necha marta kun g'olibi bo'lganlar:\n"
        "━━━━━━━━━━━━━━━━\n"
        + "\n".join(lines)
    )
    await message.answer(text, parse_mode="HTML")

# ---------- @ALL / /ALL — HAMMANI CHAQIRISH ----------
TAG_BATCH_SIZE     = 5   # bitta xabarda nechta kishi chaqiriladi
TAG_DELAY_SECONDS  = 3   # xabarlar orasidagi tanaffus (flood limitdan qochish uchun)

_active_tags: dict[str, bool] = {}   # {chat_id: stop_so'ralganmi}

# Har bir guruh uchun /on /off /recount va ✅➕ amallarini KETMA-KET (bir
# vaqtning o'zida bittadan) ishlashini kafolatlaydi — Telegram webhook
# qayta yuborishi (retry) yoki bir vaqtda kelgan xabarlar sabab tablo
# holati "poyga holati" (race condition) tufayli buzilib qolmasligi uchun.
_tablo_locks: dict[str, asyncio.Lock] = {}

def _get_tablo_lock(chat_id) -> asyncio.Lock:
    cid = str(chat_id)
    if cid not in _tablo_locks:
        _tablo_locks[cid] = asyncio.Lock()
    return _tablo_locks[cid]

def _all_trigger_prefix(text: str) -> str | None:
    """Agar matn @all yoki /all bilan boshlansa, mos prefiksni qaytaradi."""
    t = text.strip().lower()
    for prefix in ("@all", "/all"):
        if t == prefix or t.startswith(prefix + " "):
            return prefix
    return None

def _is_all_trigger(message: types.Message) -> bool:
    return bool(message.text) and _all_trigger_prefix(message.text) is not None

@main_router.message(_is_all_trigger)
async def tag_all_cmd(message: types.Message, bot: Bot):
    if message.chat.type not in ("group", "supergroup"):
        await message.answer("⚠️ Bu buyruq faqat guruhlarda ishlaydi.")
        return

    chat_id = str(message.chat.id)
    if chat_id in _active_tags:
        await message.answer("⚠️ Hozir chaqiruv jarayoni allaqachon ketyapti. To'xtatish uchun !stop deb yozing.")
        return

    prefix  = _all_trigger_prefix(message.text)
    caption = message.text.strip()[len(prefix):].strip()   # trigger'dan keyingi matn (bo'lishi ham, bo'lmasligi ham mumkin)

    members = load_json(MEMBERS_FILE).get(chat_id, {})
    user_items = list(members.items())

    if not user_items:
        await message.answer(
            "😕 Hozircha chaqiriladigan a'zolar ro'yxati bo'sh.\n"
            "Bot faqat guruhda xabar yozgan a'zolarni \"ko'radi\" — "
            "a'zolar xabar yozgan sari ro'yxatga avtomatik qo'shilib boradi."
        )
        return

    _active_tags[chat_id] = False   # jarayon boshlandi, stop so'ralmagan
    total  = len(user_items)
    guruhlar = [user_items[i:i + TAG_BATCH_SIZE] for i in range(0, total, TAG_BATCH_SIZE)]

    await message.answer(f"📣 Chaqiruv boshlandi — jami {total} kishi. To'xtatish uchun !stop deb yozing.")

    try:
        for batch in guruhlar:
            if _active_tags.get(chat_id):
                await message.answer("🛑 Chaqiruv to'xtatildi.")
                return
            mentions = " ".join(
                f'<a href="tg://user?id={uid}">{name}</a>' for uid, name in batch
            )
            body = f"{caption}\n{mentions}" if caption else mentions
            try:
                await bot.send_message(int(chat_id), body, parse_mode="HTML")
            except Exception as e:
                logging.warning(f"tag_all: xabar yuborilmadi chat={chat_id}: {e}")
            await asyncio.sleep(TAG_DELAY_SECONDS)
        await message.answer("✅ Chaqiruv yakunlandi — barcha bilingan a'zolar chaqirildi.")
    finally:
        _active_tags.pop(chat_id, None)

@main_router.message(F.text == "!stop")
async def stop_tag_cmd(message: types.Message):
    chat_id = str(message.chat.id)
    if chat_id in _active_tags:
        _active_tags[chat_id] = True
        await message.answer("⏳ Chaqiruv to'xtatilmoqda...")
    else:
        await message.answer("Hozir faol chaqiruv jarayoni yo'q.")

# ---------- ✅ / ➕ — TABLO BALL BELGILASH ----------
def _is_tablo_mark_message(message: types.Message) -> bool:
    return (
        bool(message.text)
        and message.reply_to_message is not None
        and message.reply_to_message.from_user is not None
        and _tablo_mark(message.text) is not None
    )

@main_router.message(_is_tablo_mark_message)
async def tablo_mark_cmd(message: types.Message):
    async with _get_tablo_lock(message.chat.id):
        chat_id = str(message.chat.id)
        tablo = load_json(TABLO_FILE)
        state = tablo.get(chat_id)
        if not state or not state.get("active"):
            return   # tablo faol emas — bu belgilarga umuman e'tibor berilmaydi
        if message.from_user.id != state.get("boshlovchi_id"):
            return   # boshlovchi bo'lmagan odam yozsa — e'tiborsiz qoldiriladi

        kind, count = _tablo_mark(message.text)
        ball_value = state.get("ball_value", 5)
        delta = count * ball_value
        if kind == "minus":
            delta = -delta

        target = message.reply_to_message.from_user
        if target.is_bot:
            return

        uid = str(target.id)
        scores = state.setdefault("scores", {})
        entry = scores.setdefault(uid, {"name": target.full_name, "score": 0})
        entry["name"] = target.full_name
        entry["score"] += delta
        tablo[chat_id] = state
        save_json(TABLO_FILE, tablo)

        harakat = "ball qo'shildi" if delta >= 0 else "ball ayirildi"
        await message.answer(
            f'<a href="tg://user?id={uid}">{target.full_name}</a>ga {abs(delta)} {harakat}',
            parse_mode="HTML",
        )
        await message.answer(_format_tablo_reyting(scores, state.get("boshlovchi_name", "")))

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
        await send_new_question(
            message.chat.id, bot,
            state.get("file", TESKARI_FILE),
            state.get("label", "🔄 Toping"),
        )

# ---------- DAILY WINNER (GLOBAL) ----------
async def daily_reset():
    scores       = load_json(SCORE_FILE)      # {chat_id: {user_id: ball}}
    winner_count = load_json(WINNER_FILE)     # {user_id: {"count": N, "name": "..."}}

    # Barcha guruhlar bo'yicha ENG YUQORI natijani (yagona global g'olibni) topamiz
    best = None   # (ball, chat_id, user_id)
    for chat_id, users in scores.items():
        if not users:
            continue
        user_id, ball = max(users.items(), key=lambda x: x[1])
        if best is None or ball > best[0]:
            best = (ball, chat_id, user_id)

    if not best:
        save_json(SCORE_FILE, {})
        return

    max_score, winner_chat_id, winner_id = best

    try:
        member = await bot.get_chat_member(int(winner_chat_id), int(winner_id))
        name   = member.user.first_name
    except Exception:
        name = "👤 Nomaʼlum"

    try:
        chat       = await bot.get_chat(int(winner_chat_id))
        group_name = chat.title or "noma'lum guruh"
    except Exception:
        group_name = "noma'lum guruh"

    msg = (
        "🌟━━━━━━━━━━━━━━━━🌟\n"
        "🏆 KUN BILIMDONI 🏆\n"
        "🌟━━━━━━━━━━━━━━━━🌟\n"
        f"🥇 G'olib: {name}\n"
        f"👥 Guruh: {group_name}\n"
        f"📊 Ball: {max_score}\n"
        f"🎊 {name}ni bugungi g'alabasi bilan chin qalbdan tabriklaymiz!\n"
        "💫 Bilim va zukkolik yo'lida yanada ulkan zafarlar tilaymiz! 🏆👏"
    )

    # Xabar BARCHA faol guruhlarga yuboriladi (bir xil, global g'olib bilan)
    for chat_id in scores.keys():
        try:
            await bot.send_message(int(chat_id), msg)
        except Exception as e:
            logging.warning(f"daily_reset: xabar yuborilmadi chat={chat_id}: {e}")

    entry = winner_count.get(str(winner_id))
    if not isinstance(entry, dict):   # eski formatdagi (raqam) yozuvni ham qo'llab-quvvatlash
        entry = {"count": entry or 0, "name": name}
    entry["count"] = entry.get("count", 0) + 1
    entry["name"]  = name   # eng so'nggi ma'lum ismni saqlab boramiz
    winner_count[str(winner_id)] = entry

    save_json(WINNER_FILE, winner_count)
    save_json(SCORE_FILE, {})

# ---------- STARTUP ----------
@app.on_event("startup")
async def startup():
    # Redis'da saqlangan oxirgi nusxalarni local fayllarga tiklash
    # (Render qayta deploy qilganda local fayl tizimi bo'sh boshlanadi)
    for f in _PERSISTED_FILES:
        await storage.restore_file(f)
    for f in rasm_oyini.persisted_files():
        await storage.restore_file(f)

    # rasm_oyini ga bot havolasini berish va FastAPI routelarini qo'shish
    await rasm_oyini.setup_fastapi(bot=bot, app=app)

    # Bot "/" menyusida ko'rinadigan komandalar
    await bot.set_my_commands([
        BotCommand(command="boshla",  description="Teskari tezlik o'yinini boshlash"),
        BotCommand(command="islom",   description="🕌 Islomiy savollar"),
        BotCommand(command="rasm",    description="🎨 Rasm chizish o'yinini boshlash"),
        BotCommand(command="reyting", description="🌍 Global reyting (Top 10)"),
        BotCommand(command="kun",     description="🏆 Kun bilimdonlari ro'yxati"),
        BotCommand(command="all",     description="📣 Guruhdagi barchani chaqirish"),
        BotCommand(command="on",      description="📊 Tablo rejimini yoqish"),
        BotCommand(command="off",     description="🛑 Tablo rejimini yakunlash"),
        BotCommand(command="recount", description="👑 Boshlovchilikni topshirish"),
        BotCommand(command="ball",    description="Ballaringizni ko'rish"),
        BotCommand(command="stop",    description="Faol o'yinni to'xtatish (admin)"),
        BotCommand(command="add",     description="Yangi savol qo'shish (admin)"),
        BotCommand(command="start",   description="Botni ishga tushirish"),
    ])
    # /on, /off, /ruxsat — foydalanuvchi menyusida ko'rsatilmaydi (qo'shilmadi)

    # Webhook
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"Webhook set: {WEBHOOK_URL}")

    # Kunlik scheduler
    tz        = pytz.timezone("Asia/Tashkent")
    scheduler = AsyncIOScheduler(timezone=tz)
    # CronTrigger'ga ham aniq timezone berish shart — aks holda u
    # scheduler emas, balki server (UTC) vaqtidan foydalanadi.
    scheduler.add_job(daily_reset, CronTrigger(hour=0, minute=0, timezone=tz))
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
