from recipe.config import Settings


def test_settings_defaults_are_free_first() -> None:
    settings = Settings()

    assert settings.GEMINI_MODEL
    assert settings.OPENROUTER_BASE_URL == "https://openrouter.ai/api/v1"
