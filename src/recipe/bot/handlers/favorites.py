import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from recipe.bot.presentation import format_recipe_card, get_cached_dish_preview
from recipe.db.crud import (
    delete_favorite,
    get_or_create_user_settings,
    get_recipe_batch_from_result,
    list_favorite_records,
    save_favorite_from_result,
    save_recipe_result,
    settings_to_preferences,
)
from recipe.llm.generator import generate_similar_recipe
from recipe.schemas.recipe import Recipe

router = Router()
logger = logging.getLogger(__name__)


def _favorite_keyboard(favorite_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Remove from favorites",
                    callback_data=f"favorite_remove:{favorite_id}",
                )
            ]
        ]
    )


async def _send_favorites(
    message: Message,
    session: AsyncSession,
    telegram_id: int,
    redis: Redis,
) -> None:
    favorites = await list_favorite_records(session, telegram_id)
    if not favorites:
        await message.answer("⭐ No favorites yet. Tap Save under a recipe first.")
        return

    await message.answer(f"⭐ Your saved recipes: {len(favorites)}")
    for index, favorite in enumerate(favorites, 1):
        recipe = Recipe.model_validate_json(favorite.recipe_payload)
        image = await get_cached_dish_preview(redis, recipe)
        if image is not None:
            await message.answer_photo(
                photo=image,
                caption=f"Preview: {recipe.title}",
            )
        await message.answer(
            format_recipe_card(recipe, index),
            parse_mode="HTML",
            reply_markup=_favorite_keyboard(favorite.id),
        )


@router.message(Command("favorites"))
async def cmd_favorites(message: Message, session: AsyncSession, redis: Redis) -> None:
    if message.from_user is None:
        await message.answer("Could not identify Telegram user.")
        return

    await _send_favorites(message, session, message.from_user.id, redis)


@router.callback_query(lambda query: query.data == "favorites:show")
async def callback_favorites(query: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    if query.message is not None:
        await _send_favorites(query.message, session, query.from_user.id, redis)
    await query.answer()


@router.callback_query(lambda query: query.data and query.data.startswith("favorite_remove:"))
async def callback_remove_favorite(query: CallbackQuery, session: AsyncSession) -> None:
    if query.data is None:
        await query.answer("Could not remove this favorite.", show_alert=True)
        return

    try:
        favorite_id = int(query.data.split(":", maxsplit=1)[1])
    except ValueError:
        await query.answer("Could not remove this favorite.", show_alert=True)
        return

    favorite = await delete_favorite(session, query.from_user.id, favorite_id)
    if favorite is None:
        await query.answer("This favorite was already removed.", show_alert=True)
        return

    await query.answer("Removed from favorites.", show_alert=True)
    if query.message is not None:
        await query.message.edit_text(
            f"Removed from favorites: {favorite.title}",
            reply_markup=None,
        )


@router.callback_query(lambda query: query.data and query.data.startswith("save:"))
async def callback_save(query: CallbackQuery, session: AsyncSession) -> None:
    if query.data is None:
        await query.answer("Could not save this recipe.", show_alert=True)
        return

    parts = query.data.split(":")
    if len(parts) != 3 or parts[1] == "missing":
        await query.answer("This recipe cannot be saved yet.", show_alert=True)
        return

    try:
        result_id = int(parts[1])
        recipe_index = int(parts[2])
        favorite = await save_favorite_from_result(
            session,
            query.from_user.id,
            result_id,
            recipe_index,
        )
    except ValueError:
        await query.answer("Could not find that recipe anymore.", show_alert=True)
        return

    await query.answer(f"Saved: {favorite.title}", show_alert=True)


@router.callback_query(lambda query: query.data and query.data.startswith("more:"))
async def callback_more_like_this(
    query: CallbackQuery,
    session: AsyncSession,
    redis: Redis,
) -> None:
    if query.data is None:
        await query.answer("Could not generate a similar recipe.", show_alert=True)
        return

    parts = query.data.split(":")
    if len(parts) != 3 or parts[1] == "missing":
        await query.answer("This recipe cannot be used for variations yet.", show_alert=True)
        return

    await query.answer("Generating a similar recipe...")
    if query.message is not None:
        await query.message.answer("🔁 Generating one more recipe like this...")

    try:
        result_id = int(parts[1])
        recipe_index = int(parts[2])
        original_batch = await get_recipe_batch_from_result(
            session,
            query.from_user.id,
            result_id,
        )
        source_recipe = original_batch.recipes[recipe_index - 1]
    except (ValueError, IndexError):
        if query.message is not None:
            await query.message.answer("Could not find that recipe anymore.")
        return

    settings = await get_or_create_user_settings(session, query.from_user.id)
    preferences = settings_to_preferences(settings)
    try:
        similar_batch = await generate_similar_recipe(
            original_batch,
            source_recipe,
            preferences,
        )
    except Exception:
        logger.exception("Could not generate similar recipe for user_id=%s", query.from_user.id)
        if query.message is not None:
            await query.message.answer(
                "Could not generate a similar recipe right now. Try again in a minute."
            )
        return

    result = await save_recipe_result(
        session,
        query.from_user.id,
        "similar",
        similar_batch,
    )
    if query.message is not None:
        from recipe.bot.presentation import send_recipe_batch

        await send_recipe_batch(query.message, similar_batch, result_id=result.id, redis=redis)
