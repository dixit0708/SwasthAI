# pyrefly: ignore [missing-import]
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class MongoDB:
    client: AsyncIOMotorClient = None
    db = None

db_manager = MongoDB()

async def connect_to_mongo():
    try:
        logger.info("Connecting to MongoDB...")
        db_manager.client = AsyncIOMotorClient(settings.MONGODB_URL, serverSelectionTimeoutMS=2000)
        db_manager.db = db_manager.client[settings.DATABASE_NAME]
        await db_manager.db["users"].create_index("email", unique=True)
        doctors = db_manager.db["doctors"]
        await doctors.create_index("source_id", unique=True)
        await doctors.create_index([("is_active", 1), ("listing_priority", 1), ("name", 1)])
        await doctors.create_index("specialties")
        logger.info("Connected to MongoDB.")
    except Exception as e:
        logger.warning(f"Could not connect to MongoDB. App will run in UI-only mode. Error: {e}")

async def close_mongo_connection():
    logger.info("Closing MongoDB connection...")
    if db_manager.client:
        db_manager.client.close()
    logger.info("MongoDB connection closed.")

