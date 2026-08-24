"""Классификация мемкоинов для сканера MEXC.

Определение идёт слоями, от самого надёжного к запасным:

  0. allowlist        — ручное «никогда не считать мемом» (перебивает всё)
  1. conceptPlates    — мем-зона самой биржи из /api/v3/exchangeInfo.
                        Самый точный слой: список ведёт MEXC, обновляется сам.
  2. MEME_BASES       — статический список известных мемкоинов.
  3. TICKER_PATTERNS  — подстроки в тикере (DOGE, INU, PEPE...).
  4. NAME_RE          — слова в полном названии проекта (fullName из exchangeInfo).

Слои 2-4 нужны потому, что биржа проставляет плашку не всем монетам
и свежий листинг может пару дней висеть без категории.
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
    "SNEK", "AIDOGE", "VOLT", "PIT", "LEASH", "BONE", "SAITAMA", "KEKE",
    "TOSHIMA", "RETARDIO", "SC", "HARAMBE", "SMOG", "DOGWIFHAT", "CATI",
    "BANANA", "HIPPO", "PEIPEI", "SHIBA", "PORK", "TREMP", "BODEN", "JEO",
}

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


def classify(base, full_name=None, plates=None, allowlist=None):
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

    for pattern in TICKER_PATTERNS:
        if pattern in base:
            return True, "ticker:%s" % pattern

    if full_name:
        found = NAME_RE.search(full_name)
        if found:
            return True, "name:%s" % found.group(1).lower()

    return False, "-"
