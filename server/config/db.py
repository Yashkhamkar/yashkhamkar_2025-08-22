from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL")
client = MongoClient(MONGO_URL)

db = client["store-monitor"]


def test_connection():
    try:
        # Ping the MongoDB server
        client.admin.command("ping")
        print(MONGO_URL)
        print(f"✅ Connected to MongoDB at {MONGO_URL}")
    except Exception as e:
        print("❌ MongoDB connection failed:", e)
        raise
