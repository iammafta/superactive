import os
import redis.asyncio as redis
from loguru import logger

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}"

# Global connection pool
_redis_client: redis.Redis | None = None

async def init_redis() -> redis.Redis:
    """Initialize and return the global Redis connection pool."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        try:
            await _redis_client.ping()
            logger.info(f"✅ Connected to Redis at {REDIS_URL}")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            raise
    return _redis_client

async def close_redis():
    """Close the global Redis connection pool."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
        logger.info("🛑 Redis connection closed")

def get_redis() -> redis.Redis:
    """Get the active Redis connection. Call init_redis() on app startup first."""
    global _redis_client
    if _redis_client is None:
        raise RuntimeError("Redis client is not initialized. Call init_redis() first.")
    return _redis_client
