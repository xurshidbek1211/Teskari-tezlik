# Teskari Tezlik Bot

Telegram bot — "Teskari tezlik" (teskari yozilgan so'zlarni topish) va rasm chizish o'yinlari.

## Run & Operate

- `uvicorn main:app --host 0.0.0.0 --port 8000 --reload` — botni ishga tushirish
- Required env: `API_TOKEN` — Telegram bot tokeni (BotFather'dan olish)

## Stack

- Python 3.12
- FastAPI + uvicorn (web server)
- aiogram 3.x (Telegram bot framework)
- APScheduler (kunlik reset)
- JSON fayllar (ma'lumotlar saqlash)

## Where things live

- `main.py` — asosiy bot logikasi (teskari tezlik o'yini)
- `rasm_oyini.py` — rasm chizish o'yini moduli
- `static/draw.html` — rasm chizish Telegram Mini App
- `teskari_tezlik_savollar.json` — o'yin savollari bazasi
- `rasm_sozlar.json` — rasm o'yini so'zlari bazasi
- `user_scores.json` — foydalanuvchi ballari
- `user_states.json` — o'yin holatlari
- `winner_count.json` — g'oliblar hisobi

## Architecture decisions

- Webhook orqali ishlaydi (polling emas) — Render/Replit uchun mos
- `rasm_router` main_router'dan OLDIN qo'shiladi — Command filtrlari to'g'ri ishlashi uchun
- Har kuni yarim tunda (Toshkent vaqti) balllar reset qilinadi va g'olib e'lon qilinadi

## User preferences

_Populate as you build._

## Gotchas

- `API_TOKEN` environment variable o'rnatilmasa bot ishlamaydi
- Webhook URL avtomatik aniqlanadi: Render uchun `RENDER_EXTERNAL_URL`, Replit uchun `REPLIT_DEV_DOMAIN`
