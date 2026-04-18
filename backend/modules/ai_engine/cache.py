import json
import logging
from typing import Optional, Any, Dict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models import AIProcessCache

logger = logging.getLogger(__name__)

async def get_cached_ai_result(db: AsyncSession, cache_key: str) -> Optional[Dict[str, Any]]:
    """Fetch a cached AI result if it exists."""
    result = await db.execute(
        select(AIProcessCache).where(AIProcessCache.cache_key == cache_key)
    )
    cached = result.scalars().first()
    if cached:
        logger.debug(f"[AICache] HIT for {cache_key}")
        return cached.response_json
    return None

async def set_cached_ai_result(db: AsyncSession, cache_key: str, response: Dict[str, Any]):
    """Cache an AI result."""
    try:
        new_cache = AIProcessCache(
            cache_key=cache_key,
            response_json=response
        )
        await db.merge(new_cache)
        await db.commit()
        logger.debug(f"[AICache] SAVED for {cache_key}")
    except Exception as e:
        await db.rollback()
        logger.error(f"[AICache] Failed to save {cache_key}: {e}")
