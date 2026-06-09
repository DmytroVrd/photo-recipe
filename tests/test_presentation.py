from typing import Any

import pytest

from recipe.bot import presentation
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
    assert "👥 1 serving" in card
    assert "🛒 <b>Could buy:</b>" in card
    assert "🔥 <b>Nutrition estimate / serving</b>" in card


def test_dish_image_url_is_pollinations_url() -> None:
    url = build_dish_image_url(_batch().recipes[0])

    assert url.startswith("https://image.pollinations.ai/prompt/")
    assert "nologo=true" in url


def test_dish_image_api_uses_authenticated_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(presentation.settings, "POLLINATIONS_API_KEY", "test-key")

    url = presentation._dish_image_api_url(_batch().recipes[0])

    assert url.startswith("https://gen.pollinations.ai/image/")


@pytest.mark.asyncio
async def test_pollinations_queue_rejection_is_not_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests = 0

    class FakeResponse:
        status_code = 402
        text = '{"error":"Queue full for IP"}'

    class FakeClient:
        def __init__(self, **_: Any) -> None:
            pass

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *_: Any) -> None:
            return None

        async def get(self, _: str) -> FakeResponse:
            nonlocal requests
            requests += 1
            return FakeResponse()

    monkeypatch.setattr(presentation.settings, "POLLINATIONS_API_KEY", "")
    monkeypatch.setattr(presentation.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(presentation, "_last_pollinations_started_at", 0.0)

    result = await presentation._fetch_pollinations_dish_preview_bytes(
        _batch().recipes[0]
    )

    assert result is None
    assert requests == 1


@pytest.mark.asyncio
async def test_pixazo_downloads_generated_image(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        def __init__(
            self,
            *,
            payload: dict[str, str] | None = None,
            content: bytes = b"",
            content_type: str = "application/json",
        ) -> None:
            self._payload = payload or {}
            self.content = content
            self.headers = {"content-type": content_type}

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return self._payload

    class FakeClient:
        def __init__(self, **_: Any) -> None:
            pass

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *_: Any) -> None:
            return None

        async def post(self, *_: Any, **__: Any) -> FakeResponse:
            return FakeResponse(payload={"output": "https://cdn.example/dish.png"})

        async def get(self, _: str) -> FakeResponse:
            return FakeResponse(content=b"image-bytes", content_type="image/png")

    monkeypatch.setattr(presentation.settings, "PIXAZO_API_KEY", "test-key")
    monkeypatch.setattr(presentation.httpx, "AsyncClient", FakeClient)

    result = await presentation._fetch_pixazo_dish_preview_bytes(
        _batch().recipes[0]
    )

    assert result == b"image-bytes"
