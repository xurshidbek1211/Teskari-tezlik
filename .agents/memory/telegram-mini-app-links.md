---
name: Telegram Mini App group links
description: How drawing-game group buttons must launch Telegram Mini Apps while preserving per-game context.
---

Group inline keyboards should use a Telegram direct URL (`t.me/<bot>/<short_name>?startapp=...`) for Mini Apps. A `web_app` inline button is intended for private bot chats, so a group flow should pass its session and chat context through `startapp` and read it from Telegram WebApp init data.

**Why:** The drawing game starts in a group, while Telegram's Web App button behavior is private-chat scoped; routing through a private `/start` message creates an extra, legacy step instead of opening the Mini App directly.

**How to apply:** Keep the Mini App short name mapped to the deployed HTTPS page, encode the game context in `startapp`, and use `Telegram.WebApp.initData` for backend identity checks.
