from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Stats", callback_data="stats"),
                InlineKeyboardButton(text="⚙️ Settings", callback_data="settings:show"),
            ],
            [InlineKeyboardButton(text="⭐ Favorites", callback_data="favorites:show")],
        ]
    )
