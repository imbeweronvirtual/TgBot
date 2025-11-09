import pytest
import pytest_asyncio
import aiosqlite
import asyncio

@pytest_asyncio.fixture
async def db():
    db = await aiosqlite.connect(':memory:')

    with open('database/schema.sql', 'r') as schema:
        await db.executescript(schema.read())

    await db.commit()
    yield db

    await db.close()
