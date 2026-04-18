"""
embeddings.py — Gemini text-embedding-004 wrapper.
Cache job and resume embeddings to avoid re-computing on every score run.
"""
import json
import logging
from datetime import datetime, timezone
from typing import List, Optional

import numpy as np
import google.generativeai as genai
from sqlalchemy import select

from backend.config import settings
from backend.database import AsyncSessionLocal
from backend.models import EmbeddingCache

logger = logging.getLogger(__name__)

genai.configure(api_key=settings.gemini_api_key)

async def get_embedding(text: str, source_id: str, source_type: str) -> List[float]:
    """
    Get embedding for text, checking the cache first.
    source_id: unique ID (job hash or resume ID)
    source_type: "job" | "resume"
    """
    if not settings.enable_embeddings:
        return []

    async with AsyncSessionLocal() as db:
        # 1. Check Cache
        result = await db.execute(
            select(EmbeddingCache).where(
                EmbeddingCache.source_id == str(source_id),
                EmbeddingCache.source_type == source_type
            )
        )
        cached = result.scalars().first()
        if cached:
            return cached.vector

        # 2. Fetch from Gemini
        try:
            if not text or not text.strip():
                logger.warning(f"[Embeddings] Skipping embedding for {source_id}: empty text.")
                return []

            logger.debug(f"[Embeddings] Fetching {source_type} embedding for {source_id}...")
            # Use the verified model name for this API key
            from backend.modules.ai_engine.throttler import gemini_throttler
            await gemini_throttler.throttle()
            
            res = genai.embed_content(
                model="models/gemini-embedding-001",
                content=text,
                task_type="RETRIEVAL_DOCUMENT" if source_type == "job" else "RETRIEVAL_QUERY"
            )
            vector = res["embedding"]

            # 3. Save to Cache
            new_cache = EmbeddingCache(
                source_id=str(source_id),
                source_type=source_type,
                vector=vector,
                created_at=datetime.now(timezone.utc)
            )
            await db.merge(new_cache) # use merge to avoid race condition
            await db.commit()
            
            return vector
            
        except Exception as e:
            logger.error(f"[Embeddings] Gemini API failed: {e}")
            return []

def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not a or not b:
        return 0.0
    arr_a = np.array(a)
    arr_b = np.array(b)
    norm_a = np.linalg.norm(arr_a)
    norm_b = np.linalg.norm(arr_b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(arr_a, arr_b) / (norm_a * norm_b))
