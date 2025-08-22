import csv
from datetime import datetime
from server.config.db import db  # using your existing MongoDB connection

def parse_timestamp(ts: str) -> datetime:
    ts = ts.strip()
    # normalize to ISO format compatible with datetime.fromisoformat
    if ts.endswith(" UTC"):
        ts = ts.replace(" UTC", "+00:00")
    elif ts.endswith("Z"):
        ts = ts.replace("Z", "+00:00")
    return datetime.fromisoformat(ts)

# ---- store_status ----
with open("data/store_status.csv", "r") as f:
    reader = csv.DictReader(f)
    docs = []
    for row in reader:
        docs.append(
            {
                "store_id": row["store_id"],
                "timestamp_utc": parse_timestamp(row["timestamp_utc"]),
                "status": 1 if row["status"].lower() == "active" else 0,
            }
        )
    if docs:
        db["store_status"].insert_many(docs)
    print(f"Inserted {len(docs)} records into store_status")

# ---- business_hours ----
with open("data/menu_hours.csv", "r") as f:
    reader = csv.DictReader(f)
    docs = []
    for row in reader:
        docs.append(
            {
                "store_id": row["store_id"],
                "dayOfWeek": int(row["dayOfWeek"]),
                "start_time_local": row["start_time_local"],
                "end_time_local": row["end_time_local"],
            }
        )
    if docs:
        db["business_hours"].insert_many(docs)
    print(f"Inserted {len(docs)} records into business_hours")

# ---- stores (timezones) ----
with open("data/timezones.csv", "r") as f:
    reader = csv.DictReader(f)
    docs = []
    for row in reader:
        docs.append(
            {
                "store_id": row["store_id"],
                "timezone_str": row.get("timezone_str") or "America/Chicago",
            }
        )
    if docs:
        db["stores"].insert_many(docs)
    print(f"Inserted {len(docs)} records into stores")
