import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from recipe.db.models import FavoriteRecipe, RecipeResult, User, UserSettings
from recipe.schemas.preferences import UserPreferences
from recipe.schemas.recipe import Recipe, RecipeBatch


async def get_or_create_user(
    session: AsyncSession, telegram_id: int, username: str | None
) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user:
        if username is not None and user.username != username:
            user.username = username
            await session.commit()
        return user

    user = User(telegram_id=telegram_id, username=username)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def save_recipe_result(
    session: AsyncSession,
    telegram_id: int,
    source: str,
    batch: RecipeBatch,
    source_url: str | None = None,
    from_cache: bool = False,
) -> RecipeResult:
    user = await get_or_create_user(session, telegram_id, None)
    result = RecipeResult(
        user_id=user.id,
        source=source,
        source_url=source_url,
        detected_ingredients=json.dumps(batch.detected_ingredients, ensure_ascii=False),
        recipe_titles=json.dumps([recipe.title for recipe in batch.recipes], ensure_ascii=False),
        recipe_payload=batch.model_dump_json(),
        from_cache=from_cache,
    )
    session.add(result)
    await session.commit()
    await session.refresh(result)
    return result


async def get_or_create_user_settings(session: AsyncSession, telegram_id: int) -> UserSettings:
    user = await get_or_create_user(session, telegram_id, None)
    result = await session.execute(select(UserSettings).where(UserSettings.user_id == user.id))
    settings = result.scalar_one_or_none()
    if settings:
        return settings

    settings = UserSettings(user_id=user.id)
    session.add(settings)
    await session.commit()
    await session.refresh(settings)
    return settings


def settings_to_preferences(settings: UserSettings | None) -> UserPreferences:
    if settings is None:
        return UserPreferences()

    try:
        avoid = tuple(str(item).strip() for item in json.loads(settings.avoid_ingredients) if item)
    except json.JSONDecodeError:
        avoid = ()

    return UserPreferences(
        nutrition_enabled=settings.nutrition_enabled,
        dietary_style=settings.dietary_style,
        avoid_ingredients=avoid,
        default_servings=settings.default_servings,
    )


async def set_nutrition_enabled(
    session: AsyncSession,
    telegram_id: int,
    enabled: bool,
) -> UserSettings:
    settings = await get_or_create_user_settings(session, telegram_id)
    settings.nutrition_enabled = enabled
    await session.commit()
    await session.refresh(settings)
    return settings


async def set_dietary_style(
    session: AsyncSession,
    telegram_id: int,
    dietary_style: str,
) -> UserSettings:
    settings = await get_or_create_user_settings(session, telegram_id)
    settings.dietary_style = dietary_style
    await session.commit()
    await session.refresh(settings)
    return settings


async def set_default_servings(
    session: AsyncSession,
    telegram_id: int,
    servings: int,
) -> UserSettings:
    settings = await get_or_create_user_settings(session, telegram_id)
    settings.default_servings = max(1, min(servings, 8))
    await session.commit()
    await session.refresh(settings)
    return settings


async def set_avoid_ingredients(
    session: AsyncSession,
    telegram_id: int,
    ingredients: list[str],
) -> UserSettings:
    settings = await get_or_create_user_settings(session, telegram_id)
    cleaned = [ingredient.strip().lower() for ingredient in ingredients if ingredient.strip()]
    settings.avoid_ingredients = json.dumps(sorted(set(cleaned)), ensure_ascii=False)
    await session.commit()
    await session.refresh(settings)
    return settings


async def clear_avoid_ingredients(session: AsyncSession, telegram_id: int) -> UserSettings:
    return await set_avoid_ingredients(session, telegram_id, [])


async def save_favorite_from_result(
    session: AsyncSession,
    telegram_id: int,
    result_id: int,
    recipe_index: int,
) -> FavoriteRecipe:
    user = await get_or_create_user(session, telegram_id, None)
    result = await session.execute(
        select(RecipeResult).where(
            RecipeResult.id == result_id,
            RecipeResult.user_id == user.id,
        )
    )
    recipe_result = result.scalar_one_or_none()
    if recipe_result is None or not recipe_result.recipe_payload:
        raise ValueError("Recipe result not found")

    batch = RecipeBatch.model_validate_json(recipe_result.recipe_payload)
    try:
        recipe = batch.recipes[recipe_index - 1]
    except IndexError as exc:
        raise ValueError("Recipe index not found") from exc

    favorite = FavoriteRecipe(
        user_id=user.id,
        source_result_id=recipe_result.id,
        title=recipe.title,
        recipe_payload=recipe.model_dump_json(),
    )
    session.add(favorite)
    await session.commit()
    await session.refresh(favorite)
    return favorite


async def get_recipe_batch_from_result(
    session: AsyncSession,
    telegram_id: int,
    result_id: int,
) -> RecipeBatch:
    user = await get_or_create_user(session, telegram_id, None)
    result = await session.execute(
        select(RecipeResult).where(
            RecipeResult.id == result_id,
            RecipeResult.user_id == user.id,
        )
    )
    recipe_result = result.scalar_one_or_none()
    if recipe_result is None or not recipe_result.recipe_payload:
        raise ValueError("Recipe result not found")
    return RecipeBatch.model_validate_json(recipe_result.recipe_payload)


async def list_favorites(session: AsyncSession, telegram_id: int, limit: int = 10) -> list[Recipe]:
    favorites = await list_favorite_records(session, telegram_id, limit=limit)
    return [Recipe.model_validate_json(favorite.recipe_payload) for favorite in favorites]


async def list_favorite_records(
    session: AsyncSession,
    telegram_id: int,
    limit: int = 10,
) -> list[FavoriteRecipe]:
    user = await get_or_create_user(session, telegram_id, None)
    result = await session.execute(
        select(FavoriteRecipe)
        .where(FavoriteRecipe.user_id == user.id)
        .order_by(FavoriteRecipe.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def delete_favorite(
    session: AsyncSession,
    telegram_id: int,
    favorite_id: int,
) -> FavoriteRecipe | None:
    user = await get_or_create_user(session, telegram_id, None)
    result = await session.execute(
        select(FavoriteRecipe).where(
            FavoriteRecipe.id == favorite_id,
            FavoriteRecipe.user_id == user.id,
        )
    )
    favorite = result.scalar_one_or_none()
    if favorite is None:
        return None

    await session.delete(favorite)
    await session.commit()
    return favorite
