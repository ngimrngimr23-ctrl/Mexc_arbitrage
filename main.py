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
    "check_interval": 30,  # Частота проверки (сек)
    "min_volume": 100000,  # Мин. объем ($)
    "day_drop": -15.0,     # НЕ показывать, если падение сильнее этого (например -15)
    "cooldown_min": 5,     # Пауза между сигналами (мин)
    "week_drop": 0.0,      # Фильтр 7 дней (0=выкл)
    "month_drop": 0.0,     # Фильтр 30 дней (0=выкл)
    "chat_id": None,
    "channel_id": os.environ.get("CHANNEL_ID", None) 
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
        "🚀 <b>Бот запущен. Сигналы копируются нажатием на имя монеты.</b>\n\n"
        f"📢 Канал: <b>{settings['channel_id'] or '❌ Не настроен'}</b>\n"
        "⚙️ <b>Команды:</b> /p, /d, /w, /m, /v, /channel, /test, /s", parse_mode="HTML")

@dp.message(Command("channel"))
async def set_channel(message: types.Message, command: CommandObject):
    if command.args:
                      daily_memory[pair] = {
                                        "time": daily_memory[pair]["time"] if pair in daily_memory else now,
                                        "price": price,
                                        "last_msg": now
                                    }
                                    
                                    label = "🔥 <b>ПОВТОРНЫЙ ДАМП (x2)</b>\n" if is_repeat else ""
                                    
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
                                    
                                    # Отправляем в личку
                                    await bot.send_message(settings["chat_id"], msg_text, parse_mode="HTML")
                                    
                                    # Отправляем в канал
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
    
