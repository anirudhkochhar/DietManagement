import asyncio
from datetime import date, timedelta

import structlog

from diet.meal_service import MealService
from diet.models import DailySummary, NutritionTargets, UserProfile
from storage.repositories import UserProfileRepository

logger = structlog.get_logger()


class NutritionService:
    def __init__(self, meal_service: MealService, profile_repo: UserProfileRepository) -> None:
        self._meals = meal_service
        self._profile_repo = profile_repo

    async def weekly_summary(self, user_id: int) -> list[DailySummary]:
        today = date.today()
        days = [today - timedelta(days=i) for i in range(6, -1, -1)]
        return list(
            await asyncio.gather(*[self._meals.get_daily_summary(user_id, d) for d in days])
        )

    async def profile_with_targets(
        self, user_id: int
    ) -> tuple[UserProfile | None, NutritionTargets | None]:
        profile = await self._profile_repo.get(user_id)
        targets = profile.targets if profile else None
        return profile, targets
