# Сбор разнородной выборки НОВОСТРОЕК (первичка) по 20 городам.
# Отличия от main.py (вторичка):
#   - object_type=2 в URL выдачи (новостройки);
#   - потолок ~PRIMARY_MAX_PER_CITY объявлений на город;
#   - разнородность: срез из каждого ценового сегмента (разброс по цене) +
#     не более PRIMARY_MAX_PER_JK лотов из одного ЖК (чтобы не набрать сотни
#     одинаковых студий из одной башни);
#   - source="cian_new" — отделимо от вторички ("cian") в той же таблице.

import math
import time

from config import (CITY_REGIONS, PRIMARY_CITY_NAMES, PRIMARY_MAX_PER_CITY,
                    PRIMARY_MAX_PER_JK, PRIMARY_PAGES_PER_SEGMENT, ROTATE_INTERVAL)
from db import Database, save
from crawler import collect_all_offers
from normalize import normalize_offer
from breaking_links import build_city_urls
from proxy import get_proxy_url, rotate_ip
from notifer import notify
from logger import logger

QUALITY_FIELDS = ["title", "price", "address", "rooms", "floor",
                  "area_total", "house_type", "year_built"]


def _jk_id(offer):
    # id жилого комплекса: сначала из newbuilding, потом из geo.jk
    nb = offer.get("newbuilding") or {}
    if isinstance(nb, dict) and nb.get("id"):
        return nb["id"]
    jk = (offer.get("geo") or {}).get("jk") or {}
    return jk.get("id") if isinstance(jk, dict) else None


proxy_url   = get_proxy_url()
last_rotate = time.time()

cities       = [(n, CITY_REGIONS[n]) for n in PRIMARY_CITY_NAMES]
total_cities = len(cities)
city_times   = []

with Database() as db:
    for city_idx, (city_name, region) in enumerate(cities, 1):
        city_start = time.time()
        logger.info(f"=== {city_name} (region {region}) — новостройки ===")

        segments  = build_city_urls(city_name, region, object_type=2)
        seg_quota = math.ceil(PRIMARY_MAX_PER_CITY / len(segments))  # ровный срез по цене
        logger.info(f"Сегментов по цене: {len(segments)} | квота на сегмент: {seg_quota}")

        saved           = 0
        city_seen       = set()   # item_id, дедуп по городу
        jk_counts       = {}      # лотов взято из каждого ЖК
        quality_buckets = {"0%": 0, "1-49%": 0, "50-99%": 0, "100%": 0}
        skipped_jk      = 0       # отброшено лимитом по ЖК

        for seg_label, seg_url in segments.items():
            if saved >= PRIMARY_MAX_PER_CITY:
                break
            if time.time() - last_rotate > ROTATE_INTERVAL:
                logger.info("Проактивная смена IP...")
                rotate_ip()
                last_rotate = time.time()

            offers = collect_all_offers(proxy_url, seg_url, max_pages=PRIMARY_PAGES_PER_SEGMENT)

            got = 0
            for offer in offers:
                if saved >= PRIMARY_MAX_PER_CITY or got >= seg_quota:
                    break

                iid = str(offer.get("cianId") or offer.get("id"))
                if iid in city_seen:
                    continue

                jk = _jk_id(offer)
                if jk is not None and jk_counts.get(jk, 0) >= PRIMARY_MAX_PER_JK:
                    skipped_jk += 1
                    continue

                try:
                    data = normalize_offer(offer)
                except Exception as e:
                    logger.error(f"Ошибка нормализации: {e}")
                    continue

                data["source"] = "cian_new"
                data["city"]   = city_name

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
                    continue

                try:
                    save(db, data)
                except Exception as e:
                    logger.error(f"Ошибка сохранения {iid}: {e}")
                    continue

                city_seen.add(iid)
                if jk is not None:
                    jk_counts[jk] = jk_counts.get(jk, 0) + 1
                saved += 1
                got   += 1

            logger.info(f"{seg_label}: +{got} (всего по городу: {saved}, ЖК: {len(jk_counts)})")

        logger.info(
            f"\n=== Итог {city_name} (новостройки) ===\n"
            f"Сохранено:       {saved}\n"
            f"Уникальных ЖК:   {len(jk_counts)}\n"
            f"Отброшено по ЖК: {skipped_jk}\n"
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
            f"Циан / новостройки / {city_name} [{city_idx}/{total_cities}]\n"
            f"Сохранено: {saved} (ЖК: {len(jk_counts)})\n"
            f"Осталось: {remaining} {'город' if remaining == 1 else 'городов'}"
            + (f" (~{eta_str})" if remaining > 0 else " — всё готово ✅")
        )

logger.info("Парсинг новостроек завершён")
