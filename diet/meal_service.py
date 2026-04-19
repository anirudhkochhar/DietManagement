import contextlib
from datetime import UTC, date, datetime

import structlog

from diet.audio import transcribe_voice
from diet.barcode import lookup_barcode
from diet.image import analyze_image
from diet.models import (
    DailySummary,
    FoodItem,
    InputSource,
    MealEntry,
    MealLog,
    MealType,
    NutritionInfo,
    ParsedMealResponse,
    UserProfile,
)
from llm.interface import LLMClient, Message, TaskClass, TaskSpec, TranscriptionClient
from storage.repositories import MealRepository, UserProfileRepository

logger = structlog.get_logger()

_PARSE_TASK = TaskSpec(name="parse_meal_text", task_class=TaskClass.STANDARD)

_MEAL_SYSTEM = """You are a nutrition expert. Parse the user's meal description.
For each food item, provide estimated calories, protein, carbs, fat, and fiber in grams.
Use standard food database values. Be specific about portions.
meal_type should be one of: breakfast, lunch, dinner, snack — infer from context or time."""


async def _parse_text_to_entries(
    llm: LLMClient, text: str, profile: UserProfile | None, user_id: int | None = None
) -> tuple[list[MealEntry], MealType | None]:
    context = ""
    if profile and profile.dietary_restrictions:
        context = f"\nUser restrictions: {', '.join(profile.dietary_restrictions)}"

    messages = [
        Message(role="system", content=_MEAL_SYSTEM + context),
        Message(role="user", content=f"Log this meal: {text[:1000]}"),
    ]
    result = await llm.complete(
        _PARSE_TASK, messages, response_model=ParsedMealResponse, user_id=user_id
    )
    if result.parsed is None:
        return [], None

    parsed: ParsedMealResponse = result.parsed
    entries = [
        MealEntry(
            food=FoodItem(
                name=e.name,
                quantity=e.quantity,
                unit=e.unit,
                nutrition=NutritionInfo(
                    calories=e.calories,
                    protein_g=e.protein_g,
                    carbs_g=e.carbs_g,
                    fat_g=e.fat_g,
                    fiber_g=e.fiber_g,
                ),
                confidence=e.confidence,
            )
        )
        for e in parsed.entries
    ]
    meal_type: MealType | None = None
    if parsed.meal_type:
        with contextlib.suppress(ValueError):
            meal_type = MealType(parsed.meal_type.lower())
    return entries, meal_type


def _infer_meal_type() -> MealType:
    hour = datetime.now(UTC).hour
    if 5 <= hour < 11:
        return MealType.BREAKFAST
    if 11 <= hour < 15:
        return MealType.LUNCH
    if 17 <= hour < 21:
        return MealType.DINNER
    return MealType.SNACK


class MealService:
    def __init__(
        self,
        llm: LLMClient,
        transcriber: TranscriptionClient | None,
        meal_repo: MealRepository,
        profile_repo: UserProfileRepository,
    ) -> None:
        self._llm = llm
        self._transcriber = transcriber
        self._meal_repo = meal_repo
        self._profile_repo = profile_repo

    async def _get_profile(self, user_id: int) -> UserProfile | None:
        return await self._profile_repo.get(user_id)

    async def log_from_text(
        self,
        user_id: int,
        text: str,
        meal_type: MealType | None = None,
    ) -> MealLog:
        profile = await self._get_profile(user_id)
        entries, inferred_type = await _parse_text_to_entries(self._llm, text, profile, user_id)

        log = MealLog(
            user_id=user_id,
            meal_type=meal_type or inferred_type or _infer_meal_type(),
            source=InputSource.TEXT,
            entries=entries,
            raw_input=text,
            logged_at=datetime.now(UTC),
        )
        saved = await self._meal_repo.save(log)
        logger.info("meal.logged", user_id=user_id, source="text", entries=len(entries))
        return saved

    async def log_from_image(
        self,
        user_id: int,
        image_bytes: bytes,
        media_type: str,
        meal_type: MealType | None = None,
    ) -> MealLog:
        entries, source, inferred_type = await analyze_image(
            self._llm, image_bytes, media_type, user_id
        )
        log = MealLog(
            user_id=user_id,
            meal_type=meal_type or inferred_type or _infer_meal_type(),
            source=source,
            entries=entries,
            raw_input=f"image:{media_type}",
            logged_at=datetime.now(UTC),
        )
        saved = await self._meal_repo.save(log)
        logger.info("meal.logged", user_id=user_id, source=source, entries=len(entries))
        return saved

    async def log_from_audio(
        self,
        user_id: int,
        audio_bytes: bytes,
    ) -> MealLog | None:
        if self._transcriber is None:
            logger.warning("meal.no_transcriber", user_id=user_id)
            return None
        text = await transcribe_voice(self._transcriber, audio_bytes, user_id)
        if not text:
            return None
        profile = await self._get_profile(user_id)
        entries, inferred_type = await _parse_text_to_entries(self._llm, text, profile, user_id)
        log = MealLog(
            user_id=user_id,
            meal_type=inferred_type or _infer_meal_type(),
            source=InputSource.AUDIO,
            entries=entries,
            raw_input=text,
            logged_at=datetime.now(UTC),
        )
        saved = await self._meal_repo.save(log)
        logger.info("meal.logged", user_id=user_id, source="audio", entries=len(entries))
        return saved

    async def log_from_barcode(
        self,
        user_id: int,
        barcode: str,
        quantity: float = 1.0,
        meal_type: MealType | None = None,
    ) -> MealLog | None:
        food = await lookup_barcode(barcode)
        if food is None:
            return None
        # scale quantity
        scaled_food = FoodItem(
            name=food.name,
            quantity=quantity,
            unit=food.unit,
            nutrition=NutritionInfo(
                calories=food.nutrition.calories * quantity,
                protein_g=food.nutrition.protein_g * quantity,
                carbs_g=food.nutrition.carbs_g * quantity,
                fat_g=food.nutrition.fat_g * quantity,
                fiber_g=food.nutrition.fiber_g * quantity,
            ),
            barcode=barcode,
            confidence=food.confidence,
        )
        log = MealLog(
            user_id=user_id,
            meal_type=meal_type or _infer_meal_type(),
            source=InputSource.BARCODE,
            entries=[MealEntry(food=scaled_food)],
            raw_input=f"barcode:{barcode}",
            logged_at=datetime.now(UTC),
        )
        saved = await self._meal_repo.save(log)
        logger.info("meal.logged", user_id=user_id, source="barcode", barcode=barcode)
        return saved

    async def get_daily_summary(self, user_id: int, for_date: date) -> DailySummary:
        profile = await self._get_profile(user_id)
        targets = profile.targets if profile else None
        return await self._meal_repo.get_summary_for_date(user_id, for_date, targets)

    async def get_recent_meals(self, user_id: int, limit: int = 5) -> list[MealLog]:
        return await self._meal_repo.get_recent_meals(user_id, limit)
