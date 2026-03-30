import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandObject
from aiohttp import web
import time
from collections import deque
import os

# ================= TOKEN =================
BOT_TOKEN = "8145739398:AAG3dl79hQnSsTe1KoYGt9hvaaUsR3XXllY"

# ================= SETTINGS =================
settings = {
    "percent": 5.0,
    "window_min": 15,
    "check_interval": 30,
    "min_volume": 100000,
    "chat_id": None
}

price_history = {}
blacklist = set()
last_alert = {}
COOLDOWN = 300

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ================= COMMANDS =================

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    settings["chat_id"] = message.chat.id
    await message.answer("🚀 Бот запущен")

@dp.message(Command("p"))
async def set_percent(message: types.Message, command: CommandObject):
    settings["percent"] = float(command.args)
    await message.answer(f"OK {settings['percent']}%")

@dp.message(Command("t"))
async def set_time(message: types.Message, command: CommandObject):
    settings["window_min"] = int(command.args)
    await message.answer("OK")

@dp.message(Command("v"))
async def set_volume(message: types.Message, command: CommandObject):
    settings["min_volume"] = int(command.args)
    await message.answer("OK")

@dp.message(Command("b"))
async def add_blacklist(message: types.Message, command: CommandObject):
    coin = command.args.upper()
    blacklist.add(coin)
    await message.answer("OK")

# ================= MEXC =================

async def fetch_prices():
    url = "https://api.mexc.com/api/v3/ticker/24hr"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as r:
            return await r.json()

async def parser_task():
    while True:
        try:
            if settings["chat_id"]:
                data = await fetch_prices()
                now = time.time()

                for item in data:
                    pair = item["symbol"]
                    if not pair.endswith("USDT") or pair in blacklist:
                        continue

                    volume = float(item["quoteVolume"])
                    if volume < settings["min_volume"]:
                        continue

                    price = float(item["lastPrice"])

                    max_points = int((settings["window_min"] * 60) / settings["check_interval"])

                    if pair not in price_history:
                        price_history[pair] = deque(maxlen=max_points)

                    history = price_history[pair]

                    if len(history) > 0:
                        max_price = max(history)
                        drop = ((max_price - price) / max_price) * 100

                        if drop >= settings["percent"]:
                            if pair not in last_alert or (now - last_alert[pair]) > COOLDOWN:
                                last_alert[pair] = now
                                await bot.send_message(
                                    settings["chat_id"],
                                    f"🚨 {pair}\n-{drop:.2f}%"
                                )

                    history.append(price)

        except Exception as e:
            print("Parser error:", e)

        await asyncio.sleep(settings["check_interval"])

# ================= WEBHOOK =================

async def handle_ping(request):
    return web.Response(text="OK")

async def webhook_handler(request):
    data = await request.json()
    update = types.Update.model_validate(data)
    await dp.feed_update(bot, update)
    return web.Response(text="ok")

# ================= MAIN =================

async def main():
    asyncio.create_task(parser_task())

    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_post("/webhook", webhook_handler)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    url = os.environ.get("RENDER_EXTERNAL_URL")
    webhook_url = f"{url}/webhook"

    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(webhook_url)

    print("WEBHOOK:", webhook_url)

    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
