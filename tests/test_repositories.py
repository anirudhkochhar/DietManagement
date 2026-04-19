from datetime import UTC, date, datetime

import pytest

from diet.models import (
    FoodItem,
    InputSource,
    MealEntry,
    MealLog,
    MealType,
    NutritionInfo,
    UserGoal,
    UserProfile,
)
from storage.repositories import MealRepository, UserProfileRepository


@pytest.mark.asyncio
async def test_profile_upsert_and_get(profile_repo: UserProfileRepository) -> None:
    profile = UserProfile(user_id=1, telegram_username="alice", goal=UserGoal.WEIGHT_LOSS)
    await profile_repo.upsert(profile)

    fetched = await profile_repo.get(1)
    assert fetched is not None
    assert fetched.telegram_username == "alice"
    assert fetched.goal == UserGoal.WEIGHT_LOSS


@pytest.mark.asyncio
async def test_profile_upsert_updates_existing(profile_repo: UserProfileRepository) -> None:
    p1 = UserProfile(user_id=2, goal=UserGoal.MAINTENANCE)
    await profile_repo.upsert(p1)
    p2 = UserProfile(user_id=2, goal=UserGoal.MUSCLE_BUILDING, weight_kg=75.0)
    await profile_repo.upsert(p2)

    fetched = await profile_repo.get(2)
    assert fetched is not None
    assert fetched.goal == UserGoal.MUSCLE_BUILDING
    assert fetched.weight_kg == 75.0


@pytest.mark.asyncio
async def test_profile_get_missing_returns_none(profile_repo: UserProfileRepository) -> None:
    result = await profile_repo.get(9999)
    assert result is None


@pytest.mark.asyncio
async def test_save_and_retrieve_meal(
    meal_repo: MealRepository,
    profile_repo: UserProfileRepository,
) -> None:
    profile = UserProfile(user_id=10)
    await profile_repo.upsert(profile)

    meal = MealLog(
        user_id=10,
        meal_type=MealType.LUNCH,
        source=InputSource.TEXT,
        entries=[
            MealEntry(
                food=FoodItem(
                    name="Chicken breast",
                    quantity=200,
                    unit="g",
                    nutrition=NutritionInfo(calories=330, protein_g=62, carbs_g=0, fat_g=7),
                )
            )
        ],
        raw_input="200g chicken breast",
        logged_at=datetime.now(UTC),
    )
    saved = await meal_repo.save(meal)
    assert saved.id is not None

    meals = await meal_repo.get_meals_for_date(10, date.today())
    assert len(meals) == 1
    assert meals[0].entries[0].food.name == "Chicken breast"
    assert meals[0].total_nutrition.calories == 330


@pytest.mark.asyncio
async def test_daily_totals_sum_correctly(
    meal_repo: MealRepository,
    profile_repo: UserProfileRepository,
) -> None:
    profile = UserProfile(user_id=20)
    await profile_repo.upsert(profile)

    for cal in (300, 500, 200):
        await meal_repo.save(
            MealLog(
                user_id=20,
                meal_type=MealType.SNACK,
                source=InputSource.TEXT,
                entries=[
                    MealEntry(
                        food=FoodItem(
                            name="Food",
                            quantity=1,
                            unit="serving",
                            nutrition=NutritionInfo(calories=cal, protein_g=5, carbs_g=10, fat_g=2),
                        )
                    )
                ],
                raw_input="food",
                logged_at=datetime.now(UTC),
            )
        )

    summary = await meal_repo.get_summary_for_date(20, date.today(), targets=None)
    assert summary.total_nutrition.calories == 1000.0
