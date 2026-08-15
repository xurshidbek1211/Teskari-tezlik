# Teskari Tezlik

Telegram bot uchun Teskari Tezlik va Rasm chizish o'yini.

## Rasm chizish Mini App

- Mini App sahifasi: `/draw`
- Guruhdagi `🎨 Chizishni boshlash` tugmasi Telegram Mini App direct link'ini ochadi.
- Sessiya va guruh identifikatori `startapp` parametri orqali Mini App'ga o'tadi.
- Rasm chizish canvas'i, 30 soniyalik preview, yuborish va 2 daqiqalik o'yin qoidalari mavjud backend endpointlari bilan ishlaydi.

Production'da Telegram BotFather orqali Mini App short name `draw` qilib,
URL'ni Render servisining HTTPS manziliga `/draw` yo'li bilan biriktirish kerak.
`TELEGRAM_MINI_APP_SHORT_NAME` o'zgaruvchisi boshqa short name ishlatilsa uni
almashtirish uchun mavjud.
