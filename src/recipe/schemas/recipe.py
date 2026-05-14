from pydantic import BaseModel, Field, field_validator


class Ingredient(BaseModel):
    name: str
    amount: str
    unit: str = ""


class Step(BaseModel):
    order: int = Field(ge=1)
    text: str
    duration_minutes: int = Field(default=0, ge=0)


class NutritionEstimate(BaseModel):
    calories: int = Field(ge=0)
    protein_g: float = Field(ge=0)
    carbs_g: float = Field(ge=0)
    fat_g: float = Field(ge=0)


class Recipe(BaseModel):
    title: str
    difficulty: str = Field(description="easy / medium / hard")
    total_time_minutes: int = Field(gt=0)
    servings: int = Field(gt=0)
    ingredients: list[Ingredient] = Field(min_length=1)
    steps: list[Step] = Field(min_length=1)
    missing_ingredients: list[str] = Field(
        default_factory=list,
        description="Ingredients from the recipe not found in the photo",
    )
    nutrition: NutritionEstimate | None = Field(
        default=None,
        description="Approximate nutrition estimate for one serving",
    )

    @field_validator("difficulty")
    @classmethod
    def validate_difficulty(cls, value: str) -> str:
        normalized = value.lower().strip()
        if normalized not in {"easy", "medium", "hard"}:
            raise ValueError("difficulty must be easy, medium, or hard")
        return normalized


class RecipeBatch(BaseModel):
    detected_ingredients: list[str] = Field(
        description="Ingredients identified from the photo or URL"
    )
    recipes: list[Recipe] = Field(min_length=1, max_length=3)
