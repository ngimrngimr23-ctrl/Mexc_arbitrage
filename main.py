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
    "percent": 5.0,        # Порог падения в окне (%)
    "window_min": 15,      # Окно анализа (мин)
    "check_interval": 30,  # Как часто проверять (сек)
    "min_volume": 100000,  # Мин. объем 24ч ($)
    "day_drop": 0.0,       # Порог падения за 24ч (%)
    "cooldown_min": 5,     # Минимальная пауза от спама (мин)
    "week_drop": 0.0,      # МАКС. падение за 7 дней (0 - выключено)
    "month_drop": 0.0,     # МАКС. падение за 30 дней (0 - выключено)
    "chat_id": None,
    "channel_id": None     # ID или @username канала для дублирования
}

price_history = {}
blacklist = set()
daily_memory = {} 

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
        f"📆 Фильтр 7д: <b>{'Выкл' if settings['week_drop'] == 0 else f'Макс -{settings['week_drop']}%'}</b>\n"
        f"🗓 Фильтр 30д: <b>{'Выкл' if settings['month_drop'] == 0 else f'Макс -{settings['month_drop']}%'}</b>\n"
        f"💰 Мин. объём: <b>{settings['min_volume']:,}$</b>\n"
        f"📢 Канал: <b>{settings['channel_id'] or 'Выкл'}</b>\n\n"
        "⚙️ <b>Команды:</b>\n"
        "/p 5 — % падения в окне\n"
        "/d 5 — % падения за 24ч\n"
        "/w 30 — скрыть, если упала >30% за 7 дней (0=выкл)\n"
        "/m 50 — скрыть, если упала >50% за 30 дней (0=выкл)\n"
        "/channel @name — дублировать в канал (без аргументов = выкл)\n"
        "/t 10 — окно (мин)\n"
        "/v 200000 — объем $\n"
        "/b BTC — в ЧС\n"
        "/s — статус"
    , parse_mode="HTML")

@dp.message(Command("channel"))
async def set_channel(message: types.Message, command: CommandObject):
    if command.args:
        settings["channel_id"] = command.args
        await message.answer(f"✅ Дублирование сигналов в канал включено:\n<b>{command.args}</b>\n\n<i>⚠️ Не забудь добавить бота в этот канал и назначить его администратором!</i>", parse_mode="HTML")
    else:
        settings["channel_id"] = None
        await message.answer("✅ Дублирование в канал <b>ВЫКЛЮЧЕНО</b>.", parse_mode="HTML")

@dp.message(Command("p"))
async def set_percent(message: types.Message, command: CommandObject):
    try:
        val = float(command.args.replace(',', '.'))
        settings["percent"] = val
        await message.answer(f"✅ Порог падения: <b>{val}%</b>", parse_mode="HTML")
    except: await message.answer("❌ Ошибка. Пример: /p 7.5")

@dp.message(Command("d"))
async def set_day_drop(message: types.Message, command: CommandObject):
    try:
        val = float(command.args.replace(',', '.'))
        settings["day_drop"] = -abs(val) 
        await message.answer(f"✅ Фильтр 24ч: <b>{settings['day_drop']}%</b>", parse_mode="HTML")
    except: await message.answer("❌ Ошибка. Пример: /d 5")

@dp.message(Command("w"))
async def set_week_drop(message: types.Message, command: CommandObject):
    try:
        val = abs(float(command.args.replace(',', '.')))
        settings["week_drop"] = val
        if val == 0:
            await message.answer("✅ Фильтр 7 дней <b>ВЫКЛЮЧЕН</b>", parse_mode="HTML")
        else:
            await message.answer(f"✅ Фильтр 7 дней: скрывать монеты, упавшие больше чем на <b>-{val}%</b>", parse_mode="HTML")
    except: await message.answer("❌ Ошибка. Пример: /w 30 (для отключения введи /w 0)")

@dp.message(Command("m"))
async def set_month_drop(message: types.Message, command: CommandObject):
    try:
        val = abs(float(command.args.replace(',', '.')))
        settings["month_drop"] = val
        if val == 0:
            await message.answer("✅ Фильтр 30 дней <b>ВЫКЛЮЧЕН</b>", parse_mode="HTML")
        else:
            await message.answer(f"✅ Фильтр 30 дней: скрывать монеты, упавшие больше чем на <b>-{val}%</b>", parse_mode="HTML")
    except: await message.answer("❌ Ошибка. Пример: /m 50 (для отключения введи /m 0)")

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
        await message.answer(f"🚫 <b>{pair}</b> в ЧС")

@dp.message(Command("s"))
async def status_cmd(message: types.Message):
    await message.answer(
        "📊 <b>Статус</b>\n"
        f"📉 Окно: {settings['percent']}% ({settings['window_min']}м)\n"
        f"📅 24ч: {settings['day_drop']}%\n"
        f"📆 7 дней: {'Выкл' if settings['week_drop'] == 0 else f'Макс -{settings['week_drop']}%'}\n"
        f"🗓 30 дней: {'Выкл' if settings['month_drop'] == 0 else f'Макс -{settings['month_drop']}%'}\n"
        f"💰 Объём: {settings['min_volume']:,}$\n"
        f"📢 Канал: {settings['channel_id'] or 'Выкл'}\n"
        f"🛑 В памяти дампов: {len(daily_memory)}"
    , parse_mode="HTML")

# ================= API & LOGIC =================

async def fetch_prices():
    url = "https://api.mexc.com/api/v3/ticker/24hr"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                if response.status == 200: return await response.json()
    except Exception as e: print(f"Ошибка API: {e}", flush=True)
    return []

async def get_long_term_changes(symbol, current_price):
    url = f"https://api.mexc.com/api/v3/klines?symbol={symbol}&interval=1d&limit=31"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if not data: return 0.0, 0.0
                    idx_7 = -8 if len(data) >= 8 else 0
                    idx_30 = -31 if len(data) >= 31 else 0
                    p_7 = float(data[idx_7][1])
                    p_30 = float(data[idx_30][1])
                    c_7 = ((current_price - p_7) / p_7) * 100
                    c_30 = ((current_price - p_30) / p_30) * 100
                    return c_7, c_30
    except: pass
    return 0.0, 0.0

async def parser_task():
    print("--- Фоновый парсер запущен ---", flush=True)
    while True:
        try:
            if settings["chat_id"]:
                data = await fetch_prices()
                now = time.time()
                max_pts = int((settings["window_min"] * 60) / settings["check_interval"])
                cooldown_sec = settings["cooldown_min"] * 60

                for item in data:
                    pair = item['symbol']
                    if not pair.endswith("USDT") or pair in blacklist: continue
                    try:
                        vol = float(item['quoteVolume'])
                        if vol < settings["min_volume"]: continue
                        price = float(item['lastPrice'])
                        ch_24 = float(item['priceChangePercent']) * 100
                    except: continue

                    if pair not in price_history or price_history[pair].maxlen != max_pts:
                        price_history[pair] = deque(maxlen=max_pts)

                    history = price_history[pair]
                    if len(history) > 0:
                        max_p = max(history)
                        drop = ((max_p - price) / max_p) * 100
                        
                        if pair in daily_memory and (now - daily_memory[pair]["time"]) >= 86400:
                            del daily_memory[pair]

                        if drop >= settings["percent"] and ch_24 <= settings["day_drop"]:
                            should_alert = True
                            is_repeat = False
                            
                            if pair in daily_memory:
                                if (now - daily_memory[pair]["last_msg"]) < cooldown_sec:
                                    should_alert = False
                                else:
                                    req_drop = settings["percent"] * 2
                                    threshold = daily_memory[pair]["price"] * (1 - (req_drop / 100))
                                    if price <= threshold:
                                        is_repeat = True
                                    else:
                                        should_alert = False
                            
                            if should_alert:
                                ch_7, ch_30 = await get_long_term_changes(pair, price)
                                
                                if settings["week_drop"] > 0 and ch_7 < -settings["week_drop"]:
                                    should_alert = False
                                elif settings["month_drop"] > 0 and ch_30 < -settings["month_drop"]:
                                    should_alert = False
                                
                                if should_alert:
                                    daily_memory[pair] = {
                                        "time": daily_memory[pair]["time"] if pair in daily_memory else now,
                                        "price": price,
                                        "last_msg": now
                                    }
                                    
                                    label = "🔥 <b>ПОВТОРНЫЙ ДАМП (x2)</b>\n" if is_repeat else ""
                                    
                                    # Формируем сообщение (название монеты обернуто в тег <code> для копирования по клику)
                                    msg_text = (
                                        f"🚨 <b>ДАМП:</b> <code>{pair}</code>\n{label}"
                                        f"📉 В окне: <b>-{drop:.2f}%</b>\n"
                                        f"📊 За 24 часа: <b>{ch_24:.2f}%</b>\n"
                                        f"📆 За 7 дней: <b>{ch_7:.2f}%</b>\n"
                                        f"🗓 За 30 дней: <b>{ch_30:.2f}%</b>\n"
                                        f"💵 Было (пик): <code>{max_p}</code>\n"
                                        f"💸 Стало (тек): <code>{price}</code>\n"
                                        f"💰 Объём: <b>{int(vol):,}$</b>"
                                    )
                                    
                                    # Отправляем сообщение тебе в личку
                                    await bot.send_message(settings["chat_id"], msg_text, parse_mode="HTML")
                                    
                                    # Отправляем в канал, если он настроен
                                    if settings["channel_id"]:
                                        try:
                                            await bot.send_message(settings["channel_id"], msg_text, parse_mode="HTML")
                                        except Exception as e:
                                            print(f"Ошибка отправки в канал: {e}", flush=True)

                    history.append(price)
        except Exception as e: print(f"Ошибка парсера: {e}", flush=True)
        await asyncio.sleep(settings["check_interval"])

# ================= WEB & RUN =================

async def handle_ping(request): return web.Response(text="OK", status=200)

async def main():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 10000)))
    await site.start()
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(parser_task())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
