import asyncio
import base64
import hashlib
import logging
import re
import time
from html import escape
from urllib.parse import quote

import httpx
from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message
from redis.asyncio import Redis

from recipe.config import settings
from recipe.schemas.recipe import Recipe, RecipeBatch

logger = logging.getLogger(__name__)

_IMAGE_TIMEOUT_SECONDS = 35
_POLLINATIONS_MIN_INTERVAL_SECONDS = 20
_POLLINATIONS_MAX_ATTEMPTS = 2
_pollinations_lock = asyncio.Lock()
_last_pollinations_started_at = 0.0


def _difficulty_icon(difficulty: str) -> str:
    return {"easy": "🟢", "medium": "🟡", "hard": "🔴"}.get(difficulty, "⭐")


def _ingredient_line(name: str, amount: str, unit: str = "") -> str:
    quantity = " ".join(part for part in [amount, unit] if part).strip()
    if quantity:
        return f"• {escape(quantity)} {escape(name)}"
    return f"• {escape(name)}"


def format_intro(batch: RecipeBatch, from_cache: bool = False) -> str:
    cache_note = (
        "\n\n♻️ <i>Result from cache: same photo was processed before.</i>"
        if from_cache
        else ""
    )
    preview = ", ".join(batch.detected_ingredients[:12])
    extra = len(batch.detected_ingredients) - 12
    if extra > 0:
        preview = f"{preview}, +{extra} more"

    return (
        f"🧊 <b>Fridge scan complete</b>\n\n"
        f"Found <b>{len(batch.detected_ingredients)}</b> ingredients:\n"
        f"{escape(preview)}\n\n"
        f"🍳 I made <b>{len(batch.recipes)}</b> recipe ideas from what you have."
        f"{cache_note}"
    )


def format_recipe_card(recipe: Recipe, index: int) -> str:
    difficulty = f"{_difficulty_icon(recipe.difficulty)} {escape(recipe.difficulty.title())}"
    servings_label = "serving" if recipe.servings == 1 else "servings"
    meta = (
        f"⏱ {recipe.total_time_minutes} min  |  "
        f"👥 {recipe.servings} {servings_label}  |  {difficulty}"
    )

    ingredients = "\n".join(
        _ingredient_line(ingredient.name, ingredient.amount, ingredient.unit)
        for ingredient in recipe.ingredients
    )
    steps = "\n".join(
        f"{step.order}. {escape(step.text)}"
        + (f" <i>({step.duration_minutes} min)</i>" if step.duration_minutes else "")
        for step in recipe.steps
    )
    missing = (
        "\n\n🛒 <b>Could buy:</b>\n"
        + "\n".join(f"• {escape(item)}" for item in recipe.missing_ingredients)
        if recipe.missing_ingredients
        else "\n\n🛒 <b>Could buy:</b> nothing important"
    )
    nutrition = ""
    if recipe.nutrition is not None:
        nutrition = (
            "\n\n🔥 <b>Nutrition estimate / serving</b>\n"
            f"• Calories: ~{recipe.nutrition.calories} kcal\n"
            f"• Protein: ~{recipe.nutrition.protein_g:g} g\n"
            f"• Carbs: ~{recipe.nutrition.carbs_g:g} g\n"
            f"• Fat: ~{recipe.nutrition.fat_g:g} g"
        )

    return (
        f"🍳 <b>Recipe {index}: {escape(recipe.title)}</b>\n"
        f"{meta}\n\n"
        f"🥕 <b>Ingredients</b>\n"
        f"{ingredients}"
        f"{missing}\n\n"
        f"{nutrition}\n\n"
        f"👨‍🍳 <b>Steps</b>\n"
        f"{steps}"
    )


def recipe_actions_keyboard(
    recipe: Recipe,
    index: int,
    result_id: int | None = None,
) -> InlineKeyboardMarkup:
    save_callback = f"save:{result_id}:{index}" if result_id is not None else "save:missing"
    more_callback = f"more:{result_id}:{index}" if result_id is not None else "more:missing"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🖼 Open dish image",
                    url=build_dish_image_url(recipe),
                ),
                InlineKeyboardButton(text="⭐ Save", callback_data=save_callback),
            ],
            [
                InlineKeyboardButton(text="🔁 More like this", callback_data=more_callback),
            ],
        ]
    )


def _dish_image_prompt(recipe: Recipe) -> str:
    ingredients = ", ".join(ingredient.name for ingredient in recipe.ingredients[:6])
    return (
        f"realistic appetizing food photography of {recipe.title}, "
        f"made with {ingredients}, home kitchen lighting, plated meal, no text"
    )


def build_dish_image_url(recipe: Recipe) -> str:
    prompt = _dish_image_prompt(recipe)
    return (
        "https://image.pollinations.ai/prompt/"
        f"{quote(prompt)}?width=512&height=384&nologo=true&safe=true&private=true"
    )


def _dish_image_api_url(recipe: Recipe) -> str:
    prompt = _dish_image_prompt(recipe)
    if settings.POLLINATIONS_API_KEY:
        return (
            "https://gen.pollinations.ai/image/"
            f"{quote(prompt)}?width=512&height=384&nologo=true&safe=true&private=true"
        )
    return build_dish_image_url(recipe)


def _image_filename(recipe: Recipe) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", recipe.title.lower()).strip("-")
    return f"{slug or 'dish-preview'}.jpg"


def _provider_dish_image_cache_key(recipe: Recipe, provider: str) -> str:
    raw_key = f"{provider}:{build_dish_image_url(recipe)}"
    digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    return f"recipe:dish-image:{digest}"


async def _get_cached_dish_preview(
    redis: Redis | None,
    recipe: Recipe,
    provider: str = "pollinations",
) -> BufferedInputFile | None:
    if redis is None:
        return None

    raw = await redis.get(_provider_dish_image_cache_key(recipe, provider))
    if not raw:
        return None

    try:
        image_bytes = base64.b64decode(raw)
    except Exception:
        logger.warning("Could not decode cached dish image for %s", recipe.title, exc_info=True)
        return None

    logger.info("Dish image cache hit for %s (%s bytes)", recipe.title, len(image_bytes))
    return BufferedInputFile(image_bytes, filename=_image_filename(recipe))


async def get_cached_dish_preview(
    redis: Redis | None,
    recipe: Recipe,
) -> BufferedInputFile | None:
    return await _get_cached_dish_preview(redis, recipe)


async def _set_cached_dish_preview(
    redis: Redis | None,
    recipe: Recipe,
    image_bytes: bytes,
    provider: str = "pollinations",
) -> None:
    if redis is None:
        return

    await redis.set(
        _provider_dish_image_cache_key(recipe, provider),
        base64.b64encode(image_bytes).decode("ascii"),
        ex=settings.IMAGE_CACHE_TTL_SECONDS,
    )


async def _fetch_pollinations_dish_preview_bytes(recipe: Recipe) -> bytes | None:
    global _last_pollinations_started_at

    url = _dish_image_api_url(recipe)
    headers = (
        {"Authorization": f"Bearer {settings.POLLINATIONS_API_KEY}"}
        if settings.POLLINATIONS_API_KEY
        else {}
    )
    started_at = time.perf_counter()
    async with _pollinations_lock:
        wait_seconds = _POLLINATIONS_MIN_INTERVAL_SECONDS - (
            time.perf_counter() - _last_pollinations_started_at
        )
        if wait_seconds > 0:
            logger.info(
                "Waiting %.2fs before Pollinations request for %s",
                wait_seconds,
                recipe.title,
            )
            await asyncio.sleep(wait_seconds)
        _last_pollinations_started_at = time.perf_counter()

        async with httpx.AsyncClient(
            timeout=_IMAGE_TIMEOUT_SECONDS,
            follow_redirects=True,
            headers=headers,
        ) as client:
            for attempt in range(_POLLINATIONS_MAX_ATTEMPTS):
                try:
                    response = await client.get(url)
                    if response.status_code in {401, 402}:
                        logger.warning(
                            "Pollinations rejected dish image for %s with HTTP %s: %s",
                            recipe.title,
                            response.status_code,
                            response.text[:300],
                        )
                        return None
                    if (
                        response.status_code == 429
                        and attempt < _POLLINATIONS_MAX_ATTEMPTS - 1
                    ):
                        retry_after = response.headers.get("retry-after")
                        delay = int(retry_after) if retry_after and retry_after.isdigit() else 10
                        delay = min(delay, 15)
                        logger.info(
                            "Pollinations rate limited %s, retrying in %ss",
                            recipe.title,
                            delay,
                        )
                        await asyncio.sleep(delay)
                        continue
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "")
                    if not content_type.startswith("image/"):
                        raise ValueError(f"Pollinations returned non-image content: {content_type}")

                    logger.info(
                        "Dish image fetched for %s in %.2fs (%s bytes)",
                        recipe.title,
                        time.perf_counter() - started_at,
                        len(response.content),
                    )
                    return response.content
                except Exception:
                    if attempt == _POLLINATIONS_MAX_ATTEMPTS - 1:
                        logger.warning(
                            "Pollinations dish image preview failed for %s after %.2fs",
                            recipe.title,
                            time.perf_counter() - started_at,
                            exc_info=True,
                        )
                        return None
                    await asyncio.sleep(5)
    return None


async def _fetch_dish_preview(
    recipe: Recipe,
    redis: Redis | None = None,
    provider: str = "pollinations",
) -> BufferedInputFile | None:
    cached = await _get_cached_dish_preview(redis, recipe, provider=provider)
    if cached is not None:
        return cached

    image_bytes = await _fetch_pollinations_dish_preview_bytes(recipe)
    if image_bytes is None:
        return None

    await _set_cached_dish_preview(redis, recipe, image_bytes, provider=provider)
    return BufferedInputFile(image_bytes, filename=_image_filename(recipe))


async def send_recipe_batch(
    message: Message,
    batch: RecipeBatch,
    result_id: int | None = None,
    from_cache: bool = False,
    include_images: bool = True,
    redis: Redis | None = None,
) -> None:
    await message.answer(format_intro(batch, from_cache=from_cache), parse_mode="HTML")

    for index, recipe in enumerate(batch.recipes, 1):
        image: BufferedInputFile | None = None
        if include_images:
            image = await _fetch_dish_preview(recipe, redis=redis)
            if image is not None:
                sent_at = time.perf_counter()
                await message.answer_photo(
                    photo=image,
                    caption=f"🖼 Preview: {recipe.title}",
                )

                logger.info(
                    "Dish image sent to Telegram for %s in %.2fs",
                    recipe.title,
                    time.perf_counter() - sent_at,
                )

        await message.answer(
            format_recipe_card(recipe, index),
            parse_mode="HTML",
            reply_markup=recipe_actions_keyboard(recipe, index, result_id=result_id),
        )
