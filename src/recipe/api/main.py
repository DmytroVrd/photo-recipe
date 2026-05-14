import asyncio
from collections.abc import AsyncIterator

from fastapi import Depends, FastAPI, File, Form, UploadFile
from pydantic import BaseModel, HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession

from recipe.db.crud import save_recipe_result
from recipe.db.session import async_session
from recipe.schemas.preferences import UserPreferences
from recipe.schemas.recipe import RecipeBatch
from recipe.scraper.playwright_scraper import url_to_recipe_batch
from recipe.vision.analyzer import analyze_photo

app = FastAPI(
    title="AI Photo Recipe API",
    version="0.1.0",
    description="Backend API for fridge-photo recipe generation and recipe URL normalization.",
)


class ApiPreferences(BaseModel):
    nutrition_enabled: bool = True
    dietary_style: str = "balanced"
    avoid_ingredients: list[str] = []
    default_servings: int = 2

    def to_user_preferences(self) -> UserPreferences:
        return UserPreferences(
            nutrition_enabled=self.nutrition_enabled,
            dietary_style=self.dietary_style,
            avoid_ingredients=tuple(self.avoid_ingredients),
            default_servings=self.default_servings,
        )


class UrlNormalizeRequest(BaseModel):
    url: HttpUrl
    telegram_id: int | None = None
    preferences: ApiPreferences = ApiPreferences()


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with async_session() as session:
        yield session


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/analyze-photo", response_model=RecipeBatch)
async def api_analyze_photo(
    file: UploadFile = File(...),
    telegram_id: int | None = Form(default=None),
    nutrition_enabled: bool = Form(default=True),
    dietary_style: str = Form(default="balanced"),
    avoid_ingredients: str = Form(default=""),
    default_servings: int = Form(default=2),
    session: AsyncSession = Depends(get_db_session),
) -> RecipeBatch:
    image_bytes = await file.read()
    preferences = UserPreferences(
        nutrition_enabled=nutrition_enabled,
        dietary_style=dietary_style,
        avoid_ingredients=tuple(
            item.strip().lower() for item in avoid_ingredients.split(",") if item.strip()
        ),
        default_servings=default_servings,
    )
    batch = await asyncio.to_thread(
        analyze_photo,
        image_bytes,
        file.content_type or "image/jpeg",
        preferences,
    )
    if telegram_id is not None:
        await save_recipe_result(session, telegram_id, "api_photo", batch)
    return batch


@app.post("/api/normalize-url", response_model=RecipeBatch)
async def api_normalize_url(
    request: UrlNormalizeRequest,
    session: AsyncSession = Depends(get_db_session),
) -> RecipeBatch:
    batch = await url_to_recipe_batch(
        str(request.url),
        preferences=request.preferences.to_user_preferences(),
    )
    if request.telegram_id is not None:
        await save_recipe_result(
            session,
            request.telegram_id,
            "api_url",
            batch,
            source_url=str(request.url),
        )
    return batch
