from recipe.schemas.preferences import UserPreferences, format_preferences_for_prompt


def test_preferences_cache_key_changes_when_avoid_list_changes() -> None:
    first = UserPreferences(avoid_ingredients=("ketchup",))
    second = UserPreferences(avoid_ingredients=("mustard",))

    assert first.cache_key() != second.cache_key()


def test_preferences_prompt_mentions_disabled_nutrition() -> None:
    prompt = format_preferences_for_prompt(UserPreferences(nutrition_enabled=False))

    assert "set nutrition to null" in prompt


def test_preferences_prompt_expands_high_protein_style() -> None:
    prompt = format_preferences_for_prompt(UserPreferences(dietary_style="high_protein"))

    assert "Prioritize protein-rich recipes" in prompt
    assert "protein_g meaningfully higher" in prompt


def test_preferences_prompt_enforces_servings_and_avoid_list() -> None:
    prompt = format_preferences_for_prompt(
        UserPreferences(default_servings=4, avoid_ingredients=("ketchup",))
    )

    assert "Preferred servings: 4" in prompt
    assert "Set every recipe's servings field" in prompt
    assert "Never use avoid ingredients" in prompt
