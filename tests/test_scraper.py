from recipe.bot.handlers.url import URL_RE


def test_url_regex_detects_http_url() -> None:
    match = URL_RE.search("try https://example.com/recipe/123 please")

    assert match is not None
    assert match.group(0) == "https://example.com/recipe/123"
