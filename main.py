import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandObject
from aiohttp import web
import time
from collections import deque
import os

# ================= НАСТРОЙКИ =================

# Совет: лучше использовать os.getenv("BOT_TOKEN"), но если вписываешь вручную — сюда:
BOT_TOKEN = "8145739398:AAG3dl79hQnSsTe1KoYGt9hvaaUsR3XXllY"

settings = {
    "percent": 5.0,
    "window_min": 15,
    "check_interval": 30,
    "min_volume": 100000,  # Минимальный объем в USDT за 24ч
    "chat_id": None
}

price_history = {}
blacklist = set()
last_alert = {}

COOLDOWN = 300  # 5 минут пауза между алертами на одну монету

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ================= TELEGRAM UI =================

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    settings["chat_id"] = message.chat.id
    await message.answer(
        "🚀 <b>Бот-сканер MEXC запущен</b>\n\n"
        f"📉 Порог падения: <b>{settings['percent']}%</b>\n"
        f"⏱ Окно анализа: <b>{settings['window_min']} мин</b>\n"
        f"💰 Мин. объём: <b>{settings['min_volume']:,}$</b>\n\n"
        "⚙️ <b>Команды:</b>\n"
        "/p 5 — % падения\n"
        "/t 10 — окно (мин)\n"
        "/v 200000 — объём $\n"
        "/b BTC — в ЧС\n"
        "/ub BTC — из ЧС\n"
        "/s — статус"
    , parse_mode="HTML")

@dp.message(Command("p"))
async def set_percent(message: types.Message, command: CommandObject):
    try:
        val = float(command.args.replace(',', '.'))
        settings["percent"] = val
        await message.answer(f"✅ Порог: <b>{val}%</b>", parse_mode="HTML")
    except:
        await message.answer("❌ Ошибка. Пример: /p 7.5")

@dp.message(Command("t"))
async def set_time(message: types.Message, command: CommandObject):
    if command.args and command.args.isdigit():
        settings["window_min"] = int(command.args)
        await message.answer(f"✅ Окно: <b>{command.args} мин</b>", parse_mode="HTML")

@dp.message(Command("v"))
async def set_volume(message: types.Message, command: CommandObject):
    if command.args and command.args.isdigit():
        settings["min_volume"] = int(command.args)
        await message.answer(f"✅ Объём: <b>{settings['min_volume']:,}$</b>", parse_mode="HTML")

@dp.message(Command("b"))
async def add_blacklist(message: types.Message, command: CommandObject):
    if command.args:
        coin = command.args.upper()
        pair = coin if coin.endswith("USDT") else f"{coin}USDT"
        blacklist.add(pair)
        await message.answer(f"🚫 {pair} в ЧС", parse_mode="HTML")

@dp.message(Command("ub"))
async def remove_blacklist(message: types.Message, command: CommandObject):
    if command.args:
        coin = command.args.upper()
        pair = coin if coin.endswith("USDT") else f"{coin}USDT"
        blacklist.discard(pair)
        await message.answer(f"✅ {pair} удален из ЧС", parse_mode="HTML")

@dp.message(Command("s"))
async def status_cmd(message: types.Message):
    await message.answer(
        "📊 <b>Статус</b>\n\n"
        f"📉 Порог: <b>{settings['percent']}%</b>\n"
        f"⏱ Окно: <b>{settings['window_min']} мин</b>\n"
        f"💰 Объём: <b>{settings['min_volume']:,}$</b>\n"
        f"📡 Пар: <b>{len(price_history)}</b>\n"
        f"🚫 ЧС: <b>{len(blacklist)}</b>"
    , parse_mode="HTML")

# ================= API & LOGIC =================

async def fetch_prices():
    url = "https://api.mexc.com/api/v3/ticker/24hr"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    return await response.json()
    except Exception as e:
        print(f"Ошибка API MEXC: {e}")
    return []

async def parser_task():
    while True:
        # Добавляем try-except, чтобы любая ошибка внутри не останавливала цикл
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
                                    f"🚨 <b>ДАМП: {pair}</b>\n\n"
                                    f"📉 Падение: <b>-{drop:.2f}%</b>\n"
                                    f"🔝 Пик: <code>{max_price}</code>\n"
                                    f"💸 Сейчас: <code>{price}</code>\n"
                                    f"💰 Объём: <b>{int(volume):,}$</b>"
                                , parse_mode="HTML")

                    history.append(price)
        except Exception as e:
            print(f"Критическая ошибка в цикле парсера: {e}")
            # Небольшая пауза при ошибке, чтобы не спамить в лог
            await asyncio.sleep(5)

        await asyncio.sleep(settings["check_interval"])

# ================= WEB & RUN =================

async def handle_ping(request):
    return web.Response(text="Бот активен")

async def main():
    # 1. Запуск фонового парсера
    asyncio.create_task(parser_task())

    # 2. Настройка веб-сервера (жестко порт 10000 для Render)
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Жестко прописанный порт
    port = 10000 
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Веб-сервер запущен на порту {port}")

    # 3. Сброс старых соединений (Webhook и накопившиеся сообщения)
    # Это решает проблему конфликта при перезагрузке на Render
    await bot.delete_webhook(drop_pending_updates=True)
    print("Старые обновления Telegram очищены.")

    # 4. Запуск Telegram бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен")
