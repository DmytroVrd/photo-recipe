import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from redis.asyncio import Redis

from recipe.bot.handlers import favorites, photo, start, stats, url
from recipe.bot.handlers import settings as settings_handler
from recipe.bot.middleware import DBSessionMiddleware, PhotoRateLimitMiddleware, RedisMiddleware
from recipe.config import settings
from recipe.db.session import async_session


async def setup_bot_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Start bot and show main menu"),
            BotCommand(command="help", description="How to use the bot"),
            BotCommand(command="settings", description="Nutrition, style, servings, avoid list"),
            BotCommand(command="avoid", description="Avoid ingredients, e.g. /avoid ketchup"),
            BotCommand(command="avoid_clear", description="Clear avoided ingredients"),
            BotCommand(command="servings", description="Set servings, e.g. /servings 2"),
            BotCommand(command="favorites", description="Show saved recipes"),
            BotCommand(command="stats", description="Show recipe history stats"),
        ]
    )


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    if not settings.BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is required")

    bot = Bot(token=settings.BOT_TOKEN)
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    dispatcher = Dispatcher()

    dispatcher.update.middleware(DBSessionMiddleware(async_session))
    dispatcher.update.middleware(RedisMiddleware(redis))
    dispatcher.message.middleware(PhotoRateLimitMiddleware(redis))

    dispatcher.include_router(start.router)
    dispatcher.include_router(settings_handler.router)
    dispatcher.include_router(favorites.router)
    dispatcher.include_router(stats.router)
    dispatcher.include_router(url.router)
    dispatcher.include_router(photo.router)

    try:
        await setup_bot_commands(bot)
        await dispatcher.start_polling(bot)
    finally:
        await redis.aclose()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
