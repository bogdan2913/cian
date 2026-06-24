import json
import random
import time

from curl_cffi import requests as cffi_requests

from config import BLOCK_THRESHOLD
from logger import logger
from proxy import rotate_ip


# Циан фильтрует по TLS fingerprint так же, как Авито: обычный Python-запрос виден
# ещё на TCP-рукопожатии. curl_cffi имитирует fingerprint реального Chrome,
# чередуем версии для разнообразия.
_IMPERSONATE    = ["chrome120", "chrome124", "chrome131"]
_block_attempts = 0  # счётчик блокировок подряд, сбрасывается при успехе

# Якорь, по которому Циан встраивает состояние выдачи в HTML:
#   window._cianConfig['frontend-serp'] = (window._cianConfig['frontend-serp'] || []).concat([...]);
_SERP_ANCHOR = "_cianConfig['frontend-serp'] = (window._cianConfig['frontend-serp'] || []).concat("


def fetch_html(url, proxy_url=None):
    # Возвращает (html, final_url); html=None при неудаче/блокировке.
    global _block_attempts
    try:
        # Новая сессия на каждый запрос — уникальный fingerprint при каждом обращении
        session = cffi_requests.Session(impersonate=random.choice(_IMPERSONATE))
        kwargs  = {"timeout": 40, "allow_redirects": True}
        if proxy_url:
            kwargs["proxy"] = proxy_url
        r = session.get(url, **kwargs)
        final_url = str(getattr(r, "url", None) or url)

        if r.status_code == 200:
            # Qrator отдаёт страницу-заглушку с кодом 200. Отличаем её от реальной
            # выдачи по отсутствию якоря состояния: на капче его нет.
            if _SERP_ANCHOR not in r.text and _looks_blocked(r.text):
                _block_attempts += 1
                logger.warning(f"Похоже на капчу/Qrator (подряд: {_block_attempts}): {url}")
                _maybe_rotate()
                return None, None
            _block_attempts = 0
            return r.text, final_url

        if r.status_code in (403, 429):
            _block_attempts += 1
            logger.warning(f"HTTP {r.status_code} (подряд: {_block_attempts}): {url}")
            _maybe_rotate()
        else:
            logger.warning(f"HTTP {r.status_code}: {url}")
        return None, None
    except Exception as e:
        logger.error(f"fetch_html {url}: {e}")
        return None, None


def _looks_blocked(text):
    # Маркеры челлендж-страницы Qrator. Проверяем только когда якоря выдачи нет,
    # чтобы не ловить ложные срабатывания на словах внутри JS-конфига выдачи.
    markers = ("Доступ ограничен", "Доступ временно", "qrator", "Qrator", "id=\"capova\"")
    return any(m in text for m in markers)


def _maybe_rotate():
    global _block_attempts
    if _block_attempts >= BLOCK_THRESHOLD:
        logger.warning("Достигнут лимит блокировок — ротация IP")
        rotate_ip()
        _block_attempts = 0
        time.sleep(60)
    else:
        time.sleep(random.uniform(10, 20))


def _extract_serp_state(html):
    # Достаём JSON-состояние выдачи. Значение присваивается как
    # ... .concat(<МАССИВ>); — берём массив с балансировкой скобок,
    # т.к. внутри встречаются строки со скобками/кавычками.
    a = html.find(_SERP_ANCHOR)
    if a == -1:
        return {}
    start = html.find(".concat(", a) + len(".concat(")
    depth, i, in_str, esc = 0, start, False, False
    while i < len(html):
        c = html[i]
        if esc:
            esc = False
        elif c == "\\":
            esc = True
        elif c == '"':
            in_str = not in_str
        elif not in_str:
            if c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:
                    break
        i += 1
    try:
        arr = json.loads(html[start:i + 1])
    except ValueError:
        return {}
    # Массив — список объектов {"key": ..., "value": ...}; собираем в словарь
    flat = {x["key"]: x["value"] for x in arr if isinstance(x, dict) and "key" in x}
    return flat.get("initialState", {})


def collect_offers(html):
    # Возвращает (offers, total_offers): offers — список «сырых» объектов-объявлений
    # прямо из выдачи (со всеми полями, включая описание).
    state   = _extract_serp_state(html)
    results = state.get("results", {}) or {}
    offers  = results.get("offers") or []
    total   = results.get("totalOffers")
    return offers, total
