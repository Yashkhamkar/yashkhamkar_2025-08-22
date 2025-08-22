from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import IntEnum


# ---------- ENUMS ----------
class StoreStatusEnum(IntEnum):
    inactive = 0
    active = 1


# ---------- COLLECTION MODELS ----------
class StoreStatus(BaseModel):
    store_id: str
    timestamp_utc: datetime
    status: StoreStatusEnum  # 1 = active, 0 = inactive


class BusinessHours(BaseModel):
    store_id: str
    dayOfWeek: int  # 0=Monday, 6=Sunday
    start_time_local: str  # e.g. "09:00:00"
    end_time_local: str  # e.g. "17:00:00"


class Store(BaseModel):
    store_id: str
    timezone_str: Optional[str] = "America/Chicago"


# ---------- REPORT MODELS ----------
class ReportStatusEnum(IntEnum):
    running = 1
    complete = 2
    failed = 3


class StoreReport(BaseModel):
    report_id: str
    status: ReportStatusEnum = ReportStatusEnum.running
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    file_path: Optional[str] = None  # Path to generated CSV
