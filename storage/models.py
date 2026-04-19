import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from storage.database import Base

_now_utc = lambda: datetime.datetime.now(datetime.UTC)  # noqa: E731


class UserProfileRecord(Base):
    __tablename__ = "user_profiles"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    height_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    goal: Mapped[str] = mapped_column(String(50), default="maintenance")
    dietary_restrictions: Mapped[str] = mapped_column(Text, default="[]")
    target_calories: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_protein_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_carbs_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_fat_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_now_utc)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=_now_utc, onupdate=_now_utc
    )
    meal_logs: Mapped[list["MealLogRecord"]] = relationship(
        "MealLogRecord", back_populates="user", cascade="all, delete-orphan"
    )


class MealLogRecord(Base):
    __tablename__ = "meal_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user_profiles.user_id"), index=True)
    meal_type: Mapped[str] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(String(20))
    raw_input: Mapped[str] = mapped_column(Text)
    logged_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), index=True)
    total_calories: Mapped[float] = mapped_column(Float, default=0.0)
    total_protein_g: Mapped[float] = mapped_column(Float, default=0.0)
    total_carbs_g: Mapped[float] = mapped_column(Float, default=0.0)
    total_fat_g: Mapped[float] = mapped_column(Float, default=0.0)
    total_fiber_g: Mapped[float] = mapped_column(Float, default=0.0)
    user: Mapped["UserProfileRecord"] = relationship(
        "UserProfileRecord", back_populates="meal_logs"
    )
    entries: Mapped[list["MealEntryRecord"]] = relationship(
        "MealEntryRecord", back_populates="meal_log", cascade="all, delete-orphan"
    )


class MealEntryRecord(Base):
    __tablename__ = "meal_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    meal_log_id: Mapped[int] = mapped_column(Integer, ForeignKey("meal_logs.id"))
    food_name: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(50))
    calories: Mapped[float] = mapped_column(Float)
    protein_g: Mapped[float] = mapped_column(Float)
    carbs_g: Mapped[float] = mapped_column(Float)
    fat_g: Mapped[float] = mapped_column(Float)
    fiber_g: Mapped[float] = mapped_column(Float, default=0.0)
    barcode: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    meal_log: Mapped["MealLogRecord"] = relationship("MealLogRecord", back_populates="entries")
