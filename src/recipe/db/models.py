from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    recipes: Mapped[list["RecipeResult"]] = relationship(back_populates="user")
    preferences: Mapped["UserSettings | None"] = relationship(back_populates="user")
    favorites: Mapped[list["FavoriteRecipe"]] = relationship(back_populates="user")


class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    nutrition_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    dietary_style: Mapped[str] = mapped_column(String(32), default="balanced")
    avoid_ingredients: Mapped[str] = mapped_column(Text, default="[]")
    default_servings: Mapped[int] = mapped_column(Integer, default=2)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    user: Mapped["User"] = relationship(back_populates="preferences")


class RecipeResult(Base):
    __tablename__ = "recipe_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    source: Mapped[str] = mapped_column(String(16))
    source_url: Mapped[str | None] = mapped_column(String(512))
    detected_ingredients: Mapped[str] = mapped_column(Text)
    recipe_titles: Mapped[str] = mapped_column(Text)
    recipe_payload: Mapped[str | None] = mapped_column(Text)
    from_cache: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    user: Mapped["User"] = relationship(back_populates="recipes")


class FavoriteRecipe(Base):
    __tablename__ = "favorite_recipes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    source_result_id: Mapped[int | None] = mapped_column(ForeignKey("recipe_results.id"))
    title: Mapped[str] = mapped_column(String(160))
    recipe_payload: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    user: Mapped["User"] = relationship(back_populates="favorites")
