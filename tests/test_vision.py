import pytest

from recipe.llm.json_utils import parse_json_object
from recipe.schemas.recipe import RecipeBatch


def test_parse_json_object_strips_markdown_fence() -> None:
    data = parse_json_object(
        """```json
        {"detected_ingredients": ["egg"], "recipes": [{
          "title": "Egg",
          "difficulty": "easy",
          "total_time_minutes": 5,
          "servings": 1,
          "ingredients": [{"name": "egg", "amount": "1"}],
          "steps": [{"order": 1, "text": "Cook it"}]
        }]}
        ```"""
    )

    assert RecipeBatch.model_validate(data).detected_ingredients == ["egg"]


def test_recipe_batch_rejects_bad_difficulty() -> None:
    with pytest.raises(ValueError):
        RecipeBatch.model_validate(
            {
                "detected_ingredients": ["egg"],
                "recipes": [
                    {
                        "title": "Egg",
                        "difficulty": "impossible",
                        "total_time_minutes": 5,
                        "servings": 1,
                        "ingredients": [{"name": "egg", "amount": "1"}],
                        "steps": [{"order": 1, "text": "Cook it"}],
                    }
                ],
            }
        )
