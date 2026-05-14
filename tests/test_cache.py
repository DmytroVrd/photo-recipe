from recipe.cache.redis_cache import get_cached, photo_hash, set_cached
from recipe.schemas.recipe import RecipeBatch


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def set(self, key: str, value: str, ex: int) -> None:
        self.values[key] = value
        self.ttls[key] = ex


def _batch() -> RecipeBatch:
    return RecipeBatch.model_validate(
        {
            "detected_ingredients": ["tomato"],
            "recipes": [
                {
                    "title": "Tomato Salad",
                    "difficulty": "easy",
                    "total_time_minutes": 5,
                    "servings": 1,
                    "ingredients": [{"name": "tomato", "amount": "1"}],
                    "steps": [{"order": 1, "text": "Slice tomato"}],
                }
            ],
        }
    )


def test_photo_hash_is_stable() -> None:
    assert photo_hash(b"same") == photo_hash(b"same")
    assert photo_hash(b"same") != photo_hash(b"different")


async def test_cache_roundtrip() -> None:
    redis = FakeRedis()
    image = b"image-bytes"
    await set_cached(redis, image, _batch())

    cached = await get_cached(redis, image)

    assert cached is not None
    assert cached.detected_ingredients == ["tomato"]
    assert next(iter(redis.ttls.values())) > 0


async def test_cache_variant_changes_key() -> None:
    redis = FakeRedis()
    image = b"image-bytes"
    await set_cached(redis, image, _batch(), variant="a")

    assert await get_cached(redis, image, variant="b") is None
    assert await get_cached(redis, image, variant="a") is not None
