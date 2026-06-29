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
    "percent": 5.0,          # Порог падения в окне (%)
    "window_min": 15,        # Окно анализа (мин)
    "check_interval": 30,    # Как часто проверять (сек)
    "min_volume": 100000,    # Мин. объем 24ч ($)
    "day_drop": 999.0,       # По умолчанию выключено (999%), чтобы не блочить зеленые монеты
    "cooldown_min": 5,       # Минимальная пауза от спама (мин)
    "week_min_drop": 0.0,    # МИН. порог падения за 7 дней (0 - выключено)
    "week_drop": 0.0,        # МАКС. падение за 7 дней (0 - выключено)
    "month_min_drop": 0.0,   # МИН. порог падения за 30 дней (0 - выключено)
    "month_drop": 0.0,       # МАКС. падение за 30 дней (0 - выключено)
    "chat_id": None,         # ID админа (куда пишутся логи и команды)
    "channel_id": None       # ID или юзернейм канала для дублирования сигналов
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
        f"📅 Порог 24ч: <b>{'Выкл' if settings['day_drop'] == 999.0 else f'{settings['day_drop']}%'}</b>\n"
        f"📆 Мин. порог 7д: <b>{settings['week_min_drop']}%</b>\n"
        f"🗓 Мин. порог 30д: <b>{settings['month_min_drop']}%</b>\n"
        f"📆 Фильтр макс 7д: <b>{'Выкл' if settings['week_drop'] == 0 else f'Макс -{settings['week_drop']}%'}</b>\n"
        f"🗓 Фильтр макс 30д: <b>{'Выкл' if settings['month_drop'] == 0 else f'Макс -{settings['month_drop']}%'}</b>\n"
        f"💰 Мин. объём: <b>{settings['min_volume']:,}$</b>\n"
        f"📢 Канал: <b>{settings['channel_id'] or 'Не задан'}</b>\n\n"
        "⚙️ <b>Команды:</b>\n"
        "/p 5 — % падения в окне\n"
        "/d 5 — мин. % падения за 24ч (0 = отключить фильтр)\n"
        "/wmin 10 — мин. % падения за 7 дней (0=выкл)\n"
        "/mmin 20 — мин. % падения за 30 дней (0=выкл)\n"
        "/w 30 — скрыть, если упала >30% за 7 дней (0=выкл)\n"
        "/m 50 — скрыть, если упала >50% за 30 дней (0=выкл)\n"
        "/t 10 — окно (мин)\n"
        "/v 200000 — объем $\n"
        "/b BTC — в ЧС\n"
        "/channel @имя_канала — куда дублировать сигналы (пусто = выкл)\n"
        "/s — статус"
        , parse_mode="HTML")

@dp.message(Command("channel"))
async def set_channel(message: types.Message, command: CommandObject):
    settings["chat_id"] = message.chat.id
    if command.args:
        settings["channel_id"] = command.args
        await message.answer(f"✅ Канал для сигналов установлен: <b>{command.args}</b>\n<i>Не забудь сделать бота администратором в этом канале!</i>", parse_mode="HTML")
    else:
        settings["channel_id"] = None
        await message.answer("✅ Дублирование в канал <b>ОТКЛЮЧЕНО</b>", parse_mode="HTML")

@dp.message(Command("p"))
async def set_percent(message: types.Message, command: CommandObject):
    try:
        settings["chat_id"] = message.chat.id
        val = float(command.args.replace(',', '.'))
        settings["percent"] = val
        await message.answer(f"✅ Порог падения в окне: <b>{val}%</b>", parse_mode="HTML")
    except: await message.answer("❌ Ошибка. Пример: /p 7.5")

@dp.message(Command("d"))
async def set_day_drop(message: types.Message, command: CommandObject):
    try:
        settings["chat_id"] = message.chat.id
        val = float(command.args.replace(',', '.'))
        if val == 0:
            settings["day_drop"] = 999.0
            await message.answer("✅ Фильтр 24ч <b>ОТКЛЮЧЕН</b> (уведомления идут по всем монетам)", parse_mode="HTML")
        else:
            settings["day_drop"] = -abs(val)
            await message.answer(f"✅ Фильтр 24ч: монета должна быть в минусе минимум на <b>{settings['day_drop']}%</b>", parse_mode="HTML")
    except: await message.answer("❌ Ошибка. Пример: /d 5 (или /d 0 для выключения)")

@dp.message(Command("wmin"))
async def set_week_min_drop(message: types.Message, command: CommandObject):
    try:
        settings["chat_id"] = message.chat.id
        val = float(command.args.replace(',', '.'))
        settings["week_min_drop"] = -abs(val) if val != 0 else 0.0
        if val == 0:
            await message.answer("✅ Мин. порог падения за 7 дней <b>ВЫКЛЮЧЕН</b>", parse_mode="HTML")
        else:
            await message.answer(f"✅ Порог за 7 дней: монета должна упасть минимум на <b>{settings['week_min_drop']}%</b>", parse_mode="HTML")
    except: await message.answer("❌ Ошибка. Пример: /wmin 10")

@dp.message(Command("mmin"))
async def set_month_min_drop(message: types.Message, command: CommandObject):
    try:
        settings["chat_id"] = message.chat.id
        val = float(command.args.replace(',', '.'))
        settings["month_min_drop"] = -abs(val) if val != 0 else 0.0
        if val == 0:
            await message.answer("✅ Мин. порог падения за 30 дней <b>ВЫКЛЮЧЕН</b>", parse_mode="HTML")
        else:
            await message.answer(f"✅ Порог за 30 дней: монета должна упасть минимум на <b>{settings['month_min_drop']}%</b>", parse_mode="HTML")
    except: await message.answer("❌ Ошибка. Пример: /mmin 20")

@dp.message(Command("w"))
async def set_week_drop(message: types.Message, command: CommandObject):
    try:
        settings["chat_id"] = message.chat.id
        val = abs(float(command.args.replace(',', '.')))
        settings["week_drop"] = val
        if val == 0:
            await message.answer("✅ Макс. фильтр 7 дней <b>ВЫКЛЮЧЕН</b>", parse_mode="HTML")
        else:
            await message.answer(f"✅ Макс. фильтр 7 дней: скрывать монеты, упавшие больше чем на <b>-{val}%</b>", parse_mode="HTML")
    except: await message.answer("❌ Ошибка. Пример: /w 30 (для отключения введи /w 0)")

@dp.message(Command("m"))
async def set_month_drop(message: types.Message, command: CommandObject):
    try:
        settings["chat_id"] = message.chat.id
        val = abs(float(command.args.replace(',', '.')))
        settings["month_drop"] = val
        if val == 0:
            await message.answer("✅ Макс. фильтр 30 дней <b>ВЫКЛЮЧЕН</b>", parse_mode="HTML")
        else:
            await message.answer(f"✅ Макс. фильтр 30 дней: скрывать монеты, упавшие больше чем на <b>-{val}%</b>", parse_mode="HTML")
    except: await message.answer("❌ Ошибка. Пример: /m 50 (для отключения введи /m 0)")

@dp.message(Command("t"))
async def set_time(message: types.Message, command: CommandObject):
    settings["chat_id"] = message.chat.id
    if command.args and command.args.isdigit():
        settings["window_min"] = int(command.args)
        await message.answer(f"✅ Окно: <b>{command.args} мин</b>", parse_mode="HTML")

@dp.message(Command("v"))
async def set_volume(message: types.Message, command: CommandObject):
    settings["chat_id"] = message.chat.id
    if command.args and command.args.isdigit():
        settings["min_volume"] = int(command.args)
        await message.answer(f"✅ Объём: <b>{settings['min_volume']:,}$</b>", parse_mode="HTML")

@dp.message(Command("b"))
async def add_blacklist(message: types.Message, command: CommandObject):
    settings["chat_id"] = message.chat.id
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
        f"📅 24ч (мин): {'Выкл' if settings['day_drop'] == 999.0 else f'{settings['day_drop']}%'}\n"
        f"📆 7 дней (мин): {settings['week_min_drop']}%\n"
        f"🗓 30 дней (мин): {settings['month_min_drop']}%\n"
        f"📆 7 дней (макс): {'Выкл' if settings['week_drop'] == 0 else f'-{settings['week_drop']}%'}\n"
        f"🗓 30 дней (макс): {'Выкл' if settings['month_drop'] == 0 else f'-{settings['month_drop']}%'}\n"
        f"💰 Объём: {settings['min_volume']:,}$\n"
        f"📢 Канал: {settings['channel_id'] or 'Не задан'}\n"
        f"🛑 В памяти дампов: {len(daily_memory)}\n"
        f"📡 Отслеживается пар: {len(price_history)}"
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
    except:
        pass
    return 0.0, 0.0

async def parser_task():
    print("--- Фоновый парсер запущен ---", flush=True)
    while True:
        try:
            data = await fetch_prices()
            now = time.time()
            window_sec = settings["window_min"] * 60
            max_pts = max(int((window_sec / settings["check_interval"]) * 1.2), 5)
            cooldown_sec = settings["cooldown_min"] * 60

            for item in data:
                pair = item['symbol']
                if not pair.endswith("USDT") or pair in blacklist: continue

                try:
                    vol = float(item['quoteVolume'])
                    if vol < settings["min_volume"]: continue
                    price = float(item['lastPrice'])
                    # MEXC отдаёт priceChangePercent КАК ДОЛЮ (например 0.0787 = 7.87%),
                    # а не готовым процентом, как Binance. Проверено живым запросом к
                    # api.mexc.com: SOLUSDT openPrice 75.21 -> lastPrice 69.29 (-7.87%
                    # реально), а API вернул priceChangePercent "-0.0787". Поэтому
                    # умножение на 100 здесь ОБЯЗАТЕЛЬНО, без него фильтр /d почти
                    # никогда не будет срабатывать.
                    ch_24 = float(item['priceChangePercent']) * 100
                except: continue

                if pair not in price_history or price_history[pair].maxlen != max_pts:
                    price_history[pair] = deque(maxlen=max_pts)

                history = price_history[pair]
                relevant = [p for (t, p) in history if (now - t) <= window_sec]

                have_full_window = (
                    len(history) > 0
                    and (now - history[0][0]) >= window_sec
                )

                if have_full_window and relevant:
                    max_p = max(relevant)
                    drop = ((max_p - price) / max_p) * 100
                else:
                    max_p = price
                    drop = 0.0

                if pair in daily_memory and (now - daily_memory[pair]["time"]) >= 86400:
                    del daily_memory[pair]

                if have_full_window and drop >= settings["percent"] and ch_24 <= settings["day_drop"]:
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
                        ch_7, ch_30 = await get_long_term_changes(pair, max_p)

                        if settings["week_min_drop"] != 0 and ch_7 > settings["week_min_drop"]:
                            should_alert = False
                        elif settings["month_min_drop"] != 0 and ch_30 > settings["month_min_drop"]:
                            should_alert = False
                        elif settings["week_drop"] > 0 and ch_7 < -settings["week_drop"]:
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
                            base_coin = pair.replace("USDT", "")

                            alert_text = (
                                f"🚨 <b>ДАМП: <code>{base_coin}</code></b>\n{label}"
                                f"📉 В окне: <b>-{drop:.2f}%</b>\n"
                                f"📊 За 24 часа: <b>{ch_24:.2f}%</b>\n"
                                f"📆 За 7 дней (до дампа): <b>{ch_7:.2f}%</b>\n"
                                f"🗓 За 30 дней (до дампа): <b>{ch_30:.2f}%</b>\n"
                                f"💵 Было (пик): <code>{max_p}</code>\n"
                                f"💸 Стало (тек): <code>{price}</code>\n"
                                f"💰 Объём: <b>{int(vol):,}$</b>"
                            )

                            if settings["chat_id"]:
                                try:
                                    await bot.send_message(settings["chat_id"], alert_text, parse_mode="HTML")
                                except Exception as e:
                                    print(f"Ошибка отправки сообщения админу: {e}", flush=True)

                            if settings["channel_id"]:
                                try:
                                    await bot.send_message(settings["channel_id"], alert_text, parse_mode="HTML")
                                except Exception as e:
                                    print(f"Не удалось отправить в канал {settings['channel_id']}: {e}", flush=True)

                history.append((now, price))
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
    
