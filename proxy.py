import time
import requests
from urllib.parse import quote
from config import PROXY_SERVER, PROXY_USERNAME, PROXY_PASSWORD, PROXY_ROTATE_URL
from logger import logger

_last_rotate = 0
_MIN_ROTATE_INTERVAL = 60  # секунд между ротациями


def get_proxy_url():
    if not PROXY_SERVER:
        return None
    server = PROXY_SERVER
    for prefix in ("https://", "http://"):
        if server.startswith(prefix):
            server = server[len(prefix):]
            break
    if PROXY_USERNAME:
        p = quote(PROXY_PASSWORD, safe="")
        return f"http://{PROXY_USERNAME}:{p}@{server}"
    return f"http://{server}"


def _get_current_ip(proxy_url):
    try:
        r = requests.get("https://api.ipify.org", proxies={"http": proxy_url, "https": proxy_url}, timeout=10)
        return r.text.strip()
    except Exception:
        return "неизвестен"


def rotate_ip():
    global _last_rotate
    if not PROXY_ROTATE_URL:
        return False
    if time.time() - _last_rotate < _MIN_ROTATE_INTERVAL:
        logger.info("Ротация пропущена — слишком рано")
        return False
    try:
        r = requests.get(PROXY_ROTATE_URL, timeout=10)
        if r.status_code == 200:
            _last_rotate = time.time()
            time.sleep(3)  # ждём пока IP реально сменится
            proxy_url = get_proxy_url()
            new_ip = _get_current_ip(proxy_url) if proxy_url else "нет прокси"
            logger.info(f"Ротация IP успешна — новый IP: {new_ip}")
            return True
        logger.warning(f"Ротация IP не удалась: HTTP {r.status_code}")
        return False
    except Exception as e:
        logger.error(f"Ротация IP ошибка: {e}")
        return False
