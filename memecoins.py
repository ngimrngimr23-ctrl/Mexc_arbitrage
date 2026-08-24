"""Классификация мемкоинов для сканера MEXC.

Определение идёт слоями, от самого надёжного к запасным:

  0. allowlist        — ручное «никогда не считать мемом» (перебивает всё)
  1. conceptPlates    — зона Meme+ самой биржи из /api/v3/exchangeInfo.
                        Точный, но неполный: это витрина, куда MEXC отбирает
                        монеты вручную (≈200 из ≈1700 пар).
  2. MEME_BASES       — статический список известных мемкоинов.
  3. CoinGecko        — категория meme-token, тысячи тикеров, обновляется сама.
                        Именно она закрывает разрыв между витриной Meme+ и
                        реальным количеством мемов на бирже.
  4. TICKER_PATTERNS  — подстроки в тикере (DOGE, INU, PEPE...).
  5. NAME_RE          — слова в полном названии проекта (fullName из exchangeInfo).

Слои 2-5 нужны потому, что в зону Meme+ попадает меньшинство мемов:
у остальных стоит только тарифная плашка innovation.
"""

import re

# ---------------------------------------------------------------- слой 1
# Подстроки, по которым мем-зона опознаётся в conceptPlates.
# Точное значение слага у MEXC не задокументировано, поэтому ищем по подстроке:
# зона называется "Meme+" / "Memecoin Zone", слаг гарантированно содержит "meme".
# Реальные названия плашек печатаются в лог при старте — см. лог [PLATES].
MEME_PLATE_MARKERS = ("meme",)

# ---------------------------------------------------------------- слой 2
# Стартовый список известных мемкоинов (базовые тикеры, без USDT).
MEME_BASES = {
    "DOGE", "SHIB", "PEPE", "FLOKI", "BONK", "WIF", "BOME", "MEME", "MEW",
    "POPCAT", "BRETT", "MOG", "TURBO", "LADYS", "BABYDOGE", "ELON", "KISHU",
    "AKITA", "HOGE", "SAMO", "MYRO", "SLERF", "PONKE", "WEN", "MICHI",
    "GIGA", "PNUT", "GOAT", "MOODENG", "CHILLGUY", "FARTCOIN", "SPX",
    "TRUMP", "MELANIA", "DEGEN", "TOSHI", "NEIRO", "DOGS", "MUMU", "APU",
    "ANDY", "WOJAK", "PUPS", "LUCE", "SUNDOG", "KOMA", "SIGMA", "BILLY",
    "SNEK", "AIDOGE", "PIT", "LEASH", "BONE", "SAITAMA", "KEKE",
    "RETARDIO", "HARAMBE", "SMOG", "HIPPO", "PEIPEI", "SHIBA", "PORK",
    "TREMP", "BODEN", "JEO",
}
# Намеренно НЕ включены, хотя выглядят «мемно»: SC (Siacoin), BANANA
# (Banana Gun), CATI (Catizen), VOLT. Биржа их мемами не помечает,
# а слой 2 работает без её данных и дал бы ложное срабатывание.

# ---------------------------------------------------------------- слой 3
# Подстроки в тикере. Сюда попадают только достаточно длинные и характерные
# куски — короткие (CAT, BAN, APE) дают слишком много ложных срабатываний
# и вынесены в слой 4, где проверяются по полному названию с границами слов.
TICKER_PATTERNS = (
    "DOGE", "SHIB", "PEPE", "FLOKI", "WOJAK", "ELON", "MEME", "INU",
    "BABYDOGE", "KEKE", "CHAD", "TRUMP", "FART", "CUMMIES", "LAMBO",
)

# ---------------------------------------------------------------- слой 4
# Слова в fullName (полное имя проекта из exchangeInfo). Проверяются
# по границам слов, поэтому "Dog" не срабатывает внутри "Dogma".
NAME_RE = re.compile(
    r"\b("
    r"meme|memes|memecoin|doge|dogecoin|dog|dogs|shiba|inu|cat|cats|kitty|"
    r"pepe|frog|elon|wojak|chad|baby|troll|clown|monkey|ape|penguin|"
    r"hamster|duck|pig|rat|moon|wif|bonk|pump|degen"
    r")\b",
    re.IGNORECASE,
)

# ------------------------------------------------- защита от коллизий тикеров
# В мем-категории CoinGecko тысячи мелких токенов, и их тикеры пересекаются
# с нормальными проектами. Поэтому слою CoinGecko запрещено помечать монету,
# которой сама биржа выдала тематическую плашку: DeFi, Layer2, RWA и т.д.
# Тарифные плашки (innovation, assessment, mainly, newlisting2, standalone,
# Chinese) тематическими не считаются — они стоят у большинства монет.
SERIOUS_PLATES = {
    "ai", "aiagent", "layer2", "web3", "gamefi", "defi", "rwa", "depin",
    "privity", "pow", "nft", "zk", "btcecos", "metaverse", "wlfi", "ton",
    "perpdex", "fantoken", "defenseenergy", "cex", "storage", "metals",
    "metalsfutures", "x402", "infofi", "prediction", "0fees", "desci",
    "hooks", "preipo", "oil", "xstocks",
}


def has_serious_plate(plates):
    """Плашки выглядят как 'mc-trade-zone-DeFi' — берём часть после дефиса."""
    for plate in plates or ():
        if plate.rsplit("-", 1)[-1].lower() in SERIOUS_PLATES:
            return True
    return False


# ---------------------------------------------------------------- защита
# Эти монеты не блокируются никогда, чем бы их ни пометили эвристики.
WHITELIST = {
    "BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "AVAX", "LINK", "DOT", "TON",
    "TRX", "LTC", "BCH", "ATOM", "NEAR", "APT", "SUI", "ARB", "OP", "INJ",
    "MATIC", "POL", "ETC", "XLM", "HBAR", "FIL", "ICP", "IMX", "RNDR",
    "RENDER", "TIA", "SEI", "STX", "AAVE", "UNI", "MKR", "LDO", "CRV",
    "ALGO", "VET", "EOS", "XTZ", "EGLD", "FTM", "S", "GRT", "SAND", "MANA",
    "AXS", "THETA", "RUNE", "KAVA", "ZEC", "DASH", "XMR", "COMP", "SNX",
    "USDC", "USDT", "DAI", "TUSD", "FDUSD", "USDE",
}


def classify(base, full_name=None, plates=None, allowlist=None, cg_symbols=None):
    """Определяет, мемкоин ли это.

    Возвращает (is_meme, reason) — reason всегда объясняет решение
    и пишется в лог, чтобы ложное срабатывание было видно сразу.
    """
    base = (base or "").upper()

    if allowlist and base in allowlist:
        return False, "allowlist"
    if base in WHITELIST:
        return False, "whitelist"

    for plate in plates or ():
        low = plate.lower()
        for marker in MEME_PLATE_MARKERS:
            if marker in low:
                return True, "plate:%s" % plate

    if base in MEME_BASES:
        return True, "static"

    if cg_symbols and base in cg_symbols:
        if has_serious_plate(plates):
            # Тикер совпал с мемом из CoinGecko, но MEXC считает монету
            # тематическим проектом — верим бирже, она знает свой листинг.
            return False, "cg-конфликт-с-плашкой"
        return True, "coingecko"

    for pattern in TICKER_PATTERNS:
        if pattern in base:
            return True, "ticker:%s" % pattern

    if full_name:
        found = NAME_RE.search(full_name)
        if found:
            return True, "name:%s" % found.group(1).lower()

    return False, "-"
