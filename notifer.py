import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

_PROXIES = {"https": "socks5h://127.0.0.1:1080", "http": "socks5h://127.0.0.1:1080"}


def notify(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message},
            proxies=_PROXIES,
            timeout=10,
        )
    except Exception:
        pass
