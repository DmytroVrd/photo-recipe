from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from recipe.config import settings


class DBSessionMiddleware(BaseMiddleware):
    def __init__(self, session_pool: async_sessionmaker[AsyncSession]) -> None:
        self.session_pool = session_pool

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with self.session_pool() as session:
            data["session"] = session
            return await handler(event, data)


class RedisMiddleware(BaseMiddleware):
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["redis"] = self.redis
        return await handler(event, data)


class PhotoRateLimitMiddleware(BaseMiddleware):
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        message = event if isinstance(event, Message) else None
        if message is None or not getattr(message, "photo", None):
            return await handler(event, data)

        user = message.from_user
        if user is None:
            return await handler(event, data)

        hour = datetime.utcnow().strftime("%Y%m%d%H")
        key = f"rate:photo:{user.id}:{hour}"
        count = await self.redis.incr(key)
        if count == 1:
            await self.redis.expire(key, 3600)

        limit = settings.RATE_LIMIT_PHOTOS_PER_HOUR
        if count > limit:
            await message.answer(f"Limit reached: {limit} photos per hour. Try again later.")
            return None

        return await handler(event, data)
