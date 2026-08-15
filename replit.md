<<<<<<< HEAD
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
=======
# Teskari Tezlik — Telegram Bot

Telegram guruh o'yinlari boti. Ikki o'yin rejimi mavjud: Teskari Tezlik va Rasm Chizish O'yini.

## Run & Operate

- `uvicorn main:app --host 0.0.0.0 --port 5000` — botni ishga tushirish
- Required env: `API_TOKEN` — BotFather dan olingan Telegram bot tokeni
- Required env: `RENDER_EXTERNAL_URL` — Webhook URL manzili

## Stack

- **Python 3.12** + **aiogram 3.x** (Telegram bot framework)
- **FastAPI** + **uvicorn** (webhook server + Mini App)
- **APScheduler** (kunlik g'olib e'loni)
- **JSON fayllar** (ma'lumotlar saqlash)
>>>>>>> 9f36fcb9fad47c64c6fcf2819a427256acdae4ea

## Loyiha haqida

<<<<<<< HEAD
- `main.py` — asosiy bot logikasi (teskari tezlik o'yini)
- `rasm_oyini.py` — rasm chizish o'yini moduli
- `static/draw.html` — rasm chizish Telegram Mini App
- `teskari_tezlik_savollar.json` — o'yin savollari bazasi
- `rasm_sozlar.json` — rasm o'yini so'zlari bazasi
- `user_scores.json` — foydalanuvchi ballari
- `user_states.json` — o'yin holatlari
- `winner_count.json` — g'oliblar hisobi
=======
### 1. 🔄 Teskari Tezlik
- `/boshla` — teskari yozilgan so'zni toping
- `/add savol || javob` — yangi savol qo'shish (admin)
>>>>>>> 9f36fcb9fad47c64c6fcf2819a427256acdae4ea

### 2. 🎨 Rasm Chizish O'yini
- `/rasm` — Paint-ga o'xshash veb-interfeysda so'z chiziladi, boshqalar topadi
- Mini App (WebApp) orqali ishlanadi
- Layk tizimi: `+1⭐` chizuvchiga

<<<<<<< HEAD
- Webhook orqali ishlaydi (polling emas) — Render/Replit uchun mos
- `rasm_router` main_router'dan OLDIN qo'shiladi — Command filtrlari to'g'ri ishlashi uchun
- Har kuni yarim tunda (Toshkent vaqti) balllar reset qilinadi va g'olib e'lon qilinadi

## User preferences

_Populate as you build._

## Gotchas

- `API_TOKEN` environment variable o'rnatilmasa bot ishlamaydi
- Webhook URL avtomatik aniqlanadi: Render uchun `RENDER_EXTERNAL_URL`, Replit uchun `REPLIT_DEV_DOMAIN`
=======
## Fayl tuzilmasi

```
main.py                        — asosiy bot va FastAPI server
rasm_oyini.py                  — rasm chizish o'yini moduli
static/draw.html               — rasm chizish Mini App (WebApp)
rasm_sozlar.json               — rasm o'yini so'zlar bazasi
teskari_tezlik_savollar.json   — teskari tezlik savollari
user_scores.json               — teskari tezlik ballari
render.yaml                    — Render deploy konfiguratsiyasi
requirements.txt               — Python paketlari
```

## User preferences

- Bot kodi Uzbek tilida, o'zgaruvchi nomlar va mantiq Uzbek dasturlash uslubida
- Mavjud JSON fayl tizimidan foydalanish (SQL DB ga o'tkazmaslik)
- Modular arxitektura: har bir o'yin alohida `.py` faylda

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
>>>>>>> 9f36fcb9fad47c64c6fcf2819a427256acdae4ea
