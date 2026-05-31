from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    BOT_TOKEN: str = ""

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"

    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "meta-llama/llama-3.3-70b-instruct:free"
    OPENROUTER_VISION_MODEL: str = "openrouter/free"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/photo_recipe"
    REDIS_URL: str = "redis://localhost:6379/0"

    RATE_LIMIT_PHOTOS_PER_HOUR: int = Field(default=5, ge=1)
    CACHE_TTL_SECONDS: int = Field(default=86_400, ge=60)
    IMAGE_CACHE_TTL_SECONDS: int = Field(default=604_800, ge=60)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
