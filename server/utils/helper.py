from datetime import datetime, timedelta
from pymongo import MongoClient
from pytz import UTC, timezone as pytz_timezone
from typing import List, Dict
import math
import os
import time
import csv
from uuid import uuid4
from server.models.models import StoreStatusEnum, BusinessHours, StoreStatus
from server.config.db import db

"""
helper.py
---------
This file calculates how long each store was UP or DOWN.

Steps:
1. Get store info, status logs, and business hours from the database.
2. Fill any missing status times so there are no gaps.
3. Calculate uptime and downtime for:
   - last 1 hour
   - last 24 hours
   - last 7 days
4. Save the final results into a CSV file.
"""

BATCH_SIZE = 250
REPORTS_FOLDER = "reports"
os.makedirs(REPORTS_FOLDER, exist_ok=True)


def get_batch_business_hours(store_ids: List[str]) -> Dict[str, List[BusinessHours]]:
    """
    For each store ID, fetch its business hours from MongoDB.
    If no business hours are set → assume open 24/7.
    """
    bh_map = {}
    # Create empty list for every store first
    for store_id in store_ids:
        bh_map[store_id] = []
        
    # Query DB to fetch hours for these stores
    cursor = db.business_hours.find(
        {"store_id": {"$in": store_ids}},
        {
            "store_id": 1,
            "dayOfWeek": 1,
            "start_time_local": 1,
            "end_time_local": 1,
            "_id": 0,
        },
    )
    # Add records to our dictionary
    for doc in cursor:
        bh_map[doc["store_id"]].append(BusinessHours(**doc))

    # If no records for a store → assume open all day every day
    for store_id, hours in bh_map.items():
        if not hours:
            bh_map[store_id] = [
                BusinessHours(
                    store_id=store_id,
                    dayOfWeek=d,
                    start_time_local="00:00:00",
                    end_time_local="23:59:59",
                )
                for d in range(7)
            ]
    return bh_map


def get_batch_status_records(
    store_ids: List[str], start: datetime, end: datetime
) -> Dict[str, List[StoreStatus]]:
    """
    Fetch store open/closed logs between start and end times.
    Store them as a list for each store.
    """
    record_map = {}
    for store_id in store_ids:
        record_map[store_id] = []
        
    # Query DB for status logs within given time window
    cursor = db.store_status.find(
        {"store_id": {"$in": store_ids}, "timestamp_utc": {"$gte": start, "$lte": end}},
        {"store_id": 1, "timestamp_utc": 1, "status": 1, "_id": 0},
    ).sort([("store_id", 1), ("timestamp_utc", 1)])

    # Add logs to dictionary
    for doc in cursor:
        ts = doc["timestamp_utc"]
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        record_map[doc["store_id"]].append(
            StoreStatus(
                store_id=doc["store_id"],
                timestamp_utc=ts,
                status=StoreStatusEnum(doc["status"]),
            )
        )
    return record_map


def get_batch_timezones(
    store_ids: List[str], default_tz="America/Chicago"
) -> Dict[str, str]:
    """
    Fetch timezone for each store.
    If missing → use default timezone.
    """
    tz_map = {}
    for store_id in store_ids:
        tz_map[store_id] = default_tz

    cursor = db.stores.find(
        {"store_id": {"$in": store_ids}}, {"store_id": 1, "timezone_str": 1, "_id": 0}
    )
    for doc in cursor:
        if "timezone_str" in doc:
            tz_map[doc["store_id"]] = doc["timezone_str"]
    return tz_map


def interpolate_status(records: List[StoreStatus], start: datetime, end: datetime):
    """
    Make sure we have a continuous timeline.
    If data is missing, assume last known status continues.
    """
    if not records:
        # No data → assume store inactive entire period
        return [(start, end, StoreStatusEnum.inactive)]

    intervals = []
    # Go through every status log and build time intervals
    for i in range(len(records) - 1):
        t1, s1 = records[i].timestamp_utc, records[i].status
        t2 = records[i + 1].timestamp_utc
        # Skip if interval is completely outside window
        if t2 < start or t1 > end:
            continue
        intervals.append((max(t1, start), min(t2, end), s1))
    
    # Add last interval up to 'end'
    last_t, last_s = records[-1].timestamp_utc, records[-1].status
    if last_t < end:
        intervals.append((max(last_t, start), end, last_s))
    return intervals


def overlap_minutes(
    start1: datetime, end1: datetime, start2: datetime, end2: datetime
) -> float:
    """
    Calculate overlapping minutes between two time ranges.
    If no overlap → return 0.
    """
    latest_start = max(start1, start2)
    earliest_end = min(end1, end2)
    if latest_start >= earliest_end:
        return 0.0
    return (earliest_end - latest_start).total_seconds() / 60.0


def process_one_store(
    store_id: str,
    now_utc: datetime,
    timezone_str: str,
    business_hours: List[BusinessHours],
    status_records: List[StoreStatus],
) -> Dict:
    """
    For a single store → calculate uptime/downtime
    for last 1 hour, 24 hours, and 7 days.
    """
    tz = pytz_timezone(timezone_str)
    # Define reporting windows
    windows = {
        "hour": now_utc - timedelta(hours=1),
        "day": now_utc - timedelta(days=1),
        "week": now_utc - timedelta(weeks=1),
    }
    results = {}

    for label, start_time in windows.items():
        total_up, total_down = 0.0, 0.0
        # Fill gaps in store status
        status_intervals = interpolate_status(status_records, start_time, now_utc)

        # For each business-hour block of the store
        for bh in business_hours:
            bh_start_local = datetime.combine(
                start_time.date(),
                datetime.strptime(bh.start_time_local, "%H:%M:%S").time(),
            )
            bh_end_local = datetime.combine(
                start_time.date(),
                datetime.strptime(bh.end_time_local, "%H:%M:%S").time(),
            )
            day_cursor = start_time

            # Slide day by day through the window
            while day_cursor < now_utc:
                if day_cursor.weekday() == bh.dayOfWeek:
                    # Convert local BH window to UTC
                    bh_start = tz.localize(
                        bh_start_local.replace(
                            year=day_cursor.year,
                            month=day_cursor.month,
                            day=day_cursor.day,
                        )
                    ).astimezone(UTC)
                    bh_end = tz.localize(
                        bh_end_local.replace(
                            year=day_cursor.year,
                            month=day_cursor.month,
                            day=day_cursor.day,
                        )
                    ).astimezone(UTC)

                    # Check every status interval overlap with BH window
                    for s_start, s_end, status in status_intervals:
                        minutes = overlap_minutes(s_start, s_end, bh_start, bh_end)
                        if minutes > 0:
                            if status == StoreStatusEnum.active:
                                total_up += minutes
                            else:
                                total_down += minutes
                day_cursor += timedelta(days=1)

        # Store results
        if label == "hour":
            results["uptime_last_hour"] = round(total_up, 2)
            results["downtime_last_hour"] = round(total_down, 2)
        else:
            # Convert to hours for day/week
            results[f"uptime_last_{label}"] = round(total_up / 60.0, 2)
            results[f"downtime_last_{label}"] = round(total_down / 60.0, 2)

    return {"store_id": store_id, **results}


def process_stores_in_batches(
    now_utc: datetime, batch_size: int = BATCH_SIZE
) -> List[Dict]:
    """
    Process all stores in batches to avoid memory issues.
    """
    all_stores = []
    
    for doc in db.stores.find({}, {"store_id": 1, "_id": 0}):
        all_stores.append(doc["store_id"])
    
    window_start = now_utc - timedelta(weeks=1)
    results = []
    num_batches = math.ceil(len(all_stores) / batch_size)

    start_time_total = time.time()  # start total timer

    for batch_num in range(num_batches):
        batch = all_stores[batch_num * batch_size : (batch_num + 1) * batch_size]
        print(
            f"Processing batch {batch_num + 1}/{num_batches} ({len(batch)} stores)..."
        )

        # Load all data for this batch
        tz_map = get_batch_timezones(batch)
        bh_map = get_batch_business_hours(batch)
        status_map = get_batch_status_records(batch, window_start, now_utc)

        # Process every store in the batch
        for i, store_id in enumerate(batch):
            store_start_time = time.time()
            res = process_one_store(
                store_id=store_id,
                now_utc=now_utc,
                timezone_str=tz_map[store_id],
                business_hours=bh_map[store_id],
                status_records=status_map[store_id],
            )
            results.append(res)
            elapsed = time.time() - store_start_time
            print(
                f"  [{i+1}/{len(batch)}] Processed store {store_id} in {elapsed:.2f}s"
            )

    total_elapsed = time.time() - start_time_total
    print(f"\n🚀 Total execution time for {len(results)} stores: {total_elapsed:.2f}s")
    print(f"📊 Average time per store: {total_elapsed / len(results):.2f}s")

    return results


def save_report_csv(results: List[Dict]) -> str:
    """
    Save results to a CSV file inside 'reports' folder.
    Returns the file path.
    """
    report_id = str(uuid4())
    file_path = os.path.join(REPORTS_FOLDER, f"report_{report_id}.csv")
    with open(file_path, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "store_id",
                "uptime_last_hour",
                "downtime_last_hour",
                "uptime_last_day",
                "downtime_last_day",
                "uptime_last_week",
                "downtime_last_week",
            ],
        )
        writer.writeheader()
        writer.writerows(results)
    return file_path
