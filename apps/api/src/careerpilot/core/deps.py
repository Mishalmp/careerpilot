from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.core.config import Settings
from careerpilot.core.fetcher import Fetcher
from careerpilot.core.llm import LlmClient


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sessionmaker() as session:
        yield session


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_llm(request: Request) -> LlmClient | None:
    """None when no API key is configured; features then offer their non-AI path."""
    return request.app.state.llm


def get_fetcher(request: Request) -> Fetcher:
    return request.app.state.fetcher


DbSession = Annotated[AsyncSession, Depends(get_session)]
AppSettings = Annotated[Settings, Depends(get_app_settings)]
AppLlm = Annotated[LlmClient | None, Depends(get_llm)]
AppFetcher = Annotated[Fetcher, Depends(get_fetcher)]
