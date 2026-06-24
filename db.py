import psycopg2
from config import DATABASE_URL


_COLUMNS = [
    "item_id", "source", "city", "url", "title", "price", "published_at",
    "address", "metro", "description",
    "property_type", "rooms", "room_type", "floor",
    "area_total", "area_living", "area_kitchen", "ceiling_height",
    "renovation", "bathroom", "windows", "furniture", "appliances",
    "balcony", "loggia", "wardrobe", "panoramic_windows", "warm_floor",
    "house_type", "total_floors", "year_built",
    "passenger_elevator", "cargo_elevator", "yard", "parking",
    "concierge", "garbage_chute", "gas", "demolition_planned",
    "sale_method", "sale_conditions", "developer", "sale_type",
    "lat", "lon",
]


class Database:
    def __init__(self, url=None):
        self._conn = psycopg2.connect(url or DATABASE_URL)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def execute(self, sql, params=None):
        with self._conn.cursor() as cur:
            try:
                cur.execute(sql, params)
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def fetchall(self, sql, params=None):
        with self._conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    def close(self):
        self._conn.close()


def save(db, data):
    row = {col: data[col] for col in _COLUMNS if col in data}
    cols = [c for c in _COLUMNS if c in row]
    updates = ", ".join(
        f"{c} = EXCLUDED.{c}" for c in cols if c not in ("item_id", "source")
    )
    sql = (
        f"INSERT INTO listings ({', '.join(cols)}) "
        f"VALUES ({', '.join(['%s'] * len(cols))}) "
        f"ON CONFLICT (item_id, source) DO UPDATE SET {updates}, parsed_at = NOW()"
    )
    db.execute(sql, [row[c] for c in cols])


def get_listings(db, city=None, source=None):
    conditions, params = [], []
    if city:
        conditions.append("city = %s")
        params.append(city)
    if source:
        conditions.append("source = %s")
        params.append(source)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return db.fetchall(f"SELECT * FROM listings {where}", params or None)
