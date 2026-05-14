import asyncio
import logging

from google import genai
from google.genai import types
from openai import AsyncOpenAI

from recipe.config import settings
from recipe.llm.json_utils import parse_json_object
from recipe.schemas.preferences import UserPreferences, format_preferences_for_prompt
from recipe.schemas.recipe import Recipe, RecipeBatch

logger = logging.getLogger(__name__)

_client = AsyncOpenAI(
    base_url=settings.OPENROUTER_BASE_URL,
    api_key=settings.OPENROUTER_API_KEY or "missing-openrouter-key",
)

_NORMALIZE_SYSTEM = """You receive raw scraped text from a recipe website.
Extract the recipe and return ONLY valid JSON matching this schema:
{
  "detected_ingredients": ["all ingredients from the recipe"],
  "recipes": [
    {
      "title": "string",
      "difficulty": "easy|medium|hard",
      "total_time_minutes": 30,
      "servings": 2,
      "ingredients": [{"name": "string", "amount": "string", "unit": "string"}],
      "steps": [{"order": 1, "text": "string", "duration_minutes": 0}],
      "missing_ingredients": [],
      "nutrition": {
        "calories": 500,
        "protein_g": 25,
        "carbs_g": 40,
        "fat_g": 20
      } or null
    }
  ]
}
Return exactly 1 recipe from the page. If nutrition is disabled, set nutrition to null.
No markdown, no explanation."""

_SIMILAR_SYSTEM = """You are a culinary AI.
The user liked one recipe from a fridge-photo result.
Create exactly 1 new recipe that is similar in style, difficulty, and main ingredients,
but not a duplicate.

Return ONLY valid JSON matching this schema:
{
  "detected_ingredients": ["ingredients available from the original fridge scan"],
  "recipes": [
    {
      "title": "string",
      "difficulty": "easy|medium|hard",
      "total_time_minutes": 30,
      "servings": 2,
      "ingredients": [{"name": "string", "amount": "string", "unit": "string"}],
      "steps": [{"order": 1, "text": "string", "duration_minutes": 0}],
      "missing_ingredients": [],
      "nutrition": {
        "calories": 500,
        "protein_g": 25,
        "carbs_g": 40,
        "fat_g": 20
      } or null
    }
  ]
}

Rules:
- Use primarily the detected ingredients.
- Do not require buying a missing main ingredient.
- Keep missing_ingredients short and optional.
- If nutrition is disabled, set nutrition to null.
- No markdown, no explanation."""


async def normalize_scraped_recipe(
    raw_text: str,
    source_url: str,
    preferences: UserPreferences | None = None,
) -> RecipeBatch:
    response = await _client.chat.completions.create(
        model=settings.OPENROUTER_MODEL,
        max_tokens=1500,
        temperature=0.1,
        messages=[
            {"role": "system", "content": _NORMALIZE_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Source: {source_url}\n\n"
                    f"{format_preferences_for_prompt(preferences)}\n\n"
                    f"{raw_text}"
                ),
            },
        ],
    )
    raw = str(response.choices[0].message.content or "").strip()
    data = parse_json_object(raw)
    return RecipeBatch.model_validate(data)


async def generate_similar_recipe(
    original_batch: RecipeBatch,
    source_recipe: Recipe,
    preferences: UserPreferences | None = None,
) -> RecipeBatch:
    if settings.GEMINI_API_KEY:
        try:
            return await asyncio.to_thread(
                _generate_similar_recipe_with_gemini,
                original_batch,
                source_recipe,
                preferences,
            )
        except Exception:
            logger.warning(
                "Gemini similar recipe generation failed; trying OpenRouter",
                exc_info=True,
            )

    response = await _client.chat.completions.create(
        model=settings.OPENROUTER_MODEL,
        max_tokens=1500,
        temperature=0.4,
        messages=[
            {"role": "system", "content": _SIMILAR_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"{format_preferences_for_prompt(preferences)}\n\n"
                    "Detected fridge ingredients:\n"
                    f"{original_batch.detected_ingredients}\n\n"
                    "Original recipe the user liked:\n"
                    f"{source_recipe.model_dump_json()}\n\n"
                    "Generate one similar recipe variation."
                ),
            },
        ],
    )
    raw = str(response.choices[0].message.content or "").strip()
    data = parse_json_object(raw)
    return RecipeBatch.model_validate(data)


def _generate_similar_recipe_with_gemini(
    original_batch: RecipeBatch,
    source_recipe: Recipe,
    preferences: UserPreferences | None = None,
) -> RecipeBatch:
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    response = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=[
            (
                f"{format_preferences_for_prompt(preferences)}\n\n"
                "Detected fridge ingredients:\n"
                f"{original_batch.detected_ingredients}\n\n"
                "Original recipe the user liked:\n"
                f"{source_recipe.model_dump_json()}\n\n"
                "Generate one similar recipe variation."
            )
        ],
        config=types.GenerateContentConfig(
            system_instruction=_SIMILAR_SYSTEM,
            temperature=0.4,
            response_mime_type="application/json",
        ),
    )
    raw = str(response.text or "").strip()
    data = parse_json_object(raw)
    return RecipeBatch.model_validate(data)
