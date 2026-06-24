import time

from config import CITY_REGIONS, ROTATE_INTERVAL
from db import Database, save
from crawler import collect_all_offers
from normalize import normalize_offer
from breaking_links import build_city_urls
from proxy import get_proxy_url, rotate_ip
from notifer import notify
from logger import logger

QUALITY_FIELDS = ["title", "price", "address", "rooms", "floor",
                  "area_total", "house_type", "year_built"]

proxy_url   = get_proxy_url()
last_rotate = time.time()

cities       = list(CITY_REGIONS.items())
total_cities = len(cities)
city_times   = []

with Database() as db:
    for city_idx, (city_name, region) in enumerate(cities, 1):
        city_start = time.time()
        logger.info(f"=== {city_name} (region {region}) ===")

        # Дробим выдачу города по ценовым диапазонам, чтобы обойти лимит ~1500/запрос
        segments = build_city_urls(city_name, region)
        logger.info(f"Сегментов по цене: {len(segments)}")

        ok              = 0
        seen_ids        = set()  # дедуп объявлений между ценовыми сегментами города
        quality_buckets = {"0%": 0, "1-49%": 0, "50-99%": 0, "100%": 0}
        failed          = 0

        for seg_label, seg_url in segments.items():
            if time.time() - last_rotate > ROTATE_INTERVAL:
                logger.info("Проактивная смена IP...")
                rotate_ip()
                last_rotate = time.time()

            logger.info(f"--- {seg_label} ---")
            offers = collect_all_offers(proxy_url, seg_url)

            for offer in offers:
                try:
                    data = normalize_offer(offer)
                except Exception as e:
                    failed += 1
                    logger.error(f"Ошибка нормализации: {e}")
                    continue

                if data["item_id"] in seen_ids:
                    continue
                seen_ids.add(data["item_id"])

                data["source"] = "cian"
                # Город — из цикла (мы знаем регион), geo даёт поселения Новой Москвы
                data["city"] = city_name

                fill_pct = sum(1 for f in QUALITY_FIELDS if data.get(f) is not None) / len(QUALITY_FIELDS) * 100
                if fill_pct == 0:
                    quality_buckets["0%"] += 1
                elif fill_pct < 50:
                    quality_buckets["1-49%"] += 1
                elif fill_pct < 100:
                    quality_buckets["50-99%"] += 1
                else:
                    quality_buckets["100%"] += 1

                if fill_pct == 0:
                    failed += 1
                    continue

                try:
                    save(db, data)
                    ok += 1
                except Exception as e:
                    failed += 1
                    logger.error(f"Ошибка сохранения {data['item_id']}: {e}")

            logger.info(f"{seg_label}: уникальных за город — {len(seen_ids)}")

        logger.info(
            f"\n=== Итог {city_name} ===\n"
            f"Уникальных:      {len(seen_ids)}\n"
            f"Сохранено:       {ok}\n"
            f"Ошибок/пустых:   {failed}\n"
            f"Качество 0%:     {quality_buckets['0%']}\n"
            f"Качество 1-49%:  {quality_buckets['1-49%']}\n"
            f"Качество 50-99%: {quality_buckets['50-99%']}\n"
            f"Качество 100%:   {quality_buckets['100%']}"
        )

        city_times.append(time.time() - city_start)
        remaining = total_cities - city_idx
        avg       = sum(city_times) / len(city_times)
        eta_sec   = avg * remaining
        if eta_sec >= 3600:
            eta_str = f"{int(eta_sec // 3600)}ч {int(eta_sec % 3600 // 60)}м"
        elif eta_sec >= 60:
            eta_str = f"{int(eta_sec // 60)}м"
        else:
            eta_str = "меньше минуты"

        notify(
            f"Циан / {city_name} [{city_idx}/{total_cities}]\n"
            f"Сохранено: {ok}\n"
            f"Уникальных: {len(seen_ids)}\n"
            f"Осталось: {remaining} {'город' if remaining == 1 else 'городов'}"
            + (f" (~{eta_str})" if remaining > 0 else " — всё готово ✅")
        )

logger.info("Парсинг завершён")
