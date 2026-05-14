import hashlib
import json
from dataclasses import dataclass, field


@dataclass(frozen=True)
class UserPreferences:
    nutrition_enabled: bool = True
    dietary_style: str = "balanced"
    avoid_ingredients: tuple[str, ...] = field(default_factory=tuple)
    default_servings: int = 2

    def cache_key(self) -> str:
        payload = {
            "nutrition_enabled": self.nutrition_enabled,
            "dietary_style": self.dietary_style,
            "avoid_ingredients": sorted(self.avoid_ingredients),
            "default_servings": self.default_servings,
        }
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def format_preferences_for_prompt(preferences: UserPreferences | None) -> str:
    if preferences is None:
        preferences = UserPreferences()

    avoid = ", ".join(preferences.avoid_ingredients) or "none"
    nutrition = (
        "include approximate nutrition per serving"
        if preferences.nutrition_enabled
        else "set nutrition to null"
    )
    style_instructions = {
        "balanced": (
            "Create balanced everyday recipes with reasonable protein, vegetables, and carbs."
        ),
        "high_protein": (
            "Prioritize protein-rich recipes. Prefer eggs, dairy, legumes, fish, meat, or other "
            "visible protein sources when available, and make protein_g meaningfully higher than "
            "in a balanced version."
        ),
        "low_calorie": (
            "Create lighter lower-calorie recipes. Prefer vegetables, lean proteins, and modest "
            "fat portions; avoid heavy sauces, extra sugar, and unnecessary oil."
        ),
        "vegetarian": (
            "Create vegetarian recipes only. Do not use meat, poultry, fish, or seafood in recipe "
            "ingredients or steps."
        ),
    }
    style_instruction = style_instructions.get(
        preferences.dietary_style,
        "Follow the requested dietary style as closely as possible.",
    )
    return (
        "User preferences:\n"
        f"- Dietary style: {preferences.dietary_style}\n"
        f"- Dietary instruction: {style_instruction}\n"
        f"- Avoid ingredients: {avoid}\n"
        f"- Preferred servings: {preferences.default_servings}\n"
        f"- Nutrition: {nutrition}\n"
        "Set every recipe's servings field to the preferred servings value unless the recipe "
        "physically cannot be portioned that way.\n"
        "Never use avoid ingredients inside recipe ingredients or steps. If an avoided "
        "ingredient is visible, it may appear in detected_ingredients, but do not build "
        "a recipe around it."
    )
