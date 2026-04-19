from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from telegram.ext import ContextTypes

from diet.meal_service import MealService
from diet.nutrition import NutritionService
from diet.profile_service import ProfileService
from llm.interface import LLMClient, TranscriptionClient
from storage.repositories import MealRepository, UserProfileRepository


def _factory(context: ContextTypes.DEFAULT_TYPE) -> async_sessionmaker[AsyncSession]:
    f: async_sessionmaker[AsyncSession] = context.bot_data["session_factory"]
    return f


def _llm(context: ContextTypes.DEFAULT_TYPE) -> LLMClient:
    llm: LLMClient = context.bot_data["llm"]
    return llm


def _transcriber(context: ContextTypes.DEFAULT_TYPE) -> TranscriptionClient | None:
    t: TranscriptionClient | None = context.bot_data.get("transcriber")
    return t


@asynccontextmanager
async def meal_service(
    context: ContextTypes.DEFAULT_TYPE,
) -> AsyncGenerator[MealService, None]:
    async with _factory(context)() as session:
        meal_repo = MealRepository(session)
        profile_repo = UserProfileRepository(session)
        yield MealService(_llm(context), _transcriber(context), meal_repo, profile_repo)
        await session.commit()


@asynccontextmanager
async def profile_service(
    context: ContextTypes.DEFAULT_TYPE,
) -> AsyncGenerator[ProfileService, None]:
    async with _factory(context)() as session:
        profile_repo = UserProfileRepository(session)
        yield ProfileService(profile_repo)
        await session.commit()


@asynccontextmanager
async def nutrition_service(
    context: ContextTypes.DEFAULT_TYPE,
) -> AsyncGenerator[NutritionService, None]:
    async with _factory(context)() as session:
        meal_repo = MealRepository(session)
        profile_repo = UserProfileRepository(session)
        meal_svc = MealService(_llm(context), _transcriber(context), meal_repo, profile_repo)
        yield NutritionService(meal_svc, profile_repo)
        await session.commit()
