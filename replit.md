# Teskari Tezlik — Telegram Bot

## Loyiha haqida
Telegram guruh o'yinlari boti. Ikki o'yin rejimi mavjud:

### 1. 🔄 Teskari Tezlik
- `/boshla` — teskari yozilgan so'zni toping
- `/add savol || javob` — yangi savol qo'shish (admin)

### 2. 🎨 Rasm Chizish O'yini
- `/rasm` — Paint-ga o'xshash veb-interfeysdа so'z chiziladi, boshqalar topadi
- Mini App (WebApp) orqali ishlanadi
- Layk tizimi: `+1⭐` chizuvchiga

## Stack
- **Python 3.11** + **aiogram 3.x** (Telegram bot framework)
- **FastAPI** + **uvicorn** (webhook server + Mini App)
- **APScheduler** (kunlik g'olib e'loni)
- **JSON fayllar** (ma'lumotlar saqlash)

## Fayl tuzilmasi
```
main.py                        — asosiy bot va FastAPI server
rasm_oyini.py                  — rasm chizish o'yini moduli
static/draw.html               — rasm chizish Mini App (WebApp)
rasm_sozlar.json               — rasm o'yini so'zlar bazasi (kategoria + qiyinlik)
teskari_tezlik_savollar.json   — teskari tezlik savollari
user_scores.json               — teskari tezlik ballari
user_states.json               — teskari tezlik holatlari
drawing_game_states.json       — rasm o'yini holatlari (avtomatik yaratiladi)
drawing_likes.json             — layklar (avtomatik yaratiladi)
drawing_star_scores.json       — rasm o'yini yulduz ballari (avtomatik yaratiladi)
render.yaml                    — Render deploy konfiguratsiyasi
requirements.txt               — Python paketlari
```

## Render platformasida ishlatish
Bot **Render.com** da joylashtiriladi.

### Kerakli muhit o'zgaruvchilari (Render Dashboard):
| O'zgaruvchi | Tavsif |
|---|---|
| `API_TOKEN` | BotFather dan olingan Telegram bot tokeni |
| `RENDER_EXTERNAL_URL` | Render servisining to'liq HTTPS URL manzili |

`render.yaml` da `RENDER_EXTERNAL_URL` avtomatik to'ldiriladi (`fromService`).
`API_TOKEN` esa Render Dashboard → Environment dan qo'lda kiritiladi.

### Deploy qilish:
1. GitHub repoga push qiling
2. Render.com → New Web Service → reponi ulang
3. `render.yaml` avtomatik taniladi
4. `API_TOKEN` ni Environment Variables ga qo'shing
5. Deploy!

## Mahalliy ishga tushirish (test uchun)
```bash
pip install -r requirements.txt
API_TOKEN=your_token RENDER_EXTERNAL_URL=https://your-domain.onrender.com uvicorn main:app --host 0.0.0.0 --port 8000
```

## User preferences
- Bot kodi Uzbek tilida, o'zgaruvchi nomlar va mantiq Uzbek dasturlash uslubida
- Mavjud JSON fayl tizimidan foydalanish (SQL DB ga o'tkazmaslik)
- Modular arxitektura: har bir o'yin alohida `.py` faylda
