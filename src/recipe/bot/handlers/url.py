import re

from aiogram import F, Router
from aiogram.types import Message
from aiogram.utils.chat_action import ChatActionSender
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from recipe.bot.presentation import send_recipe_batch
from recipe.db.crud import (
    get_or_create_user,
    get_or_create_user_settings,
    save_recipe_result,
    settings_to_preferences,
)
from recipe.scraper.playwright_scraper import url_to_recipe_batch

router = Router()

URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)


@router.message(F.text.regexp(URL_RE))
async def handle_url(message: Message, session: AsyncSession, redis: Redis) -> None:
    match = URL_RE.search(message.text or "")
    if not match:
        return
    if message.from_user is None:
        await message.answer("Could not identify Telegram user.")
        return

    await get_or_create_user(session, message.from_user.id, message.from_user.username)
    user_settings = await get_or_create_user_settings(session, message.from_user.id)
    preferences = settings_to_preferences(user_settings)
    url = match.group(0).rstrip(").,]")

    await message.answer(f"🔎 Scraping recipe from:\n{url}")
    async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id):
        try:
            batch = await url_to_recipe_batch(url, preferences=preferences)
        except Exception as exc:
            await message.answer(
                "Could not extract recipe from this URL.\n"
                "Try a direct recipe page, for example allrecipes.com/recipe/...\n"
                f"Error: {exc}"
            )
            return

    result = await save_recipe_result(session, message.from_user.id, "url", batch, source_url=url)
    await send_recipe_batch(message, batch, result_id=result.id, redis=redis)
