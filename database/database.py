"""
Middleware for aiogram and sessions/engine init for sqlalchemy
"""
from typing import Awaitable, Any, Callable, Dict

from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from aiogram import BaseMiddleware

engine = create_async_engine('sqlite+aiosqlite:///test.db', echo=True)
session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class DbMiddleware(BaseMiddleware):
    def __init__(self, session_pool) -> None:
        self.session_pool = session_pool

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ):
        db_session = await self.session_pool()
        data['db_session'] = db_session
        return await handler(event, data)

