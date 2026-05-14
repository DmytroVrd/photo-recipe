import logging

from playwright.async_api import async_playwright

from recipe.llm.generator import normalize_scraped_recipe
from recipe.schemas.preferences import UserPreferences
from recipe.schemas.recipe import RecipeBatch

logger = logging.getLogger(__name__)

_RECIPE_SELECTORS = [
    "article",
    '[class*="recipe"]',
    '[class*="Recipe"]',
    "main",
    "body",
]

_BLOCKED_RESOURCES = {"image", "stylesheet", "font", "media"}


async def scrape_recipe_url(url: str) -> str:
    """Return raw page text from a recipe URL using Playwright."""
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.route(
            "**/*",
            lambda route: route.abort()
            if route.request.resource_type in _BLOCKED_RESOURCES
            else route.continue_(),
        )

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=15_000)

            for selector in _RECIPE_SELECTORS:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        text = await element.inner_text()
                        if len(text.strip()) > 200:
                            return text.strip()[:8000]
                except Exception:
                    logger.debug("Selector failed while scraping: %s", selector, exc_info=True)

            text = await page.inner_text("body")
            return text.strip()[:8000]
        finally:
            await browser.close()


async def url_to_recipe_batch(
    url: str,
    preferences: UserPreferences | None = None,
) -> RecipeBatch:
    raw_text = await scrape_recipe_url(url)
    return await normalize_scraped_recipe(raw_text, source_url=url, preferences=preferences)
