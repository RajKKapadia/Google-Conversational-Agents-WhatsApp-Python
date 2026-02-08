"""
Redis pool management and enqueue helpers for ARQ-based async task queue.
"""

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from src import logging
from src.config import REDIS_URL

logger = logging.getLogger(__name__)

_pool: ArqRedis | None = None


async def init_pool() -> ArqRedis:
    """Initialize the ARQ Redis connection pool. Called from FastAPI lifespan."""
    global _pool
    _pool = await create_pool(RedisSettings.from_dsn(REDIS_URL))
    logger.info("ARQ Redis pool initialized")
    return _pool


async def close_pool() -> None:
    """Close the ARQ Redis connection pool. Called from FastAPI lifespan."""
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None
        logger.info("ARQ Redis pool closed")


def get_pool() -> ArqRedis:
    """Return the module-level ARQ Redis pool singleton."""
    if _pool is None:
        raise RuntimeError("Redis pool not initialized. Call init_pool() first.")
    return _pool


async def enqueue_message_task(
    sender: str,
    message_type: str,
    content_data: str | dict | list | None,
    message_id: str,
) -> None:
    """
    Enqueue a process_message job to Redis.

    Args:
        sender: WhatsApp sender phone number
        message_type: Message type value string (e.g. "text", "image")
        content_data: Serialized content (str, dict, list[dict], or None)
        message_id: WhatsApp message ID
    """
    pool = get_pool()
    job = await pool.enqueue_job(
        "process_message",
        sender,
        message_type,
        content_data,
        message_id,
    )
    logger.info(f"Enqueued process_message job {job.job_id} for message {message_id} from {sender}")
