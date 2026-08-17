"""
Upstash Redis orqali doimiy saqlash (backup/restore) yordamchisi.

Mantiq:
  - Bot hamon local JSON fayllar bilan ishlayveradi (tez, sinxron, kodni
    o'zgartirish shart emas).
  - Har safar fayl saqlanganda (save_json/_save chaqirilganda), uning
    tarkibi orqa fonda (fire-and-forget) Upstash Redis'ga ham yuboriladi.
  - Bot ishga tushganda (startup), agar local fayl bo'sh/yo'q bo'lsa,
    Redis'dan oxirgi saqlangan nusxa tortib olinadi va local faylga
    yoziladi — shu orqali Render qayta deploy qilinganda (local fayl
    tizimi tozalanganda ham) ma'lumotlar yo'qolmaydi.

Agar UPSTASH_REDIS_REST_URL / TOKEN sozlanmagan bo'lsa, bu modul jim
o'chirilgan holatda ishlaydi (hech narsa qilmaydi) — bot avvalgidek
oddiy local fayllar bilan davom etadi.
"""
import os
import json
import logging
import asyncio

import aiohttp

log = logging.getLogger("storage")

UPSTASH_URL   = os.getenv("UPSTASH_REDIS_REST_URL", "").rstrip("/")
UPSTASH_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN", "")

ENABLED = bool(UPSTASH_URL and UPSTASH_TOKEN)

_HEADERS = {"Authorization": f"Bearer {UPSTASH_TOKEN}"}
_TIMEOUT = aiohttp.ClientTimeout(total=10)

if ENABLED:
    log.info("✅ Upstash Redis ulandi — ma'lumotlar deploy'da saqlanadi")
else:
    log.warning(
        "⚠️ UPSTASH_REDIS_REST_URL/TOKEN sozlanmagan — ma'lumotlar "
        "qayta deploy qilinganda yo'qolishi mumkin"
    )


async def _command(*args):
    """Upstash REST API'ga bitta Redis buyrug'ini yuboradi (body-style)."""
    async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
        async with session.post(
            UPSTASH_URL,
            headers=_HEADERS,
            data=json.dumps(list(args)),
        ) as resp:
            data = await resp.json()
            if "error" in data:
                raise RuntimeError(data["error"])
            return data.get("result")


def _key_for(filename: str) -> str:
    """Fayl nomini Redis kaliti sifatida ishlatish (yo'l qismisiz)."""
    return "file:" + os.path.basename(filename)


async def restore_file(filename: str):
    """
    Startup'da chaqiriladi: agar Redis'da shu fayl uchun saqlangan
    nusxa bo'lsa, uni local faylga yozadi (local fayl mavjud
    bo'lsa ham — Redis'dagi eng so'nggi holat ustunlik qiladi,
    chunki local fayl qayta deploy'dan keyin bo'sh boshlangan bo'ladi).
    """
    if not ENABLED:
        return
    try:
        raw = await _command("GET", _key_for(filename))
        if raw is None:
            log.info("Redis'da %s uchun zaxira topilmadi — bo'sh boshlanadi", filename)
            return
        with open(filename, "w", encoding="utf-8") as f:
            f.write(raw)
        log.info("✅ %s Redis'dan tiklandi", filename)
    except Exception as e:
        log.warning("restore_file(%s) xatolik: %s", filename, e)


async def _backup_now(filename: str):
    try:
        if not os.path.exists(filename):
            return
        with open(filename, "r", encoding="utf-8") as f:
            content = f.read()
        result = await _command("SET", _key_for(filename), content)
        if result != "OK":
            log.warning("backup_file(%s): kutilmagan natija: %s", filename, result)
    except Exception as e:
        log.warning("backup_file(%s) xatolik: %s", filename, e)


def backup_file(filename: str):
    """
    Fire-and-forget: faylni Redis'ga orqa fonda zaxiralaydi.
    Sinxron funksiyalardan ham xavfsiz chaqirish mumkin — chunki
    faqat ishlayotgan asyncio tsiklida (event loop) fon vazifasi
    sifatida rejalashtiriladi, natijani kutmaydi.
    """
    if not ENABLED:
        return
    try:
        asyncio.get_running_loop()
        asyncio.create_task(_backup_now(filename))
    except RuntimeError:
        # Ishlayotgan event loop topilmadi (masalan modul yuklanish vaqtida) — o'tkazib yuborish
        log.debug("backup_file(%s): faol event loop yo'q, o'tkazib yuborildi", filename)
