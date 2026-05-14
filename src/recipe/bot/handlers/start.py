from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from recipe.bot.keyboards import main_menu_keyboard
from recipe.db.crud import get_or_create_user

router = Router()

_HELP_TEXT = (
    "Hi. Send me a fridge photo and I will generate 3 recipes from visible ingredients.\n\n"
    "You can also send a recipe URL and I will normalize it into the same format.\n\n"
    "Commands:\n"
    "/settings - nutrition, style, servings, avoid list\n"
    "/avoid ketchup, pork - ingredients to avoid\n"
    "/avoid_clear - clear avoided ingredients\n"
    "/servings 2 - preferred servings\n"
    "/favorites - saved recipes\n"
    "/stats - recipe history stats\n"
    "/help - show this help"
)


@router.message(Command("start"))
async def cmd_start(message: Message, session: AsyncSession) -> None:
    user = message.from_user
    if user is not None:
        await get_or_create_user(session, user.id, user.username)

    await message.answer(_HELP_TEXT, reply_markup=main_menu_keyboard())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(_HELP_TEXT, reply_markup=main_menu_keyboard())
