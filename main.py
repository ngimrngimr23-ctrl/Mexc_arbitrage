import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandObject
from aiohttp import web
import time
from collections import deque
import os

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "8145739398:AAG3dl79hQnSsTe1KoYGt9hvaaUsR3XXllY"

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

# ================= TELEGRAM UI =================

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    settings["chat_id"] = message.chat.id
    await message.answer(
        "🚀 <b>Бот-сканер MEXC запущен</b>\n\n"
        f"📉 Порог: <b>{settings['percent']}%</b>\n"
        f"⏱ Окно: <b>{settings['window_min']} мин</b>\n"
        f"💰 Мин. объём: <b>{settings['min_volume']:,}$</b>\n\n"
        "Пиши /s для проверки статуса.", parse_mode="HTML")

@dp.message(Command("s"))
async def status_cmd(message: types.Message):
    await message.answer(
        "📊 <b>Статус</b>\n"
        f"📡 Пар в мониторинге: <b>{len(price_history)}</b>\n"
        f"📉 Порог: <b>{settings['percent']}%</b>\n"
        f"💰 Объём: <b>{settings['min_volume']:,}$</b>", parse_mode="HTML")

# Добавь остальные команды (/p, /t, /v) из предыдущего кода, если они нужны

# ================= API & LOGIC =================

async def fetch_prices():
    url = "https://api.mexc.com/api/v3/ticker/24hr"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    print(f"MEXC API Error: {response.status}")
    except Exception as e:
        print(f"Network error: {e}")
    return []

async def parser_task():
    while True:
        try:
            if settings["chat_id"]:
                data = await fetch_prices()
                now = time.time()
                max_points = int((settings["window_min"] * 60) / settings["check_interval"])

                for item in data:
                    pair = item['symbol']
                    if not pair.endswith("USDT") or pair in blacklist:
                        continue

                    try:
                        volume = float(item['quoteVolume'])
                        if volume < settings["min_volume"]:
                            continue
                        price = float(item['lastPrice'])
                    except: continue

                    if pair not in price_history or price_history[pair].maxlen != max_points:
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
                                    f"🚨 <b>ДАМП: {pair}</b>\n"
                                    f"📉 Падение: <b>-{drop:.2f}%</b>\n"
                                    f"💸 Цена: <code>{price}</code>", parse_mode="HTML")
                    history.append(price)
        except Exception as e:
            print(f"Ошибка в цикле парсера: {e}")
            
        await asyncio.sleep(settings["check_interval"])

# ================= WEB & RUN =================

async def handle_ping(request):
    return web.Response(text="Alive")

async def main():
    # 1. Запускаем парсер
    asyncio.create_task(parser_task())

    # 2. Веб-сервер на порту 10000
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    await site.start()

    # 3. КРИТИЧЕСКИЙ МОМЕНТ ДЛЯ RENDER:
    # Очищаем все старые сессии Telegram перед запуском
    await bot.delete_webhook(drop_pending_updates=True)
    
    # 4. Запуск бота
    print("Бот запускается...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
