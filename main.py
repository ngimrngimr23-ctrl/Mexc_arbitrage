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
    "percent": 5.0,       # Порог падения в окне (%)
    "window_min": 15,     # Окно анализа (мин)
    "check_interval": 30, # Как часто проверять (сек)
    "min_volume": 100000, # Мин. объем 24ч ($)
    "day_drop": 0.0,      # Порог падения за 24ч (%)
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
        f"📉 Порог окна: <b>{settings['percent']}%</b>\n"
        f"📅 Порог 24ч: <b>{settings['day_drop']}%</b>\n"
        f"⏱ Окно анализа: <b>{settings['window_min']} мин</b>\n"
        f"💰 Мин. объём: <b>{settings['min_volume']:,}$</b>\n\n"
        "⚙️ <b>Команды:</b>\n"
        "/p 5 — изменить % падения в окне\n"
        "/d 5 — изменить % падения за 24ч\n"
        "/t 10 — изменить окно (мин)\n"
        "/v 200000 — мин. объём $\n"
        "/b BTC — добавить в ЧС\n"
        "/ub BTC — убрать из ЧС\n"
        "/s — текущий статус"
    , parse_mode="HTML")

@dp.message(Command("p"))
async def set_percent(message: types.Message, command: CommandObject):
    try:
        val = float(command.args.replace(',', '.'))
        settings["percent"] = val
        await message.answer(f"✅ Порог падения в окне: <b>{val}%</b>", parse_mode="HTML")
    except:
        await message.answer("❌ Ошибка. Пример: /p 7.5")

@dp.message(Command("d"))
async def set_day_drop(message: types.Message, command: CommandObject):
    try:
        val = float(command.args.replace(',', '.'))
        settings["day_drop"] = -abs(val) 
        await message.answer(f"✅ Фильтр 24ч: монета должна быть ниже <b>{settings['day_drop']}%</b> за сутки", parse_mode="HTML")
    except:
        await message.answer("❌ Ошибка. Пример: /d 5")

@dp.message(Command("t"))
async def set_time(message: types.Message, command: CommandObject):
    if command.args and command.args.isdigit():
        settings["window_min"] = int(command.args)
        await message.answer(f"✅ Окно: <b>{command.args} мин</b>", parse_mode="HTML")

@dp.message(Command("v"))
async def set_volume(message: types.Message, command: CommandObject):
    if command.args and command.args.isdigit():
        settings["min_volume"] = int(command.args)
        await message.answer(f"✅ Мин. объём: <b>{settings['min_volume']:,}$</b>", parse_mode="HTML")

@dp.message(Command("b"))
async def add_blacklist(message: types.Message, command: CommandObject):
    if command.args:
        coin = command.args.upper()
        pair = coin if coin.endswith("USDT") else f"{coin}USDT"
        blacklist.add(pair)
        await message.answer(f"🚫 <b>{pair}</b> в ЧС", parse_mode="HTML")

@dp.message(Command("ub"))
async def remove_blacklist(message: types.Message, command: CommandObject):
    if command.args:
        coin = command.args.upper()
        pair = coin if coin.endswith("USDT") else f"{coin}USDT"
        blacklist.discard(pair)
        await message.answer(f"✅ <b>{pair}</b> удален из ЧС", parse_mode="HTML")

@dp.message(Command("s"))
async def status_cmd(message: types.Message):
    await message.answer(
        "📊 <b>Текущий статус</b>\n\n"
        f"📉 Порог окна: <b>{settings['percent']}%</b>\n"
        f"📅 Порог 24ч: <b>{settings['day_drop']}%</b>\n"
        f"⏱ Окно: <b>{settings['window_min']} мин</b>\n"
        f"💰 Мин. объём: <b>{settings['min_volume']:,}$</b>\n"
        f"📡 Мониторинг: <b>{len(price_history)} пар</b>\n"
        f"🚫 В черном списке: <b>{len(blacklist)}</b>"
    , parse_mode="HTML")

# ================= API & LOGIC =================

async def fetch_prices():
    url = "https://api.mexc.com/api/v3/ticker/24hr"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as response:
                if response.status == 200:
                    return await response.json()
    except Exception as e:
        print(f"Ошибка API: {e}")
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
                        change_24h = float(item['priceChangePercent'])
                    except: continue

                    if pair not in price_history or price_history[pair].maxlen != max_points:
                        price_history[pair] = deque(maxlen=max_points)

                    history = price_history[pair]
                    if len(history) > 0:
                        max_price = max(history)
                        drop = ((max_price - price) / max_price) * 100
                        
                        # Проверяем падение в окне И падение за сутки
                        if drop >= settings["percent"] and change_24h <= settings["day_drop"]:
                            if pair not in last_alert or (now - last_alert[pair]) > COOLDOWN:
                                last_alert[pair] = now
                                await bot.send_message(
                                    settings["chat_id"],
                                    f"🚨 <b>ДАМП: {pair}</b>\n\n"
                                    f"📉 В окне ({settings['window_min']}м): <b>-{drop:.2f}%</b>\n"
                                    f"📊 За 24 часа: <b>{change_24h:.2f}%</b>\n"
                                    f"🔝 Пик окна: <code>{max_price}</code>\n"
                                    f"💸 Текущая: <code>{price}</code>\n"
                                    f"💰 Объем 24ч: <b>{int(volume):,}$</b>"
                                , parse_mode="HTML")
                    history.append(price)
        except Exception as e:
            print(f"Ошибка парсера: {e}")
            await asyncio.sleep(5)

        await asyncio.sleep(settings["check_interval"])

# ================= WEB & RUN =================

async def handle_ping(request):
    return web.Response(text="Бот жив!")

async def main():
    # 1. Запускаем фоновый парсер
    asyncio.create_task(parser_task())
    
    # 2. Поднимаем веб-сервер (чтобы Render не ругался на порты)
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

    # 3. Жесткая очистка старых подключений Telegram
    await bot.delete_webhook(drop_pending_updates=True)
    
    print(f"Сервер слушает порт {port}. Запускаю Polling...")
    
    # 4. Запускаем мгновенный Polling
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Остановка бота")
        
