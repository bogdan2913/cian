import random
import time

from config import MAX_PAGES_PER_SESSION
from fetcher import fetch_html, collect_offers
from proxy import rotate_ip
from logger import logger


def collect_all_offers(proxy_url, base_url, max_pages=None):
    # Проходит страницы выдачи и возвращает список «сырых» объявлений (с дедупом
    # по cianId). Каждое объявление уже содержит все поля — карточки не нужны.
    # max_pages ограничивает число страниц (для срезов выборки).
    sep        = "&" if "?" in base_url else "?"
    seen       = set()
    all_offers = []
    empty_runs = 0  # страниц подряд без новых объявлений
    limit      = min(max_pages, MAX_PAGES_PER_SESSION) if max_pages else MAX_PAGES_PER_SESSION

    for page_num in range(1, limit + 1):
        url = base_url if page_num == 1 else f"{base_url}{sep}p={page_num}"

        html = None
        for attempt in range(1, 4):
            html, _ = fetch_html(url, proxy_url)
            if html:
                break
            logger.warning(f"Стр. {page_num}: попытка {attempt}/3 не удалась, ждём...")
            time.sleep(10 * attempt)
        if not html:
            logger.error(f"Стр. {page_num}: не удалось загрузить — ротация IP")
            rotate_ip()
            time.sleep(60)
            html, _ = fetch_html(url, proxy_url)
        if not html:
            logger.error(f"Стр. {page_num}: не удалось даже после ротации, выходим")
            break

        offers, total = collect_offers(html)
        if not offers:
            logger.info(f"Стр. {page_num}: объявлений нет, выходим")
            break

        new = [o for o in offers if str(o.get("cianId") or o.get("id")) not in seen]
        seen.update(str(o.get("cianId") or o.get("id")) for o in new)
        all_offers.extend(new)
        logger.info(f"Стр. {page_num}: +{len(new)} новых (итого: {len(all_offers)} / всего в выдаче: {total})")

        # Циан после реального конца выдачи отдаёт последнюю страницу по кругу —
        # это видно как «+0 новых». Две такие страницы подряд = выдача кончилась,
        # дальше нет смысла листать до 54-й (экономим запросы и снижаем риск блока).
        if not new:
            empty_runs += 1
            if empty_runs >= 2:
                logger.info("Конец выдачи под-запроса (страницы без новых)")
                break
        else:
            empty_runs = 0

        time.sleep(random.uniform(1.5, 3.0))

    return all_offers
