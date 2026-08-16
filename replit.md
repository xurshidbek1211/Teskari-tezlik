# Teskari Tezlik Bot

Telegram bot — “Teskari tezlik” (teskari yozilgan so‘zlarni topish) va rasm
chizish o‘yinlari.

## Run & Operate

- `uvicorn main:app --host 0.0.0.0 --port 8000 --reload` — botni ishga
  tushirish
- Required env: `API_TOKEN` — BotFather’dan olingan Telegram bot tokeni
- `RENDER_EXTERNAL_URL` — Render webhook URL manzili

## Stack

- Python 3.12
- FastAPI + uvicorn (webhook server va Mini App)
- aiogram 3.x (Telegram bot framework)
- APScheduler (kunlik reset va g‘olib e’loni)
- JSON fayllar (ma’lumotlar saqlash)

## O‘yinlar

### Teskari Tezlik

- `/boshla` — teskari yozilgan so‘zni topish
- `/add savol || javob` — yangi savol qo‘shish (admin)

### Rasm Chizish O‘yini

- `/rasm` — Paint’ga o‘xshash veb-interfeysda so‘z chizish
- Telegram Mini App orqali ishlaydi
- Layk tizimi: `+1⭐` chizuvchiga

## Loyiha haqida

- `main.py` — asosiy bot logikasi
- `rasm_oyini.py` — rasm chizish o‘yini moduli
- `static/draw.html` — rasm chizish Telegram Mini App
- `teskari_tezlik_savollar.json` — savollar bazasi
- `rasm_sozlar.json` — rasm o‘yini so‘zlari bazasi
- `user_scores.json` — foydalanuvchi ballari
- `user_states.json` — o‘yin holatlari
- `winner_count.json` — g‘oliblar hisobi
- `render.yaml` — Render deploy konfiguratsiyasi
- `requirements.txt` — Python paketlari

## Ishlash xususiyatlari

- Webhook orqali ishlaydi — Render va Replit uchun mos
- `rasm_router` `main_router`dan oldin qo‘shiladi, shuning uchun command
  filtrlari to‘g‘ri ishlaydi
- Har kuni yarim tunda Toshkent vaqti bilan ballar reset qilinadi va g‘olib
  e’lon qilinadi

## User preferences

- Bot kodi o‘zbek tilida, mavjud JSON fayl tizimi saqlanadi
- SQL bazaga o‘tmaslik
- Har bir o‘yin alohida `.py` modulida bo‘lishi

## Gotchas

- `API_TOKEN` environment variable o‘rnatilmasa bot ishga tushmaydi
- Webhook URL Render uchun `RENDER_EXTERNAL_URL`, Replit uchun
  `REPLIT_DEV_DOMAIN` orqali aniqlanadi