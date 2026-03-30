import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandObject
from aiohttp import web

# =====================
# НАСТРОЙКИ
# =====================

BOT_TOKEN = "8145739398:AAG3dl79hQnSsTe1KoYGt9hvaaUsR3XXllY"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

settings = {"percent": 5.0, "time": 15, "chat_id": None}
price_history = {}
blacklist = set()

# =====================
# TELEGRAM КОМАНДЫ
# =====================

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    settings["chat_id"] = message.chat.id
    await message.answer(
        "🚀 Бот запущен (MEXC)!\n"
        f"Падение: {settings['percent']}% за {settings['time']} мин.\n\n"
        "Команды:\n"
        "/p [число] — % (пример /p 10)\n"
        "/t [число] — минуты (/t 5)\n"
        "/b [монета] — в ЧС (/b BTCUSDT)\n"
        "/ub [монета] — убрать из ЧС\n"
        "/s — статус"
    )

@dp.message(Command("p"))
async def set_percent(message: types.Message, command: CommandObject):
    if command.args:
        settings["percent"] = float(command.args.replace(',', '.'))
        await message.answer(f"✅ Новый %: {settings['percent']}")

@dp.message(Command("t"))
async def set_time(message: types.Message, command: CommandObject):
    if command.args and command.args.isdigit():
        settings["time"] = int(command.args)
        await message.answer(f"✅ Интервал: {settings['time']} мин")

@dp.message(Command("b"))
async def add_blacklist(message: types.Message, command: CommandObject):
    if command.args:
        coin = command.args.strip().upper()
        blacklist.add(coin)
        await message.answer(f"🚫 {coin} в ЧС")

@dp.message(Command("ub"))
async def remove_blacklist(message: types.Message, command: CommandObject):
    if command.args:
        coin = command.args.strip().upper()
        blacklist.discard(coin)
        await message.answer(f"✅ {coin} удалён из ЧС")

@dp.message(Command("s"))
async def status_cmd(message: types.Message):
    bl = ", ".join(blacklist) if blacklist else "пусто"
    await message.answer(
        f"📊 Падение: {settings['percent']}%\n"
        f"⏱ Интервал: {settings['time']} мин\n"
        f"🚫 ЧС: {bl}"
    )

# =====================
# ПАРСИНГ MEXC
# =====================

async def fetch_prices():
    url = "https://api.mexc.com/api/v3/ticker/price"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        item['symbol']: float(item['price'])
                        for item in data
                        if item['symbol'].endswith("USDT")  # фильтр
                    }
    except Exception as e:
        print(f"Ошибка API: {e}")
    return {}

# =====================
# ЛОГИКА БОТА
# =====================

async def parser_task():
    while True:
        if settings["chat_id"]:
            current_prices = await fetch_prices()

            for pair, current_price in current_prices.items():

                if pair in blacklist:
                    continue

                # защита от спама при старте
                if pair not in price_history:
                    price_history[pair] = current_price
                    continue

                old_price = price_history[pair]

                if old_price > 0:
                    drop = ((old_price - current_price) / old_price) * 100

                    if drop >= settings["percent"]:
                        await bot.send_message(
                            settings["chat_id"],
                            f"🚨 ДАМП: {pair}\n"
                            f"Падение: {drop:.2f}%\n"
                            f"Было: {old_price}\n"
                            f"Сейчас: {current_price}\n"
                            f"За: {settings['time']} мин"
                        )

                price_history[pair] = current_price

        await asyncio.sleep(settings["time"] * 60)

# =====================
# ВЕБ-СЕРВЕР (для хостинга)
# =====================

async def handle_ping(request):
    return web.Response(text="Bot is running")

async def main():
    asyncio.create_task(parser_task())

    app = web.Application()
    app.router.add_get('/', handle_ping)

    runner = web.AppRunner(app)
    await runner.setup()

    port = 8080
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
