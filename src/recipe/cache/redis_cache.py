import hashlib
import logging

from redis.asyncio import Redis

from recipe.config import settings
from recipe.schemas.recipe import RecipeBatch

logger = logging.getLogger(__name__)


def photo_hash(image_bytes: bytes) -> str:
    return hashlib.sha256(image_bytes).hexdigest()


def _cache_key(image_bytes: bytes, variant: str = "") -> str:
    suffix = f":{variant}" if variant else ""
    return f"recipe:photo:{photo_hash(image_bytes)}{suffix}"


async def get_cached(redis: Redis, image_bytes: bytes, variant: str = "") -> RecipeBatch | None:
    key = _cache_key(image_bytes, variant)
    raw = await redis.get(key)
    if raw is None:
        return None
    try:
        return RecipeBatch.model_validate_json(raw)
    except Exception:
        logger.warning("Invalid cached recipe payload for key %s", key, exc_info=True)
        return None


async def set_cached(
    redis: Redis,
    image_bytes: bytes,
    result: RecipeBatch,
    variant: str = "",
) -> None:
    key = _cache_key(image_bytes, variant)
    await redis.set(key, result.model_dump_json(), ex=settings.CACHE_TTL_SECONDS)
