import asyncio
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

settings = {
    "percent": 10.0,
    "window_min": 5,
    "min_volume": 50000,
    "blacklist": set(),
    "chat_id": None
}

# ---------------- /start ----------------
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    settings["chat_id"] = message.chat.id

    await message.answer(
        "🚀 Бот-сканер MEXC запущен\n\n"
        "📉 Порог падения: 10.0%\n"
        "⏱ Окно анализа: 5 мин\n"
        "💰 Мин. объём: 50,000$\n\n"
        "⚙️ Команды:\n"
        "/p 5 — % падения\n"
        "/t 10 — окно (мин)\n"
        "/v 200000 — объём $\n"
        "/b BTC — в ЧС\n"
        "/ub BTC — из ЧС\n"
        "/s — статус"
    )


# ---------------- COMMANDS ----------------
@dp.message(Command("p"))
async def set_percent(message: types.Message):
    try:
        settings["percent"] = float(message.text.split()[1])
        await message.answer(f"📉 Новый порог: {settings['percent']}%")
    except:
        await message.answer("Используй: /p 5")


@dp.message(Command("t"))
async def set_window(message: types.Message):
    try:
        settings["window_min"] = int(message.text.split()[1])
        await message.answer(f"⏱ Окно: {settings['window_min']} мин")
    except:
        await message.answer("Используй: /t 10")


@dp.message(Command("v"))
async def set_volume(message: types.Message):
    try:
        settings["min_volume"] = int(message.text.split()[1])
        await message.answer(f"💰 Мин. объём: {settings['min_volume']}$")
    except:
        await message.answer("Используй: /v 200000")


@dp.message(Command("b"))
async def blacklist_add(message: types.Message):
    try:
        coin = message.text.split()[1].upper()
        settings["blacklist"].add(coin)
        await message.answer(f"🚫 {coin} добавлен в ЧС")
    except:
        await message.answer("Используй: /b BTC")


@dp.message(Command("ub"))
async def blacklist_remove(message: types.Message):
    try:
        coin = message.text.split()[1].upper()
        settings["blacklist"].discard(coin)
        await message.answer(f"✅ {coin} удалён из ЧС")
    except:
        await message.answer("Используй: /ub BTC")


@dp.message(Command("s"))
async def status(message: types.Message):
    await message.answer(
        f"📊 Статус\n\n"
        f"📉 Порог: {settings['percent']}%\n"
        f"⏱ Окно: {settings['window_min']} мин\n"
        f"💰 Объём: {settings['min_volume']}$\n"
        f"🚫 ЧС: {', '.join(settings['blacklist']) if settings['blacklist'] else 'пусто'}"
    )


# ---------------- WEBHOOK ----------------
async def webhook_handler(request):
    data = await request.json()
    update = types.Update.model_validate(data)
    await dp.feed_update(bot, update)
    return web.Response(text="ok")


# ---------------- AUTO WEBHOOK ----------------
async def on_startup(app):
    base_url = os.getenv("RENDER_EXTERNAL_URL")  # Render сам даёт
    webhook_url = f"{base_url}/webhook"

    await bot.set_webhook(webhook_url)
    print("WEBHOOK SET:", webhook_url)


app = web.Application()
app.router.add_post("/webhook", webhook_handler)
app.on_startup.append(on_startup)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    web.run_app(app, port=port)
