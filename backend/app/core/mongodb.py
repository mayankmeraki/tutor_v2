import os

import certifi
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import settings

_client: AsyncIOMotorClient | None = None
_DB_NAME = os.environ.get("MONGODB_DB", "myprofessor")


def get_mongo_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(
            settings.MONGODB_URI,
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            socketTimeoutMS=30000,
            maxPoolSize=20,
            retryWrites=True,
        )
    return _client


def get_mongo_db():
    return get_mongo_client()[_DB_NAME]


def get_tutor_db():
    """Returns the main database for session storage."""
    return get_mongo_client()[_DB_NAME]
