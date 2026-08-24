"""Хранилище состояния бота.

Диск на Render эфемерный: filters_state.json переживает рестарт процесса,
но пропадает при каждом редеплое. Upstash Redis решает это — состояние
живёт снаружи и не зависит от контейнера.

Работает через REST API Upstash, поэтому дополнительных зависимостей нет:
хватает уже установленного aiohttp.

Настройка (Render → Environment):
    UPSTASH_REDIS_REST_URL    https://xxxx.upstash.io
    UPSTASH_REDIS_REST_TOKEN  токен из консоли Upstash
    UPSTASH_KEY               необязательно, по умолчанию mexc_dump:state

Если переменные не заданы, бот молча продолжает работать на файле.
"""

import json
import os

import aiohttp

URL = os.environ.get("UPSTASH_REDIS_REST_URL", "").strip().rstrip("/")
TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "").strip()
KEY = os.environ.get("UPSTASH_KEY", "mexc_dump:state").strip()

TIMEOUT = 15


def is_configured():
    return bool(URL and TOKEN)


def describe():
    """Короткое описание для /s — без токена в выводе."""
    if not is_configured():
        return "локальный файл (Upstash не настроен)"
    return "Upstash %s, ключ %s" % (URL.split("//")[-1], KEY)


async def _command(args, log):
    """Выполняет одну команду Redis. Возвращает (результат, текст_ошибки)."""
    if not is_configured():
        return None, "не настроен"
    try:
        headers = {"Authorization": "Bearer %s" % TOKEN}
        async with aiohttp.ClientSession() as session:
            async with session.post(URL, json=args, headers=headers,
                                    timeout=TIMEOUT) as resp:
                body = await resp.text()
                if resp.status != 200:
                    err = "HTTP %s: %s" % (resp.status, body[:200])
                    log("Upstash %s -> %s" % (args[0], err), "ERR")
                    return None, err
                data = json.loads(body)
    except Exception as e:
        err = repr(e)
        log("Upstash %s -> %s" % (args[0], err), "ERR")
        return None, err

    if isinstance(data, dict) and data.get("error"):
        err = str(data["error"])
        log("Upstash %s -> ошибка Redis: %s" % (args[0], err), "ERR")
        return None, err
    return (data or {}).get("result"), ""


async def load(log):
    """Читает состояние. (dict|None, текст_ошибки).

    None без ошибки означает, что ключа ещё нет — это нормальный первый запуск.
    """
    raw, err = await _command(["GET", KEY], log)
    if err:
        return None, err
    if raw is None:
        log("Upstash: ключа %s ещё нет — состояние пустое" % KEY)
        return None, ""
    try:
        data = json.loads(raw)
    except Exception as e:
        log("Upstash: в ключе %s лежит не JSON (%r) — игнорирую" % (KEY, e), "ERR")
        return None, "битый JSON"
    if not isinstance(data, dict):
        log("Upstash: в ключе %s не объект — игнорирую" % KEY, "ERR")
        return None, "не объект"
    log("Upstash: состояние прочитано (%d полей)" % len(data))
    return data, ""


async def save(payload, log):
    """Пишет состояние. Возвращает текст ошибки ('' если всё хорошо)."""
    _, err = await _command(["SET", KEY, json.dumps(payload, ensure_ascii=False)], log)
    if not err:
        log("Upstash: состояние сохранено", "DEBUG")
    return err
