from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from recipe.analytics.stats import get_user_stats

router = Router()


def _format_stats(stats: dict) -> str:
    top_ingredients = "\n".join(
        f"  {index + 1}. {ingredient}"
        for index, ingredient in enumerate(stats["top_ingredients"])
    ) or "  none yet"

    return (
        "Your recipe stats\n\n"
        f"Total recipes generated: {stats['total_recipes']}\n"
        f"From photos: {stats['photo_count']}\n"
        f"From URLs: {stats['url_count']}\n"
        f"Cache hits: {stats['cache_hits']}\n\n"
        f"Top ingredients you have:\n{top_ingredients}"
    )


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    if message.from_user is None:
        await message.answer("Could not identify Telegram user.")
        return

    stats = await get_user_stats(message.from_user.id)
    if stats.get("status") == "no_data":
        await message.answer("No data yet. Send a fridge photo or recipe URL first.")
        return

    await message.answer(_format_stats(stats))


@router.callback_query(lambda query: query.data == "stats")
async def callback_stats(query: CallbackQuery) -> None:
    stats = await get_user_stats(query.from_user.id)
    if stats.get("status") == "no_data":
        await query.message.answer("No data yet. Send a fridge photo or recipe URL first.")
    else:
        await query.message.answer(_format_stats(stats))
    await query.answer()

