from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from recipe.db.crud import (
    clear_avoid_ingredients,
    get_or_create_user_settings,
    set_avoid_ingredients,
    set_default_servings,
    set_dietary_style,
    set_nutrition_enabled,
    settings_to_preferences,
)

router = Router()

_STYLES = {
    "balanced": "Balanced",
    "high_protein": "High protein",
    "low_calorie": "Low calorie",
    "vegetarian": "Vegetarian",
}


def _settings_keyboard(nutrition_enabled: bool) -> InlineKeyboardMarkup:
    nutrition_text = "🔥 Nutrition: ON" if nutrition_enabled else "🔥 Nutrition: OFF"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=nutrition_text, callback_data="settings:nutrition")],
            [
                InlineKeyboardButton(text="Balanced", callback_data="settings:style:balanced"),
                InlineKeyboardButton(
                    text="High protein",
                    callback_data="settings:style:high_protein",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Low calorie",
                    callback_data="settings:style:low_calorie",
                ),
                InlineKeyboardButton(text="Vegetarian", callback_data="settings:style:vegetarian"),
            ],
            [
                InlineKeyboardButton(text="1 serving", callback_data="settings:servings:1"),
                InlineKeyboardButton(text="2 servings", callback_data="settings:servings:2"),
            ],
            [
                InlineKeyboardButton(text="3 servings", callback_data="settings:servings:3"),
                InlineKeyboardButton(text="4 servings", callback_data="settings:servings:4"),
            ],
        ]
    )


def _format_settings(settings) -> str:
    preferences = settings_to_preferences(settings)
    avoid = ", ".join(preferences.avoid_ingredients) or "none"
    nutrition = "ON" if preferences.nutrition_enabled else "OFF"
    style = _STYLES.get(preferences.dietary_style, preferences.dietary_style)
    return (
        "⚙️ <b>Your recipe settings</b>\n\n"
        f"🔥 Nutrition estimates: <b>{nutrition}</b>\n"
        f"🥗 Dietary style: <b>{style}</b>\n"
        f"🚫 Avoid ingredients: <b>{avoid}</b>\n"
        f"👥 Preferred servings: <b>{preferences.default_servings}</b>\n\n"
        "To avoid ingredients, send:\n"
        "<code>/avoid ketchup, pork, onion</code>\n"
        "To set servings, send <code>/servings 2</code>\n"
        "To clear avoid list, send <code>/avoid_clear</code>."
    )


@router.message(Command("settings"))
async def cmd_settings(message: Message, session: AsyncSession) -> None:
    if message.from_user is None:
        await message.answer("Could not identify Telegram user.")
        return

    settings = await get_or_create_user_settings(session, message.from_user.id)
    await message.answer(
        _format_settings(settings),
        parse_mode="HTML",
        reply_markup=_settings_keyboard(settings.nutrition_enabled),
    )


@router.message(Command("avoid"))
async def cmd_avoid(message: Message, command: CommandObject, session: AsyncSession) -> None:
    if message.from_user is None:
        await message.answer("Could not identify Telegram user.")
        return

    raw = (command.args or "").strip()
    if not raw:
        await message.answer("Send ingredients like: /avoid ketchup, pork, onion")
        return

    ingredients = [item.strip() for item in raw.split(",")]
    settings = await set_avoid_ingredients(session, message.from_user.id, ingredients)
    await message.answer(
        _format_settings(settings),
        parse_mode="HTML",
        reply_markup=_settings_keyboard(settings.nutrition_enabled),
    )


@router.message(Command("avoid_clear"))
async def cmd_avoid_clear(message: Message, session: AsyncSession) -> None:
    if message.from_user is None:
        await message.answer("Could not identify Telegram user.")
        return

    settings = await clear_avoid_ingredients(session, message.from_user.id)
    await message.answer(
        _format_settings(settings),
        parse_mode="HTML",
        reply_markup=_settings_keyboard(settings.nutrition_enabled),
    )


@router.message(Command("servings"))
async def cmd_servings(message: Message, command: CommandObject, session: AsyncSession) -> None:
    if message.from_user is None:
        await message.answer("Could not identify Telegram user.")
        return

    raw = (command.args or "").strip()
    if not raw or not raw.isdigit():
        await message.answer("Send servings like: /servings 2")
        return

    servings = int(raw)
    if not 1 <= servings <= 8:
        await message.answer("Servings should be from 1 to 8.")
        return

    settings = await set_default_servings(session, message.from_user.id, servings)
    await message.answer(
        _format_settings(settings),
        parse_mode="HTML",
        reply_markup=_settings_keyboard(settings.nutrition_enabled),
    )


@router.callback_query(lambda query: query.data == "settings:nutrition")
async def callback_toggle_nutrition(query: CallbackQuery, session: AsyncSession) -> None:
    settings = await get_or_create_user_settings(session, query.from_user.id)
    settings = await set_nutrition_enabled(
        session,
        query.from_user.id,
        not settings.nutrition_enabled,
    )
    if query.message is not None:
        await query.message.answer(
            _format_settings(settings),
            parse_mode="HTML",
            reply_markup=_settings_keyboard(settings.nutrition_enabled),
        )
    await query.answer()


@router.callback_query(lambda query: query.data == "settings:show")
async def callback_show_settings(query: CallbackQuery, session: AsyncSession) -> None:
    settings = await get_or_create_user_settings(session, query.from_user.id)
    if query.message is not None:
        await query.message.answer(
            _format_settings(settings),
            parse_mode="HTML",
            reply_markup=_settings_keyboard(settings.nutrition_enabled),
        )
    await query.answer()


@router.callback_query(lambda query: query.data and query.data.startswith("settings:style:"))
async def callback_set_style(query: CallbackQuery, session: AsyncSession) -> None:
    if query.data is None:
        await query.answer("Could not update style.", show_alert=True)
        return

    style = query.data.rsplit(":", maxsplit=1)[-1]
    if style not in _STYLES:
        await query.answer("Unknown style.", show_alert=True)
        return

    settings = await set_dietary_style(session, query.from_user.id, style)
    if query.message is not None:
        await query.message.answer(
            _format_settings(settings),
            parse_mode="HTML",
            reply_markup=_settings_keyboard(settings.nutrition_enabled),
        )
    await query.answer(f"Style set to {_STYLES.get(style, style)}")


@router.callback_query(lambda query: query.data and query.data.startswith("settings:servings:"))
async def callback_set_servings(query: CallbackQuery, session: AsyncSession) -> None:
    if query.data is None:
        await query.answer("Could not update servings.", show_alert=True)
        return

    raw_servings = query.data.rsplit(":", maxsplit=1)[-1]
    if not raw_servings.isdigit():
        await query.answer("Could not update servings.", show_alert=True)
        return

    settings = await set_default_servings(session, query.from_user.id, int(raw_servings))
    if query.message is not None:
        await query.message.answer(
            _format_settings(settings),
            parse_mode="HTML",
            reply_markup=_settings_keyboard(settings.nutrition_enabled),
        )
    await query.answer(f"Servings set to {settings.default_servings}")
