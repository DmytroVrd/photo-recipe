from types import SimpleNamespace

import pytest

from recipe.llm.json_utils import parse_json_object
from recipe.schemas.recipe import RecipeBatch
from recipe.vision import analyzer


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


def test_openrouter_vision_falls_back_to_next_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    class FakeCompletions:
        def create(self, *, model: str, **_: object) -> SimpleNamespace:
            calls.append(model)
            if model == "primary-model":
                raise RuntimeError("primary unavailable")

            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content="""{
                                "detected_ingredients": ["egg"],
                                "recipes": [{
                                    "title": "Egg",
                                    "difficulty": "easy",
                                    "total_time_minutes": 5,
                                    "servings": 1,
                                    "ingredients": [{"name": "egg", "amount": "1"}],
                                    "steps": [{"order": 1, "text": "Cook it"}]
                                }]
                            }"""
                        )
                    )
                ]
            )

    class FakeOpenAI:
        def __init__(self, **_: object) -> None:
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(analyzer, "OpenAI", FakeOpenAI)
    monkeypatch.setattr(analyzer.settings, "OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(analyzer.settings, "OPENROUTER_VISION_MODEL", "primary-model")
    monkeypatch.setattr(
        analyzer.settings,
        "OPENROUTER_VISION_FALLBACK_MODELS",
        "fallback-model",
    )

    result = analyzer._analyze_via_openrouter(b"image", "image/jpeg", None)

    assert result.detected_ingredients == ["egg"]
    assert calls == ["primary-model", "fallback-model"]
