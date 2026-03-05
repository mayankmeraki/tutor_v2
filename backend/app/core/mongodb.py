import certifi
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import settings

_client: AsyncIOMotorClient | None = None


def get_mongo_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(
            settings.MONGODB_URI,
            tlsCAFile=certifi.where(),
        )
    return _client


def get_mongo_db():
    return get_mongo_client()["capacity"]


def get_tutor_db():
    """Returns the 'tutor_v2' database for session storage."""
    return get_mongo_client()["tutor_v2"]
