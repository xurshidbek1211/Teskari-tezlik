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

## Loyiha haqida

### 1. 🔄 Teskari Tezlik
- `/boshla` — teskari yozilgan so'zni toping
- `/add savol || javob` — yangi savol qo'shish (admin)

### 2. 🎨 Rasm Chizish O'yini
- `/rasm` — Paint-ga o'xshash veb-interfeysda so'z chiziladi, boshqalar topadi
- Mini App (WebApp) orqali ishlanadi
- Layk tizimi: `+1⭐` chizuvchiga

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
