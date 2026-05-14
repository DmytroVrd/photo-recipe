import json
from collections import Counter
from typing import Any

import pandas as pd
from sqlalchemy import select

from recipe.db.models import RecipeResult, User
from recipe.db.session import async_session


async def get_user_stats(telegram_id: int) -> dict[str, Any]:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            return {"status": "no_data"}

        rows = await session.execute(select(RecipeResult).where(RecipeResult.user_id == user.id))
        records = list(rows.scalars())

    if not records:
        return {"status": "no_data"}

    df = pd.DataFrame(
        [
            {
                "source": row.source,
                "from_cache": row.from_cache,
                "ingredients": json.loads(row.detected_ingredients),
                "created_at": row.created_at,
            }
            for row in records
        ]
    )

    all_ingredients: list[str] = []
    for ingredients in df["ingredients"]:
        all_ingredients.extend(ingredients)

    top_ingredients = [ingredient for ingredient, _ in Counter(all_ingredients).most_common(5)]

    return {
        "total_recipes": len(df),
        "photo_count": int((df["source"] == "photo").sum()),
        "url_count": int((df["source"] == "url").sum()),
        "cache_hits": int(df["from_cache"].sum()),
        "top_ingredients": top_ingredients,
    }
