import json
from datetime import UTC, date, datetime, time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from diet.models import (
    DailySummary,
    FoodItem,
    InputSource,
    MealEntry,
    MealLog,
    MealType,
    NutritionInfo,
    NutritionTargets,
    UserGoal,
    UserProfile,
    sum_nutrition,
)
from storage.models import MealEntryRecord, MealLogRecord, UserProfileRecord


class UserProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: int) -> UserProfile | None:
        result = await self._session.get(UserProfileRecord, user_id)
        return _record_to_profile(result) if result else None

    async def upsert(self, profile: UserProfile) -> UserProfile:
        existing = await self._session.get(UserProfileRecord, profile.user_id)
        if existing is None:
            existing = UserProfileRecord(user_id=profile.user_id)
            self._session.add(existing)
        existing.telegram_username = profile.telegram_username
        existing.height_cm = profile.height_cm
        existing.weight_kg = profile.weight_kg
        existing.age = profile.age
        existing.goal = profile.goal.value
        existing.dietary_restrictions = json.dumps(profile.dietary_restrictions)
        if profile.targets:
            existing.target_calories = profile.targets.calories
            existing.target_protein_g = profile.targets.protein_g
            existing.target_carbs_g = profile.targets.carbs_g
            existing.target_fat_g = profile.targets.fat_g
        await self._session.flush()
        return _record_to_profile(existing)


class MealRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, meal: MealLog) -> MealLog:
        record = MealLogRecord(
            user_id=meal.user_id,
            meal_type=meal.meal_type.value,
            source=meal.source.value,
            raw_input=meal.raw_input[:2000],
            logged_at=meal.logged_at,
            total_calories=meal.total_nutrition.calories,
            total_protein_g=meal.total_nutrition.protein_g,
            total_carbs_g=meal.total_nutrition.carbs_g,
            total_fat_g=meal.total_nutrition.fat_g,
            total_fiber_g=meal.total_nutrition.fiber_g,
        )
        self._session.add(record)
        await self._session.flush()

        for entry in meal.entries:
            self._session.add(
                MealEntryRecord(
                    meal_log_id=record.id,
                    food_name=entry.food.name,
                    quantity=entry.food.quantity,
                    unit=entry.food.unit,
                    calories=entry.food.nutrition.calories,
                    protein_g=entry.food.nutrition.protein_g,
                    carbs_g=entry.food.nutrition.carbs_g,
                    fat_g=entry.food.nutrition.fat_g,
                    fiber_g=entry.food.nutrition.fiber_g,
                    barcode=entry.food.barcode,
                    confidence=entry.food.confidence,
                )
            )
        await self._session.flush()
        return meal.model_copy(update={"id": record.id})

    async def get_meals_for_date(self, user_id: int, for_date: date) -> list[MealLog]:
        start = datetime.combine(for_date, time.min, tzinfo=UTC)
        end = datetime.combine(for_date, time.max, tzinfo=UTC)
        stmt = (
            select(MealLogRecord)
            .options(selectinload(MealLogRecord.entries))
            .where(
                MealLogRecord.user_id == user_id,
                MealLogRecord.logged_at >= start,
                MealLogRecord.logged_at <= end,
            )
            .order_by(MealLogRecord.logged_at)
        )
        result = await self._session.execute(stmt)
        return [_record_to_meal(r) for r in result.scalars()]

    async def get_recent_meals(self, user_id: int, limit: int = 5) -> list[MealLog]:
        stmt = (
            select(MealLogRecord)
            .options(selectinload(MealLogRecord.entries))
            .where(MealLogRecord.user_id == user_id)
            .order_by(MealLogRecord.logged_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [_record_to_meal(r) for r in result.scalars()]

    async def get_summary_for_date(
        self, user_id: int, for_date: date, targets: NutritionTargets | None
    ) -> DailySummary:
        meals = await self.get_meals_for_date(user_id, for_date)
        total = sum_nutrition([m.total_nutrition for m in meals])
        return DailySummary(
            user_id=user_id,
            date=for_date,
            meals=meals,
            total_nutrition=total,
            targets=targets,
        )


def _record_to_profile(r: UserProfileRecord) -> UserProfile:
    targets: NutritionTargets | None = None
    if r.target_calories is not None:
        targets = NutritionTargets(
            calories=r.target_calories,
            protein_g=r.target_protein_g or 0.0,
            carbs_g=r.target_carbs_g or 0.0,
            fat_g=r.target_fat_g or 0.0,
        )
    return UserProfile(
        user_id=r.user_id,
        telegram_username=r.telegram_username,
        height_cm=r.height_cm,
        weight_kg=r.weight_kg,
        age=r.age,
        goal=UserGoal(r.goal),
        dietary_restrictions=json.loads(r.dietary_restrictions or "[]"),
        targets=targets,
    )


def _record_to_meal(r: MealLogRecord) -> MealLog:
    entries = [
        MealEntry(
            food=FoodItem(
                name=e.food_name,
                quantity=e.quantity,
                unit=e.unit,
                nutrition=NutritionInfo(
                    calories=e.calories,
                    protein_g=e.protein_g,
                    carbs_g=e.carbs_g,
                    fat_g=e.fat_g,
                    fiber_g=e.fiber_g,
                ),
                barcode=e.barcode,
                confidence=e.confidence,
            )
        )
        for e in r.entries
    ]
    return MealLog(
        id=r.id,
        user_id=r.user_id,
        meal_type=MealType(r.meal_type),
        source=InputSource(r.source),
        entries=entries,
        raw_input=r.raw_input,
        logged_at=r.logged_at,
    )
