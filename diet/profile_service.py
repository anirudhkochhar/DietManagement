import structlog

from diet.models import NutritionTargets, ProfileUpdate, UserGoal, UserProfile
from storage.repositories import UserProfileRepository

logger = structlog.get_logger()

# BMR multiplier assumptions for TDEE
_ACTIVITY_FACTOR = 1.4  # lightly active default


def _estimate_targets(profile: UserProfile) -> NutritionTargets | None:
    if profile.weight_kg is None or profile.height_cm is None or profile.age is None:
        return None

    # Mifflin-St Jeor BMR (average gender)
    bmr = 10 * profile.weight_kg + 6.25 * profile.height_cm - 5 * profile.age
    tdee = bmr * _ACTIVITY_FACTOR

    adjustment = {
        UserGoal.WEIGHT_LOSS: -500.0,
        UserGoal.WEIGHT_GAIN: +300.0,
        UserGoal.MUSCLE_BUILDING: +200.0,
        UserGoal.MAINTENANCE: 0.0,
    }
    calories = tdee + adjustment[profile.goal]
    protein_g = profile.weight_kg * 1.6  # 1.6g/kg body weight
    fat_g = calories * 0.28 / 9
    carbs_g = (calories - protein_g * 4 - fat_g * 9) / 4

    return NutritionTargets(
        calories=round(calories),
        protein_g=round(protein_g),
        carbs_g=round(carbs_g),
        fat_g=round(fat_g),
    )


class ProfileService:
    def __init__(self, repo: UserProfileRepository) -> None:
        self._repo = repo

    async def get_or_create(self, user_id: int, username: str | None = None) -> UserProfile:
        profile = await self._repo.get(user_id)
        if profile is None:
            profile = UserProfile(user_id=user_id, telegram_username=username)
            profile = await self._repo.upsert(profile)
        return profile

    async def update(self, user_id: int, update: ProfileUpdate) -> UserProfile:
        profile = await self._repo.get(user_id)
        if profile is None:
            profile = UserProfile(user_id=user_id)

        merged = profile.model_copy(update=dict(update.model_dump(exclude_none=True)))

        if merged.targets is None:
            estimated = _estimate_targets(merged)
            if estimated:
                merged = merged.model_copy(update={"targets": estimated})

        saved = await self._repo.upsert(merged)
        logger.info("profile.updated", user_id=user_id)
        return saved
