"""Второй источник мемкоинов — категория meme-token у CoinGecko.

Зачем: плашка mc-trade-zone-MEME у MEXC — это витрина Meme+, куда биржа
отбирает монеты вручную (≈200 из ≈1700 пар). Мемов на бирже заметно больше,
просто у большинства стоит только тарифная плашка innovation.

CoinGecko ведёт категорию meme-token на тысячи монет и обновляет её сам.
Берём оттуда тикеры и используем как дополнительный слой.

Бесплатный тариф, ключ не обязателен. Если задан COINGECKO_KEY, он уходит
заголовком x-cg-demo-api-key и лимиты становятся выше.
"""

import asyncio
import os

import aiohttp

API = "https://api.coingecko.com/api/v3/coins/markets"
KEY = os.environ.get("COINGECKO_KEY", "").strip()

PER_PAGE = 250
MAX_PAGES = 16      # до 4000 монет
PAUSE = 2.0         # пауза между страницами, чтобы не словить 429
TIMEOUT = 25


async def fetch_meme_symbols(log):
    """Возвращает (множество тикеров, текст ошибки).

    При ошибке на первой же странице множество пустое — вызывающий код
    обязан оставить прежний список, а не затирать его.
    """
    headers = {"accept": "application/json"}
    if KEY:
        headers["x-cg-demo-api-key"] = KEY

    symbols = set()
    err = ""
    try:
        async with aiohttp.ClientSession() as session:
            for page in range(1, MAX_PAGES + 1):
                params = {
                    "vs_currency": "usd",
                    "category": "meme-token",
                    "order": "market_cap_desc",
                    "per_page": str(PER_PAGE),
                    "page": str(page),
                    "sparkline": "false",
                }
                async with session.get(API, params=params, headers=headers,
                                       timeout=TIMEOUT) as resp:
                    if resp.status == 429:
                        err = "лимит запросов (429) на странице %d" % page
                        log("CoinGecko: %s — беру, что успел (%d тикеров)"
                            % (err, len(symbols)), "WARN")
                        break
                    if resp.status != 200:
                        err = "HTTP %s на странице %d" % (resp.status, page)
                        log("CoinGecko: %s" % err, "ERR")
                        break
                    data = await resp.json()

                if not isinstance(data, list) or not data:
                    break

                for coin in data:
                    sym = str(coin.get("symbol") or "").strip().upper()
                    if sym:
                        symbols.add(sym)

                if len(data) < PER_PAGE:
                    break
                await asyncio.sleep(PAUSE)
    except Exception as e:
        err = repr(e)
        log("CoinGecko недоступен: %s" % err, "ERR")

    if symbols:
        log("CoinGecko: получено %d тикеров мемкоинов%s"
            % (len(symbols), " (неполно: %s)" % err if err else ""))
    return symbols, err
