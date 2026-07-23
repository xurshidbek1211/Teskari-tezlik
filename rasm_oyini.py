"""
Rasm chizish o'yini moduli — Teskari Tezlik boti uchun.
aiogram 3.x + FastAPI. Mavjud arxitekturaga mos, modular.
"""

import os
import json
import random
import uuid
import hmac
import hashlib
import logging
import pathlib
import io
from datetime import datetime
from urllib.parse import parse_qs

from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, BotCommand
)

log = logging.getLogger(__name__)

# ── Modul darajasida bot havolasi (setup() tomonidan o'rnatiladi) ─────────────
_bot: Bot | None = None

# ─── FAYLLAR ──────────────────────────────────────────────────────────────────
WORDS_FILE       = "rasm_sozlar.json"
DRAW_STATE_FILE  = "drawing_game_states.json"
DRAW_LIKES_FILE  = "drawing_likes.json"
DRAW_SCORES_FILE = "drawing_star_scores.json"

# ─── JSON YORDAMCHILAR ────────────────────────────────────────────────────────
def _load(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def _save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ─── SO'ZLAR BAZASI ───────────────────────────────────────────────────────────
def _get_all_words():
    db = _load(WORDS_FILE)
    words = []
    for cat_data in db.values():
        for level_words in cat_data.get("qiyinlik", {}).values():
            words.extend(level_words)
    return words

def _random_word(exclude: list = None):
    all_words = _get_all_words()
    exclude   = exclude or []
    available = [w for w in all_words if w not in exclude]
    if not available:
        available = all_words
    return random.choice(available)

# ─── HOLAT BOSHQARUVI ─────────────────────────────────────────────────────────
def _get_state(chat_id):
    return _load(DRAW_STATE_FILE).get(str(chat_id))

def _set_state(chat_id, data):
    states = _load(DRAW_STATE_FILE)
    if data is None:
        states.pop(str(chat_id), None)
    else:
        states[str(chat_id)] = data
    _save(DRAW_STATE_FILE, states)

def _clear_state(chat_id):
    _set_state(chat_id, None)

# ─── LAYK TIZIMI ──────────────────────────────────────────────────────────────
def _add_like(message_id, chat_id, liker_id, drawer_id):
    likes = _load(DRAW_LIKES_FILE)
    key   = f"{chat_id}_{message_id}"
    entry = likes.get(key, {"likers": [], "drawer_id": str(drawer_id)})
    entry["drawer_id"] = str(drawer_id)
    if str(liker_id) not in entry["likers"]:
        entry["likers"].append(str(liker_id))
        likes[key] = entry
        _save(DRAW_LIKES_FILE, likes)
        return True
    return False

# ─── YULDUZ BALL TIZIMI ───────────────────────────────────────────────────────
def _add_star(chat_id, user_id):
    scores = _load(DRAW_SCORES_FILE)
    cid    = str(chat_id)
    uid    = str(user_id)
    if cid not in scores:
        scores[cid] = {}
    scores[cid][uid] = scores[cid].get(uid, 0) + 1
    _save(DRAW_SCORES_FILE, scores)
    return scores[cid][uid]

# ─── TELEGRAM initData HMAC TEKSHIRUVI ───────────────────────────────────────
def _verify_init_data(init_data: str, bot_token: str) -> dict | None:
    try:
        parsed = {k: v[0] for k, v in parse_qs(init_data, keep_blank_values=True).items()}
        received_hash = parsed.pop("hash", None)
        if not received_hash:
            return None
        data_check = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
        secret     = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        computed   = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
        if hmac.compare_digest(computed, received_hash):
            return parsed
        return None
    except Exception as e:
        log.warning("initData verify error: %s", e)
        return None

def _user_id_from_init_data(init_data: str) -> str | None:
    bot_token = os.getenv("API_TOKEN", "")
    verified  = _verify_init_data(init_data, bot_token) if init_data else None
    if not verified:
        return None
    try:
        user_json = verified.get("user", "{}")
        u = json.loads(user_json)
        return str(u.get("id"))
    except Exception:
        return None

# ─── INLINE KLAVIATURALAR ────────────────────────────────────────────────────
def _base_url() -> str:
    url = os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
    if url:
        return url
    dev = os.getenv("REPLIT_DEV_DOMAIN", "").strip()
    return f"https://{dev}" if dev else ""

def _start_keyboard(chat_id: int, session_id: str) -> InlineKeyboardMarkup:
    base_url = _base_url()
    draw_url = f"{base_url}/draw?session={session_id}&chat_id={chat_id}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 Chizishni boshlash",
                              web_app=WebAppInfo(url=draw_url))],
        [InlineKeyboardButton(text="✍️ O'z so'zimni kiritish",
                              callback_data=f"draw_custom:{chat_id}:{session_id}")],
        [InlineKeyboardButton(text="ℹ️ Qanday chizish kerak?",
                              callback_data=f"draw_help:{chat_id}")],
    ])

def _result_keyboard(chat_id: int, message_id: int, drawer_id, session_id: str) -> InlineKeyboardMarkup:
    base_url = _base_url()
    draw_url = f"{base_url}/draw?session={session_id}&chat_id={chat_id}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👍 Layk",
                                 callback_data=f"draw_like:{chat_id}:{message_id}:{drawer_id}"),
            InlineKeyboardButton(text="✋ Chizishni xohlayman!",
                                 callback_data=f"draw_want:{chat_id}"),
        ],
        [InlineKeyboardButton(text="⏳🎨 Yangi o'yin",
                              callback_data=f"draw_restart:{chat_id}")],
    ])

# ─── ROUTER ───────────────────────────────────────────────────────────────────
rasm_router = Router()

# /rasm komandasi
@rasm_router.message(Command("rasm"))
async def cmd_rasm(message: types.Message, bot: Bot):
    chat_id    = message.chat.id
    user       = message.from_user
    session_id = str(uuid.uuid4())
    word       = _random_word()

    _set_state(chat_id, {
        "session_id":         session_id,
        "drawer_id":          str(user.id),
        "drawer_name":        user.full_name,
        "word":               word,
        "status":             "waiting",
        "game_message_id":    None,
        "drawing_message_id": None,
        "used_words":         [word],
        "custom_word":        False,
        "want_queue":         [],
    })

    kb   = _start_keyboard(chat_id, session_id)
    sent = await message.answer(
        f"🎨 <b>Rasm chizish o'yini!</b>\n\n"
        f"🖊️ <b>Chizuvchi:</b> {user.full_name}\n\n"
        f"🎨 Chizishni boshlash tugmasini bosing va so'zni chizing.\n"
        f"👥 Boshqa o'yinchilar rasmga qarab so'zni topadi!",
        reply_markup=kb,
        parse_mode="HTML",
    )
    state = _get_state(chat_id)
    if state:
        state["game_message_id"] = sent.message_id
        _set_state(chat_id, state)

# ℹ️ Qanday chizish kerak?
@rasm_router.callback_query(F.data.startswith("draw_help:"))
async def cb_draw_help(query: types.CallbackQuery):
    await query.answer(
        "ℹ️ Rasm chizish qoidalari:\n\n"
        "1️⃣ 🎨 Chizishni boshlash ni bosing\n"
        "2️⃣ 👀 Ko'rish orqali so'zingizni ko'ring\n"
        "3️⃣ ✏️ So'zni rasmda chizing\n"
        "4️⃣ 📤 Yuborish ni bosing\n"
        "5️⃣ Boshqalar rasmga qarab so'zni topadi!\n\n"
        "💡 So'zni yozib bo'lmaydi!",
        show_alert=True,
    )

# ✍️ O'z so'zimni kiritish
@rasm_router.callback_query(F.data.startswith("draw_custom:"))
async def cb_draw_custom(query: types.CallbackQuery, bot: Bot):
    parts      = query.data.split(":")
    chat_id    = int(parts[1])
    session_id = parts[2]

    state = _get_state(chat_id)
    if not state or state.get("session_id") != session_id:
        await query.answer("❌ Sessiya topilmadi.", show_alert=True)
        return
    if str(query.from_user.id) != state.get("drawer_id"):
        await query.answer("❌ Faqat chizuvchi o'z so'zini kirita oladi.", show_alert=True)
        return

    state["status"]      = "custom_word_pending"
    state["custom_word"] = True
    _set_state(chat_id, state)

    try:
        await bot.send_message(
            query.from_user.id,
            "✍️ Chizmoqchi bo'lgan so'zingizni yozing:\n\n"
            "Masalan: Ferrari, Ajdarho, Eiffel minorasi\n\n"
            "(Guruhga qaytib, o'yin davom etadi)",
        )
        await query.answer("✅ Shaxsiy chatga xabar yubordik!")
    except Exception:
        await query.answer(
            "⚠️ Avval botga /start yuboring, so'ng qaytadan urinib ko'ring.",
            show_alert=True,
        )

# 👍 Layk
@rasm_router.callback_query(F.data.startswith("draw_like:"))
async def cb_draw_like(query: types.CallbackQuery, bot: Bot):
    parts      = query.data.split(":")
    chat_id    = int(parts[1])
    message_id = int(parts[2])
    drawer_id  = int(parts[3])
    liker      = query.from_user

    if liker.id == drawer_id:
        await query.answer("❌ O'z rasmingizga layk bosa olmaysiz.", show_alert=True)
        return

    added = _add_like(message_id, chat_id, liker.id, drawer_id)
    if not added:
        await query.answer("❌ Siz allaqachon bu rasmga layk berdingiz.", show_alert=True)
        return

    total_stars = _add_star(chat_id, drawer_id)
    await bot.send_message(
        chat_id,
        f"👍 <b>{liker.full_name}</b> rasmni baholadi. +1⭐\n"
        f"🌟 Chizuvchining umumiy yulduzlari: {total_stars}⭐",
        parse_mode="HTML",
    )
    await query.answer("👍 Layk qabul qilindi!")

# ✋ Chizishni xohlayman
@rasm_router.callback_query(F.data.startswith("draw_want:"))
async def cb_draw_want(query: types.CallbackQuery):
    chat_id = int(query.data.split(":")[1])
    user    = query.from_user
    state   = _get_state(chat_id)

    if not state:
        await query.answer("Hozircha o'yin yo'q. /rasm bilan boshlang!")
        return
    if str(user.id) == state.get("drawer_id"):
        await query.answer("Siz hozir chizuvchisiz!", show_alert=True)
        return

    queue = state.get("want_queue", [])
    uid   = str(user.id)
    if uid not in [q["id"] for q in queue]:
        queue.append({"id": uid, "name": user.full_name})
        state["want_queue"] = queue
        _set_state(chat_id, state)
        await query.answer(f"✋ Navbatga qo'shildingiz! ({len(queue)}-o'rinda)", show_alert=True)
    else:
        await query.answer("Siz allaqachon navbatdasiz!", show_alert=True)

# ⏳🎨 Yangi o'yin
@rasm_router.callback_query(F.data.startswith("draw_restart:"))
async def cb_draw_restart(query: types.CallbackQuery, bot: Bot):
    chat_id = int(query.data.split(":")[1])
    state   = _get_state(chat_id)

    want_queue = state.get("want_queue", []) if state else []
    _clear_state(chat_id)

    user = query.from_user
    if want_queue:
        nxt         = want_queue.pop(0)
        drawer_id   = nxt["id"]
        drawer_name = nxt["name"]
    else:
        drawer_id   = str(user.id)
        drawer_name = user.full_name

    session_id = str(uuid.uuid4())
    word       = _random_word()

    _set_state(chat_id, {
        "session_id":         session_id,
        "drawer_id":          str(drawer_id),
        "drawer_name":        drawer_name,
        "word":               word,
        "status":             "waiting",
        "game_message_id":    None,
        "drawing_message_id": None,
        "used_words":         [word],
        "custom_word":        False,
        "want_queue":         want_queue,
    })

    kb   = _start_keyboard(chat_id, session_id)
    sent = await bot.send_message(
        chat_id,
        f"🎨 <b>Yangi o'yin boshlanadi!</b>\n\n"
        f"🖊️ <b>Chizuvchi:</b> {drawer_name}\n\n"
        f"🎨 Chizishni boshlash tugmasini bosing va so'zni chizing.\n"
        f"👥 Boshqa o'yinchilar rasmga qarab so'zni topadi!",
        reply_markup=kb,
        parse_mode="HTML",
    )
    st2 = _get_state(chat_id)
    if st2:
        st2["game_message_id"] = sent.message_id
        _set_state(chat_id, st2)

    await query.answer("✅ Yangi o'yin boshlandi!")

# ─── GURUHDA RASM JAVOB TEKSHIRUVI ───────────────────────────────────────────
async def check_drawing_answer(message: types.Message, bot: Bot) -> bool:
    """
    Guruhda yuborilgan xabarni rasm o'yini uchun tekshiradi.
    To'g'ri javob bo'lsa True qaytaradi.
    """
    chat_id = message.chat.id
    state   = _get_state(chat_id)

    if not state or state.get("status") != "submitted":
        return False

    user = message.from_user
    if str(user.id) == state.get("drawer_id"):
        return False

    user_answer  = (message.text or "").strip().lower()
    correct_word = state.get("word", "").strip().lower()

    if user_answer != correct_word:
        return False

    # ✅ To'g'ri javob!
    drawer_name = state.get("drawer_name", "Chizuvchi")
    drawer_id   = state.get("drawer_id")
    word        = state.get("word")
    session_id  = state.get("session_id")
    draw_msg_id = state.get("drawing_message_id", 0)

    state["status"]    = "answered"
    state["winner_id"] = str(user.id)
    _set_state(chat_id, state)

    kb = _result_keyboard(chat_id, draw_msg_id, drawer_id, session_id)
    await message.answer(
        f"🎯 <b>To'g'ri javob!</b>\n\n"
        f"🖼️ So'z: <b>{word}</b>\n"
        f"🏆 Topdi: <b>{user.full_name}</b>\n"
        f"🎨 Chizgan: <b>{drawer_name}</b>\n\n"
        f"👍 Rasmni yoqtirgan bo'lsangiz layk bering — chizuvchi ⭐ oladi!",
        reply_markup=kb,
        parse_mode="HTML",
    )
    return True

# ─── SHAXSIY CHATDA SO'Z QABUL QILISH ────────────────────────────────────────
async def handle_private_custom_word(message: types.Message) -> bool:
    """
    Foydalanuvchi shaxsiy chatda o'z so'zini yuborsa,
    tegishli guruh sessiyasini yangilaydi. True qaytarsa — boshqa handler ishlamasin.
    """
    if message.chat.type != "private":
        return False

    user_id = str(message.from_user.id)
    states  = _load(DRAW_STATE_FILE)

    found_chat = None
    for cid, st in states.items():
        if (
            st.get("drawer_id") == user_id
            and st.get("status") == "custom_word_pending"
        ):
            found_chat = cid
            break

    if not found_chat:
        return False

    custom_word = (message.text or "").strip()
    if not custom_word or len(custom_word) > 50:
        await message.answer("❌ So'z juda uzun yoki bo'sh. Qaytadan yuboring.")
        return True

    state = states[found_chat]
    used  = state.get("used_words", [])
    used.append(custom_word)
    state.update({
        "word":        custom_word,
        "status":      "waiting",
        "custom_word": True,
        "used_words":  used,
    })
    _set_state(int(found_chat), state)

    await message.answer(
        f"✅ So'zingiz qabul qilindi: <b>{custom_word}</b>\n\n"
        "Endi guruhga qaytib rasmni chizishni boshlang!",
        parse_mode="HTML",
    )
    return True

# ─── FASTAPI ENDPOINTLAR ──────────────────────────────────────────────────────
async def _api_draw_word(request):
    from fastapi.responses import JSONResponse
    params     = request.query_params
    session_id = params.get("session")
    chat_id    = params.get("chat_id")
    init_data  = params.get("init_data", "")

    if not session_id or not chat_id:
        return JSONResponse({"error": "missing params"}, status_code=400)

    state = _get_state(int(chat_id))
    if not state or state.get("session_id") != session_id:
        return JSONResponse({"error": "session not found"}, status_code=404)

    user_id = _user_id_from_init_data(init_data)
    if user_id and user_id != state.get("drawer_id"):
        return JSONResponse({"error": "forbidden"}, status_code=403)

    return JSONResponse({
        "word":      state.get("word", ""),
        "status":    state.get("status"),
        "drawer_id": state.get("drawer_id"),
    })

async def _api_draw_new_word(request):
    from fastapi.responses import JSONResponse
    params     = request.query_params
    session_id = params.get("session")
    chat_id    = params.get("chat_id")
    init_data  = params.get("init_data", "")

    if not session_id or not chat_id:
        return JSONResponse({"error": "missing params"}, status_code=400)

    chat_id = int(chat_id)
    state   = _get_state(chat_id)
    if not state or state.get("session_id") != session_id:
        return JSONResponse({"error": "session not found"}, status_code=404)

    user_id = _user_id_from_init_data(init_data)
    if user_id and user_id != state.get("drawer_id"):
        return JSONResponse({"error": "forbidden"}, status_code=403)

    used     = state.get("used_words", [])
    new_word = _random_word(exclude=used)
    used.append(new_word)
    state["word"]       = new_word
    state["used_words"] = used
    _set_state(chat_id, state)

    return JSONResponse({"word": new_word})

async def _api_draw_submit(request):
    from fastapi.responses import JSONResponse
    import base64

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid json"}, status_code=400)

    session_id = body.get("session_id")
    chat_id    = body.get("chat_id")
    init_data  = body.get("init_data", "")
    image_b64  = body.get("image_base64", "")

    if not session_id or not chat_id or not image_b64:
        return JSONResponse({"error": "missing fields"}, status_code=400)

    chat_id = int(chat_id)
    state   = _get_state(chat_id)
    if not state or state.get("session_id") != session_id:
        return JSONResponse({"error": "session not found"}, status_code=404)

    user_id = _user_id_from_init_data(init_data)
    if user_id and user_id != state.get("drawer_id"):
        return JSONResponse({"error": "forbidden"}, status_code=403)

    try:
        if "," in image_b64:
            image_b64 = image_b64.split(",", 1)[1]
        image_bytes = base64.b64decode(image_b64)
    except Exception as e:
        return JSONResponse({"error": f"image decode error: {e}"}, status_code=400)

    if not _bot:
        return JSONResponse({"error": "bot not ready"}, status_code=503)

    drawer_name = state.get("drawer_name", "Chizuvchi")
    drawer_id   = state.get("drawer_id")
    session_id  = state.get("session_id")

    try:
        photo_file      = io.BytesIO(image_bytes)
        photo_file.name = "drawing.png"

        # Placeholder keyboard (message_id keyin aniqlanadi)
        ph_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👍 Layk",
                                  callback_data=f"draw_like:{chat_id}:0:{drawer_id}"),
             InlineKeyboardButton(text="✋ Chizishni xohlayman!",
                                  callback_data=f"draw_want:{chat_id}")],
        ])

        sent = await _bot.send_photo(
            chat_id,
            photo=photo_file,
            caption=(
                f"🎨 <b>{drawer_name}</b> rasm chizdi!\n\n"
                "🤔 Bu nima? Rasmga qarab so'zni toping va yozing!"
            ),
            reply_markup=ph_kb,
            parse_mode="HTML",
        )

        # Haqiqiy message_id bilan keyboard yangilash
        real_kb = _result_keyboard(chat_id, sent.message_id, drawer_id, session_id)
        await _bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=sent.message_id,
            reply_markup=real_kb,
        )

        state["status"]             = "submitted"
        state["drawing_message_id"] = sent.message_id
        _set_state(chat_id, state)

        return JSONResponse({"ok": True, "message_id": sent.message_id})

    except Exception as e:
        log.error("draw submit error: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)

async def _serve_draw(request):
    from fastapi.responses import FileResponse
    return FileResponse("static/draw.html")

# ─── SETUP ────────────────────────────────────────────────────────────────────
def setup(bot: Bot, app, dp: Dispatcher):
    """
    main.py startup() ichidan chaqiriladi.
    Routerni va FastAPI endpointlarini ro'yxatdan o'tkazadi.
    """
    global _bot
    _bot = bot

    # Aiogram router
    dp.include_router(rasm_router)

    # FastAPI endpointlar
    app.add_route("/api/draw/word",     _api_draw_word,     methods=["GET"])
    app.add_route("/api/draw/new_word", _api_draw_new_word, methods=["GET"])
    app.add_route("/api/draw/submit",   _api_draw_submit,   methods=["POST"])
    app.add_route("/draw",              _serve_draw,        methods=["GET"])

    # Static papka
    pathlib.Path("static").mkdir(exist_ok=True)
    log.info("✅ rasm_oyini moduli sozlandi")
