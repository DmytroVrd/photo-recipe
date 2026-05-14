import pytest
from pydantic import ValidationError

from recipe.schemas.recipe import RecipeBatch


def test_recipe_batch_validates() -> None:
    batch = RecipeBatch.model_validate(
        {
            "detected_ingredients": ["eggs", "milk"],
            "recipes": [
                {
                    "title": "Omelet",
                    "difficulty": "Easy",
                    "total_time_minutes": 10,
                    "servings": 1,
                    "ingredients": [{"name": "eggs", "amount": "2", "unit": ""}],
                    "steps": [{"order": 1, "text": "Cook eggs", "duration_minutes": 5}],
                    "missing_ingredients": [],
                    "nutrition": {
                        "calories": 240,
                        "protein_g": 18,
                        "carbs_g": 2,
                        "fat_g": 18,
                    },
                }
            ],
        }
    )

    assert batch.recipes[0].difficulty == "easy"
    assert batch.recipes[0].nutrition is not None
    assert batch.recipes[0].nutrition.protein_g == 18


def test_recipe_batch_requires_at_most_three_recipes() -> None:
    recipe = {
        "title": "Toast",
        "difficulty": "easy",
        "total_time_minutes": 5,
        "servings": 1,
        "ingredients": [{"name": "bread", "amount": "1", "unit": "slice"}],
        "steps": [{"order": 1, "text": "Toast bread"}],
    }

    with pytest.raises(ValidationError):
        RecipeBatch.model_validate(
            {
                "detected_ingredients": ["bread"],
                "recipes": [recipe, recipe, recipe, recipe],
            }
        )
