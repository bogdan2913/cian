# Генератор URL выдачи Циана с дроблением по цене.
# В отличие от Авито (base64-протобаф), у Циана фильтры — обычные query-параметры,
# поэтому генерация тривиальна. Дробим по цене, чтобы обходить лимит ~1500
# объявлений (54 стр. × 28) на один под-запрос.

# Точки разбиения по цене (руб). Подобраны под плотность рынка: чем дешевле
# сегмент, тем он плотнее, поэтому шаг внизу мельче.
_PRICE_BREAKPOINTS = [
    3_000_000, 5_000_000, 7_000_000, 9_000_000,
    *range(10_000_000, 31_000_000, 1_000_000),
    35_000_000, 40_000_000, 50_000_000, 70_000_000,
    100_000_000, 200_000_000, 500_000_000,
]


def _base_url(region):
    # Вторичка + новостройки, продажа, только квартиры (object_type[0]=1)
    return (
        "https://www.cian.ru/cat.php?"
        f"deal_type=sale&engine_version=2&offer_type=flat&object_type%5B0%5D=1&region={region}"
    )


def _fmt(v):
    if v % 1_000_000 == 0:
        return f"{v // 1_000_000}М"
    return str(v)


def build_city_urls(city, region, breakpoints=None):
    # Возвращает {label: url} с разбивкой по ценовым диапазонам.
    points = breakpoints or _PRICE_BREAKPOINTS
    base   = _base_url(region)
    result = {}
    for frm, to in zip([0] + points, points + [0]):
        parts = []
        if frm:
            parts.append(f"minprice={frm}")
        if to:
            parts.append(f"maxprice={to}")
        suffix = ("&" + "&".join(parts)) if parts else ""
        if to == 0:
            label = f"{city} ({_fmt(frm)}+)"
        elif frm == 0:
            label = f"{city} (до {_fmt(to)})"
        else:
            label = f"{city} ({_fmt(frm)}-{_fmt(to)})"
        result[label] = base + suffix
    return result
