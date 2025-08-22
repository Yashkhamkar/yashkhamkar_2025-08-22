from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from server.utils.helper import process_stores_in_batches, save_report_csv
from server.config.db import db
from server.models.models import StoreReport, ReportStatusEnum
from datetime import datetime
from pytz import UTC
from uuid import uuid4
import os
from dotenv import load_dotenv

load_dotenv()
base_url = os.getenv("base_url", "")  # Must be set in .env, e.g. http://127.0.0.1:8000

router = APIRouter()


def generate_report(report_id: str):
    """Background task for generating report and updating DB state."""
    try:
        # Determine current timestamp based on latest store_status record
        max_doc = db.store_status.find_one(sort=[("timestamp_utc", -1)])
        now_utc = (
            max_doc["timestamp_utc"].replace(tzinfo=UTC)
            if max_doc
            else datetime.utcnow().replace(tzinfo=UTC)
        )

        # Process data and save CSV
        results = process_stores_in_batches(now_utc)
        file_path = save_report_csv(results)

        # Update report in DB
        db.store_reports.update_one(
            {"report_id": report_id},
            {
                "$set": {
                    "status": ReportStatusEnum.complete,
                    "file_path": file_path,
                    "completed_at": datetime.utcnow().replace(tzinfo=UTC),
                }
            },
        )

    except Exception as e:
        # Mark report as failed
        db.store_reports.update_one(
            {"report_id": report_id},
            {
                "$set": {
                    "status": ReportStatusEnum.failed,
                    "error": str(e),
                }
            },
        )


@router.post("/trigger_report")
def trigger_report(background_tasks: BackgroundTasks):
    """Trigger report generation asynchronously and save metadata in MongoDB."""
    report_id = str(uuid4())
    new_report = StoreReport(report_id=report_id, status=ReportStatusEnum.running)
    db.store_reports.insert_one(new_report.model_dump())  # Persist initial state

    # Launch background processing
    background_tasks.add_task(generate_report, report_id)

    return {"report_id": report_id}


@router.get("/get_report/{report_id}")
async def get_report(report_id: str):
    """Check the status of a report or return the CSV URL if complete."""
    report_doc = db.store_reports.find_one({"report_id": report_id}, {"_id": 0})
    if not report_doc:
        raise HTTPException(status_code=404, detail="Report not found")

    status = ReportStatusEnum(report_doc["status"])

    if status == ReportStatusEnum.running:
        return JSONResponse(status_code=200, content={"status": "Running"})
    elif status == ReportStatusEnum.failed:
        return JSONResponse(
            status_code=500,
            content={"status": "Failed", "error": report_doc.get("error")},
        )
    else:
        report_filename = os.path.basename(report_doc["file_path"])
        report_url = f"/reports/{report_filename}"
        return JSONResponse(
            status_code=200,
            content={
                "status": "Complete",
                "report_url": f"{base_url}{report_url}",
            },
        )
