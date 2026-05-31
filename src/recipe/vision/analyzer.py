import base64
import logging

from google import genai
from google.genai import types
from google.genai.errors import ClientError
from openai import OpenAI

from recipe.config import settings
from recipe.llm.json_utils import parse_json_object
from recipe.schemas.preferences import UserPreferences, format_preferences_for_prompt
from recipe.schemas.recipe import RecipeBatch

logger = logging.getLogger(__name__)

_SYSTEM = """You are a culinary AI. The user sends a photo of their fridge or ingredients.

Your job:
1. Identify ALL visible food ingredients in the photo.
2. Generate exactly 3 recipes using primarily those ingredients.
3. For each recipe, list any missing ingredients the user would need to buy.
4. Include approximate nutrition per serving when requested. If nutrition is disabled,
   set "nutrition": null.

Return ONLY valid JSON matching this schema exactly:
{
  "detected_ingredients": ["ingredient1", "ingredient2", ...],
  "recipes": [
    {
      "title": "string",
      "difficulty": "easy|medium|hard",
      "total_time_minutes": 30,
      "servings": 2,
      "ingredients": [
        {"name": "string", "amount": "string", "unit": "string"}
      ],
      "steps": [
        {"order": 1, "text": "string", "duration_minutes": 5}
      ],
      "missing_ingredients": ["ingredient"],
      "nutrition": {
        "calories": 500,
        "protein_g": 25,
        "carbs_g": 40,
        "fat_g": 20
      } or null
    }
  ]
}"""


def _user_prompt(preferences: UserPreferences | None) -> str:
    return (
        "Analyze this fridge/ingredients photo and generate exactly 3 recipes.\n\n"
        f"{format_preferences_for_prompt(preferences)}"
    )


def _analyze_via_gemini(
    image_bytes: bytes,
    mime_type: str,
    preferences: UserPreferences | None,
) -> RecipeBatch:
    logger.info("Analyzing photo with Gemini model=%s", settings.GEMINI_MODEL)
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    image = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    response = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=[image, _user_prompt(preferences)],
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM,
            temperature=0.2,
            response_mime_type="application/json",
        ),
    )
    raw = str(response.text or "").strip()
    data = parse_json_object(raw)
    return RecipeBatch.model_validate(data)


def _analyze_via_openrouter(
    image_bytes: bytes,
    mime_type: str,
    preferences: UserPreferences | None,
) -> RecipeBatch:
    if not settings.OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is required for the fallback vision path")

    logger.info("Analyzing photo with OpenRouter vision model=%s", settings.OPENROUTER_VISION_MODEL)
    client = OpenAI(
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL,
    )
    image_b64 = base64.b64encode(image_bytes).decode()
    image_url = f"data:{mime_type};base64,{image_b64}"

    response = client.chat.completions.create(
        model=settings.OPENROUTER_VISION_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _user_prompt(preferences)},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            },
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    raw = (response.choices[0].message.content or "").strip()
    data = parse_json_object(raw)
    return RecipeBatch.model_validate(data)


def _is_geo_block(error: ClientError) -> bool:
    msg = str(error).lower()
    return "location is not supported" in msg or "failed_precondition" in msg


def analyze_photo(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    preferences: UserPreferences | None = None,
) -> RecipeBatch:
    if not settings.GEMINI_API_KEY and not settings.OPENROUTER_API_KEY:
        raise RuntimeError(
            "At least one of GEMINI_API_KEY or OPENROUTER_API_KEY is required for photo analysis"
        )

    if settings.GEMINI_API_KEY:
        try:
            return _analyze_via_gemini(image_bytes, mime_type, preferences)
        except ClientError as exc:
            if _is_geo_block(exc):
                logger.warning(
                    "Gemini direct is geo-blocked from this region; "
                    "falling back to OpenRouter vision"
                )
            else:
                logger.warning(
                    "Gemini direct failed (%s); falling back to OpenRouter vision", exc
                )
        except Exception:
            logger.warning("Gemini direct failed; falling back to OpenRouter vision", exc_info=True)

    return _analyze_via_openrouter(image_bytes, mime_type, preferences)
