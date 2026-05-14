import logging

from google import genai
from google.genai import types

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


def analyze_photo(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    preferences: UserPreferences | None = None,
) -> RecipeBatch:
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is required for photo analysis")

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    image = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    response = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=[
            image,
            "Analyze this fridge/ingredients photo and generate exactly 3 recipes.\n\n"
            f"{format_preferences_for_prompt(preferences)}",
        ],
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM,
            temperature=0.2,
            response_mime_type="application/json",
        ),
    )

    raw = str(response.text or "").strip()
    data = parse_json_object(raw)
    return RecipeBatch.model_validate(data)
