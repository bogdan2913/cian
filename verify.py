# Dry-run: забирает одну страницу выдачи Циана, нормализует объявления
# и печатает то, что реально вытаскивается. В БД ничего не пишет.
#
#   python verify.py              # Москва, стр. 1
#   python verify.py 2 3          # регион 2 (СПб), стр. 3

import json
import sys

from proxy import get_proxy_url
from fetcher import fetch_html, collect_offers
from normalize import normalize_offer
from breaking_links import _base_url
from logger import logger

QUALITY_FIELDS = ["title", "price", "address", "rooms", "floor",
                  "area_total", "house_type", "year_built"]


def main():
    region = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    page   = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    base = _base_url(region)
    url  = base if page == 1 else f"{base}&p={page}"
    logger.info(f"GET {url}")

    proxy_url = get_proxy_url()
    html, final_url = fetch_html(url, proxy_url)
    if not html:
        logger.error("Страница не загрузилась (блокировка?). Попробуй ещё раз.")
        return

    offers, total = collect_offers(html)
    logger.info(f"Объявлений на странице: {len(offers)} | всего в выдаче: {total}")
    if not offers:
        logger.error("В выдаче нет объявлений — возможно сменилась вёрстка/якорь.")
        return

    rows = [normalize_offer(o) for o in offers]

    # Краткая таблица
    print("\n" + "=" * 100)
    for r in rows:
        rooms = {0: "студия", -1: "своб"}.get(r["rooms"], r["rooms"])
        price = f"{r['price']:,}".replace(",", " ") if r["price"] else "—"
        print(f"{str(r['item_id']):>10} | {rooms!s:>6}к | {str(r['area_total']):>6} м² | "
              f"эт {r['floor']}/{r['total_floors']} | {price:>14} ₽ | "
              f"{(r['house_type'] or '—'):<14} | {(r['city'] or '—'):<16} | "
              f"{(r['title'] or '')[:30]}")

    # Полностью один пример
    print("\n" + "=" * 100 + "\nПОЛНЫЙ ПРИМЕР (первое объявление):")
    print(json.dumps({k: v for k, v in rows[0].items()}, ensure_ascii=False, indent=2))

    # Заполненность колонок по всей странице
    print("\n" + "=" * 100 + "\nЗАПОЛНЕННОСТЬ ПОЛЕЙ (по странице):")
    keys = rows[0].keys()
    for k in keys:
        filled = sum(1 for r in rows if r.get(k) not in (None, "", []))
        bar = "█" * round(filled / len(rows) * 20)
        flag = "  <- quality" if k in QUALITY_FIELDS else ""
        print(f"  {k:<20} {filled:>2}/{len(rows)} {bar}{flag}")

    # Quality% по объявлениям
    print("\nQUALITY% по объявлениям:")
    buckets = {"0%": 0, "1-49%": 0, "50-99%": 0, "100%": 0}
    for r in rows:
        pct = sum(1 for f in QUALITY_FIELDS if r.get(f) is not None) / len(QUALITY_FIELDS) * 100
        if pct == 0:
            buckets["0%"] += 1
        elif pct < 50:
            buckets["1-49%"] += 1
        elif pct < 100:
            buckets["50-99%"] += 1
        else:
            buckets["100%"] += 1
    print(" ", buckets)


if __name__ == "__main__":
    main()
