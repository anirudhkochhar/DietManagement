from datetime import date, datetime
from enum import StrEnum
from functools import reduce
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class UserGoal(StrEnum):
    WEIGHT_LOSS = "weight_loss"
    WEIGHT_GAIN = "weight_gain"
    MAINTENANCE = "maintenance"
    MUSCLE_BUILDING = "muscle_building"


class MealType(StrEnum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"


class InputSource(StrEnum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    BARCODE = "barcode"


class NutritionInfo(BaseModel):
    model_config = ConfigDict(frozen=True)
    calories: float = 0.0
    protein_g: float = 0.0
    carbs_g: float = 0.0
    fat_g: float = 0.0
    fiber_g: float = 0.0

    def __add__(self, other: "NutritionInfo") -> "NutritionInfo":
        return NutritionInfo(
            calories=self.calories + other.calories,
            protein_g=self.protein_g + other.protein_g,
            carbs_g=self.carbs_g + other.carbs_g,
            fat_g=self.fat_g + other.fat_g,
            fiber_g=self.fiber_g + other.fiber_g,
        )


def sum_nutrition(items: list[NutritionInfo]) -> NutritionInfo:
    return reduce(lambda a, b: a + b, items, NutritionInfo())


class FoodItem(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    quantity: float
    unit: str
    nutrition: NutritionInfo
    barcode: str | None = None
    confidence: float = 1.0


class MealEntry(BaseModel):
    model_config = ConfigDict(frozen=True)
    food: FoodItem


class MealLog(BaseModel):
    id: int | None = None
    user_id: int
    meal_type: MealType
    source: InputSource
    entries: list[MealEntry]
    raw_input: str
    logged_at: datetime

    @property
    def total_nutrition(self) -> NutritionInfo:
        return sum_nutrition([e.food.nutrition for e in self.entries])


class NutritionTargets(BaseModel):
    model_config = ConfigDict(frozen=True)
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float


class UserProfile(BaseModel):
    user_id: int
    telegram_username: str | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    age: int | None = None
    goal: UserGoal = UserGoal.MAINTENANCE
    dietary_restrictions: list[str] = Field(default_factory=list)
    targets: NutritionTargets | None = None


class DailySummary(BaseModel):
    user_id: int
    date: date
    meals: list[MealLog]
    total_nutrition: NutritionInfo
    targets: NutritionTargets | None = None


# LLM structured output models
class ParsedFoodEntry(BaseModel):
    name: str
    quantity: float
    unit: str
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float = 0.0
    confidence: float = 0.8


class ParsedMealResponse(BaseModel):
    entries: list[ParsedFoodEntry]
    meal_type: str | None = None


class ImageAnalysisResponse(BaseModel):
    result_type: Literal["food", "barcode", "unknown"]
    barcode: str | None = None
    entries: list[ParsedFoodEntry] = Field(default_factory=list)


class ProfileUpdate(BaseModel):
    telegram_username: str | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    age: int | None = None
    goal: UserGoal | None = None
    dietary_restrictions: list[str] | None = None
    targets: NutritionTargets | None = None
