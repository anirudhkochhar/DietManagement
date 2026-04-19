from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from storage.database import Base
from storage.repositories import MealRepository, UserProfileRepository
from tests.fakes.llm import FakeLLMClient, FakeTranscriptionClient


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
def meal_repo(db_session: AsyncSession) -> MealRepository:
    return MealRepository(db_session)


@pytest.fixture
def profile_repo(db_session: AsyncSession) -> UserProfileRepository:
    return UserProfileRepository(db_session)


@pytest.fixture
def fake_llm() -> FakeLLMClient:
    return FakeLLMClient()


@pytest.fixture
def fake_transcriber() -> FakeTranscriptionClient:
    return FakeTranscriptionClient()
