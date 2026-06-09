import asyncio
import logging
from typing import Any

from aiogram import F, Router
from aiogram.types import Message
from aiogram.utils.chat_action import ChatActionSender
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from recipe.bot.presentation import send_recipe_batch
from recipe.cache.redis_cache import get_cached, set_cached
from recipe.db.crud import (
    get_or_create_user,
    get_or_create_user_settings,
    save_recipe_result,
    settings_to_preferences,
)
from recipe.vision.analyzer import analyze_photo

logger = logging.getLogger(__name__)
router = Router()

_ANALYSIS_RETRY_DELAYS_SECONDS = (5,)


async def _analyze_photo_with_retries(image_bytes: bytes, preferences, user_id: int):
    for attempt in range(len(_ANALYSIS_RETRY_DELAYS_SECONDS) + 1):
        try:
            return await asyncio.to_thread(analyze_photo, image_bytes, "image/jpeg", preferences)
        except Exception:
            if attempt >= len(_ANALYSIS_RETRY_DELAYS_SECONDS):
                raise

            delay = _ANALYSIS_RETRY_DELAYS_SECONDS[attempt]
            logger.warning(
                "Photo analysis attempt %s failed for user_id=%s; retrying in %ss",
                attempt + 1,
                user_id,
                delay,
                exc_info=True,
            )
            await asyncio.sleep(delay)

    raise RuntimeError("Photo analysis failed unexpectedly")


@router.message(F.photo)
async def handle_photo(message: Message, session: AsyncSession, redis: Redis) -> None:
    if message.from_user is None:
        await message.answer("Could not identify Telegram user.")
        return

    logger.info("Received photo from user_id=%s", message.from_user.id)
    await get_or_create_user(session, message.from_user.id, message.from_user.username)
    user_settings = await get_or_create_user_settings(session, message.from_user.id)
    preferences = settings_to_preferences(user_settings)
    cache_variant = preferences.cache_key()

    photo = message.photo[-1]
    cached_batch = None
    cached_result_id = None
    await message.answer("📸 Photo received. Checking cache and preparing analysis...")
    async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id):
        try:
            file = await message.bot.get_file(photo.file_id)
            buffer: Any = await message.bot.download_file(file.file_path)
            image_bytes = buffer.read()
        except Exception:
            logger.exception("Could not download Telegram photo")
            await message.answer("Could not download this photo from Telegram. Try again.")
            return

        cached = await get_cached(redis, image_bytes, variant=cache_variant)
        if cached:
            logger.info("Photo cache hit for user_id=%s", message.from_user.id)
            result = await save_recipe_result(
                session,
                message.from_user.id,
                "photo",
                cached,
                from_cache=True,
            )
            cached_batch = cached
            cached_result_id = result.id
        else:
            await message.answer("🧊 Analyzing your fridge...")
            try:
                batch = await _analyze_photo_with_retries(
                    image_bytes,
                    preferences,
                    message.from_user.id,
                )
            except Exception:
                logger.exception("Photo analysis failed for user_id=%s", message.from_user.id)
                await message.answer(
                    "The AI service is busy right now. I tried a few times, but it still did not "
                    "answer. Please resend the photo in a minute."
                )
                return
            await set_cached(redis, image_bytes, batch, variant=cache_variant)

    if cached_batch is not None:
        await send_recipe_batch(
            message,
            cached_batch,
            result_id=cached_result_id,
            from_cache=True,
            redis=redis,
        )
        return

    result = await save_recipe_result(session, message.from_user.id, "photo", batch)
    logger.info(
        "Photo analysis complete for user_id=%s result_id=%s",
        message.from_user.id,
        result.id,
    )
    await send_recipe_batch(message, batch, result_id=result.id, redis=redis)
