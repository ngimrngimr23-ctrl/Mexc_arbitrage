import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

TOKEN = "8145739398:AAG3dl79hQnSsTe1KoYGt9hvaaUsR3XXllY"

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


# ---------------- /p ----------------
@dp.message(Command("p"))
async def set_percent(message: types.Message):
    try:
        value = float(message.text.split()[1])
        settings["percent"] = value
        await message.answer(f"📉 Новый порог: {value}%")
    except:
        await message.answer("Используй: /p 5")


# ---------------- /t ----------------
@dp.message(Command("t"))
async def set_window(message: types.Message):
    try:
        value = int(message.text.split()[1])
        settings["window_min"] = value
        await message.answer(f"⏱ Окно: {value} мин")
    except:
        await message.answer("Используй: /t 10")


# ---------------- /v ----------------
@dp.message(Command("v"))
async def set_volume(message: types.Message):
    try:
        value = int(message.text.split()[1])
        settings["min_volume"] = value
        await message.answer(f"💰 Мин. объём: {value}$")
    except:
        await message.answer("Используй: /v 200000")


# ---------------- /b ----------------
@dp.message(Command("b"))
async def blacklist_add(message: types.Message):
    try:
        coin = message.text.split()[1].upper()
        settings["blacklist"].add(coin)
        await message.answer(f"🚫 {coin} добавлен в ЧС")
    except:
        await message.answer("Используй: /b BTC")


# ---------------- /ub ----------------
@dp.message(Command("ub"))
async def blacklist_remove(message: types.Message):
    try:
        coin = message.text.split()[1].upper()
        settings["blacklist"].discard(coin)
        await message.answer(f"✅ {coin} удалён из ЧС")
    except:
        await message.answer("Используй: /ub BTC")


# ---------------- /s ----------------
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


async def on_startup(app):
    await bot.set_webhook("https://YOUR_DOMAIN/webhook")


app = web.Application()
app.router.add_post("/webhook", webhook_handler)
app.on_startup.append(on_startup)


if __name__ == "__main__":
    web.run_app(app, port=10000)
