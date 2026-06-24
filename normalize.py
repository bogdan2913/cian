from datetime import datetime


# Материал дома Циана → человекочитаемый тип (в стиле house_type Авито)
_MATERIAL = {
    "monolith":          "Монолитный",
    "monolithBrick":     "Монолитно-кирпичный",
    "brick":             "Кирпичный",
    "panel":             "Панельный",
    "block":             "Блочный",
    "wood":              "Деревянный",
    "stalin":            "Сталинский",
    "old":               "Старый фонд",
    "boards":            "Щитовой",
    "aerocreteBlock":    "Газобетонный блок",
    "gasSilicateBlock":  "Газосиликатный блок",
    "foamConcreteBlock": "Пенобетонный блок",
}

# Отделка Циана → человекочитаемый ремонт (в стиле renovation Авито)
_DECORATION = {
    "without":  "Без отделки",
    "rough":    "Черновая",
    "preFine":  "Предчистовая",
    "fine":     "Чистовая",
    "cosmetic": "Косметический",
    "euro":     "Евроремонт",
    "design":   "Дизайнерский",
}

# Тип сделки/продажи Циана → условия продажи (в стиле sale_conditions Авито)
_SALE_TYPE = {
    "free":        "Свободная продажа",
    "alternative": "Альтернатива",
    "dupt":        "Договор уступки",
    "dduSale":     "Переуступка ДДУ",
}


def _city_from_geo(geo):
    # Город — последний (самый конкретный) узел типа "location":
    # для Москвы это «Москва», для региона — «<область> → <город>».
    name = None
    for node in geo.get("address") or []:
        if node.get("type") == "location":
            name = node.get("name")
    return name


def _published_at(ts):
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M")
    except (ValueError, OSError, OverflowError):
        return None


def _rooms(offer):
    flat_type = offer.get("flatType")
    if flat_type == "studio":
        return 0
    if flat_type == "openPlan":
        return -1  # свободная планировка (как у Авито)
    return offer.get("roomsCount")


def normalize_offer(offer):
    geo      = offer.get("geo") or {}
    building = offer.get("building") or {}
    terms    = offer.get("bargainTerms") or {}
    coords   = geo.get("coordinates") or {}
    parking  = building.get("parking") or {}

    def num(v):
        # Площади приходят строками ("124.9"); цена — числом
        if v is None:
            return None
        try:
            return float(str(v).replace(",", "."))
        except ValueError:
            return None

    undergrounds = [u.get("name") for u in (geo.get("undergrounds") or []) if u.get("name")]

    return {
        "item_id":            str(offer.get("cianId") or offer.get("id")),
        "url":                (offer.get("fullUrl") or "").split("?")[0],
        # У части объявлений своего заголовка нет — подставляем авто-сводку Циана
        # ("3-комн.кв. · 124,9 м² · 5/7 этаж"), чтобы title не пустовал.
        "title":              offer.get("title") or offer.get("formattedFullInfo"),
        "price":              terms.get("priceRur") or terms.get("price"),
        "published_at":       _published_at(offer.get("addedTimestamp")),
        "city":               _city_from_geo(geo),
        "address":            geo.get("userInput"),
        "metro":              undergrounds or None,
        "description":        offer.get("description"),
        "property_type":      "Апартаменты" if offer.get("isApartments") else "Квартира",
        "rooms":              _rooms(offer),
        "floor":              offer.get("floorNumber"),
        "area_total":         num(offer.get("totalArea")),
        "area_living":        num(offer.get("livingArea")),
        "area_kitchen":       num(offer.get("kitchenArea")),
        "renovation":         _DECORATION.get(offer.get("decoration")),
        "furniture":          _furniture(offer.get("hasFurniture")),
        "balcony":            (offer.get("balconiesCount") or 0) > 0,
        "loggia":             (offer.get("loggiasCount") or 0) > 0,
        "house_type":         _MATERIAL.get(building.get("materialType")),
        "total_floors":       building.get("floorsCount"),
        "year_built":         building.get("buildYear"),
        "passenger_elevator": building.get("passengerLiftsCount"),
        "cargo_elevator":     building.get("cargoLiftsCount"),
        "parking":            parking.get("type"),
        "demolition_planned": bool(offer.get("demolishedInMoscowProgramm")),
        "sale_conditions":    _SALE_TYPE.get(terms.get("saleType")),
        "lat":                coords.get("lat"),
        "lon":                coords.get("lng"),
    }


def _furniture(has):
    if has is None:
        return None
    return "Есть" if has else "Нет"
