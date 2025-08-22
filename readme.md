# Store Monitor Assessment

This repository contains my submission for the **Store Monitoring Assessment** .  
I decided to use **Python (FastAPI)** and **MongoDB** as the database for this solution.

---

## Overview

The system tracks store uptime and downtime based on periodic status updates.  
The key flow is:

1. **Trigger API** – Starts the report generation process.
2. **Poll API** – Allows checking the status of report generation.
3. **Report API** – Returns a downloadable CSV file containing the final computed results.

---

## How to Run

1. **Clone the repository**  
   ```bash
   git clone https://github.com/<your-username>/yash_2025-08-22.git
   cd yash_2025-08-22
   ```

2. **Install dependencies**  
   ```bash
   pip install -r requirements.txt
   ```

3. **Start MongoDB locally or use a cloud instance (like MongoDB Atlas).**

4. **Run FastAPI application**  
   ```bash
   uvicorn server.main:app --reload
   ```

5. **Available APIs**  
   - `POST /trigger_report` – Trigger report generation  
   - `GET /get_report/{report_id}` – Download the CSV  
   - `GET /get_report_status/{report_id}` – Check status  

---

## Key Implementation Details

- **Optimized helper functions:**  
  - Added **MongoDB indexes** on `store_id` and `timestamp_utc` for faster lookups.  
  - Used **batch processing** to handle large datasets efficiently.  
  - Designed logic to calculate **uptime/downtime accurately within business hours**, using precomputed maps like:
    ```python
    record_map = {}
    for store_id in store_ids:
        record_map[store_id] = []
    ```

- **Clear computation logic:**  
  - The calculation of hours overlap and store status is written step-by-step with detailed comments in `helper.py`.  
  - Avoided compressed dictionary comprehension to keep code easy for beginners to understand.

---

## Sample CSV

A sample report CSV file is included in this repo:  
- [sample_report.csv](reports/report_2bdd3ab1-9bb9-4954-9371-63de00a9e210.csv) *(replace with actual file or link)*

---

## Ideas for Improvement

- **Add caching layer** to reduce redundant calculations when reports are triggered frequently.  
- **Asynchronous processing** using Celery/RQ to handle very large datasets without blocking APIs.  
- **Better error handling and retries** if data sources fail.  
- **Deploy to cloud** (Render/Heroku) with a proper CI/CD pipeline.  
- **Automated tests** to verify business-hour overlap logic.

---

## Demo Video

A 3-minute screen recording (as per requirements) demonstrates the full flow:  
*(Add Google Drive link or GitHub release link here)*

---

## Repository Name

As per instructions:  
```
yash_2025-08-22
```
