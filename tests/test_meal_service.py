from datetime import date

import pytest

from diet.meal_service import MealService
from diet.models import (
    InputSource,
    MealType,
    ParsedFoodEntry,
    ParsedMealResponse,
)
from storage.repositories import MealRepository, UserProfileRepository
from tests.fakes.llm import FakeLLMClient, FakeTranscriptionClient


@pytest.fixture
def meal_service(
    fake_llm: FakeLLMClient,
    fake_transcriber: FakeTranscriptionClient,
    meal_repo: MealRepository,
    profile_repo: UserProfileRepository,
) -> MealService:
    return MealService(fake_llm, fake_transcriber, meal_repo, profile_repo)


@pytest.mark.asyncio
async def test_log_from_text_returns_meal(
    meal_service: MealService, fake_llm: FakeLLMClient
) -> None:
    parsed = ParsedMealResponse(
        entries=[
            ParsedFoodEntry(
                name="Oatmeal",
                quantity=1,
                unit="bowl",
                calories=300,
                protein_g=10,
                carbs_g=55,
                fat_g=5,
            )
        ],
        meal_type="breakfast",
    )
    fake_llm.script("parse_meal_text", content="", parsed=parsed)

    meal = await meal_service.log_from_text(user_id=1, text="oatmeal bowl")

    assert meal.source == InputSource.TEXT
    assert len(meal.entries) == 1
    assert meal.entries[0].food.name == "Oatmeal"
    assert meal.meal_type == MealType.BREAKFAST
    assert meal.total_nutrition.calories == 300


@pytest.mark.asyncio
async def test_log_from_text_infers_meal_type_from_llm(
    meal_service: MealService, fake_llm: FakeLLMClient
) -> None:
    parsed = ParsedMealResponse(
        entries=[
            ParsedFoodEntry(
                name="Pizza",
                quantity=2,
                unit="slices",
                calories=500,
                protein_g=20,
                carbs_g=60,
                fat_g=18,
            )
        ],
        meal_type="dinner",
    )
    fake_llm.script("parse_meal_text", content="", parsed=parsed)
    meal = await meal_service.log_from_text(1, "2 slices of pizza")
    assert meal.meal_type == MealType.DINNER


@pytest.mark.asyncio
async def test_log_from_audio_returns_none_without_transcriber(
    fake_llm: FakeLLMClient,
    meal_repo: MealRepository,
    profile_repo: UserProfileRepository,
) -> None:
    svc = MealService(fake_llm, None, meal_repo, profile_repo)
    result = await svc.log_from_audio(user_id=1, audio_bytes=b"fake")
    assert result is None


@pytest.mark.asyncio
async def test_log_from_audio_transcribes_and_logs(
    meal_service: MealService,
    fake_llm: FakeLLMClient,
    fake_transcriber: FakeTranscriptionClient,
) -> None:
    fake_transcriber._result = "a banana"
    parsed = ParsedMealResponse(
        entries=[
            ParsedFoodEntry(
                name="Banana",
                quantity=1,
                unit="medium",
                calories=105,
                protein_g=1,
                carbs_g=27,
                fat_g=0,
            )
        ],
    )
    fake_llm.script("parse_meal_text", content="", parsed=parsed)
    meal = await meal_service.log_from_audio(1, b"ogg_audio_bytes")

    assert meal is not None
    assert meal.source == InputSource.AUDIO
    assert meal.raw_input == "a banana"


@pytest.mark.asyncio
async def test_get_daily_summary_empty(meal_service: MealService) -> None:
    summary = await meal_service.get_daily_summary(user_id=99, for_date=date.today())
    assert summary.total_nutrition.calories == 0.0
    assert summary.meals == []
