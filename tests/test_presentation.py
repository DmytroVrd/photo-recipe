from recipe.bot.presentation import build_dish_image_url, format_intro, format_recipe_card
from recipe.schemas.recipe import RecipeBatch


def _batch() -> RecipeBatch:
    return RecipeBatch.model_validate(
        {
            "detected_ingredients": ["eggs", "milk", "cheese"],
            "recipes": [
                {
                    "title": "Cheesy Eggs",
                    "difficulty": "easy",
                    "total_time_minutes": 10,
                    "servings": 1,
                    "ingredients": [{"name": "eggs", "amount": "2"}],
                    "steps": [{"order": 1, "text": "Cook eggs"}],
                    "missing_ingredients": ["salt"],
                    "nutrition": {
                        "calories": 220,
                        "protein_g": 16,
                        "carbs_g": 2,
                        "fat_g": 15,
                    },
                }
            ],
        }
    )


def test_format_intro_mentions_count() -> None:
    assert "Found <b>3</b> ingredients" in format_intro(_batch())


def test_recipe_card_uses_html_and_emoji() -> None:
    card = format_recipe_card(_batch().recipes[0], 1)

    assert "🍳 <b>Recipe 1: Cheesy Eggs</b>" in card
    assert "🛒 <b>Could buy:</b>" in card
    assert "🔥 <b>Nutrition estimate / serving</b>" in card


def test_dish_image_url_is_pollinations_url() -> None:
    url = build_dish_image_url(_batch().recipes[0])

    assert url.startswith("https://image.pollinations.ai/prompt/")
    assert "nologo=true" in url
