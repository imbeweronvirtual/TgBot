import asyncio
import logging
import aiohttp

import aiosqlite

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config.config import TOKEN
from bot.handlers import form_router
from bot.admin import admin_router

# Initialize storage and router
storage = MemoryStorage()


#TODO: Tests, strings consts, UI


# Define the main function to start the bot
async def main():
    
    async with aiohttp.ClientSession() as http_session, \
                aiosqlite.connect('database/bot_db.db') as db_session:

        async with db_session.execute('SELECT COUNT(*) FROM sqlite_master WHERE type="table" AND name="users"') as query:
            if not await query.fetchone():
                await db_session.execute("""
                                         CREATE TABLE users (id INTEGER PRIMARY KEY NOT NULL,
                                                             cash NUMERIC NOT NULL DEFAULT 10000.00,
                                                             created DATE NOT NULL DEFAULT (date()),
                                                             username TEXT null on conflict ignore)
                                         """)
                await db_session.commit()

        async with db_session.execute('SELECT COUNT(*) FROM sqlite_master WHERE type="table" AND name="user_savings"') as query:
            if not await query.fetchone():
                await db_session.execute("""
                                         CREATE TABLE user_savings (user_id INTEGER NOT NULL,
                                                                    stock TEXT NOT NULL,
                                                                    quantity INTEGER NOT NULL,
                                                                    PRIMARY KEY (user_id, stock),
                                                                    FOREIGN KEY (user_id) REFERENCES users(id));
                                         CREATE TRIGGER delete_zero_quantity
                                         AFTER UPDATE ON user_savings
                                         FOR EACH ROW
                                         WHEN NEW.quantity = 0
                                         BEGIN
                                             DELETE FROM user_savings WHERE user_id = NEW.user_id AND stock = NEW.stock;
                                         END;
                                         """)
                await db_session.commit()

        async with db_session.execute('SELECT COUNT(*) FROM sqlite_master WHERE type="table" AND name="history"') as query:
            if not await query.fetchone():
                await db_session.execute("""
                                         CREATE TABLE history (id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                               user_id INTEGER NOT NULL,
                                                               stock TEXT NOT NULL,
                                                               price NUMERIC NOT NULL,
                                                               quantity INTEGER NOT NULL,
                                                               time NUMERIC DEFAULT (datetime('now')),
                                         FOREIGN KEY (user_id) REFERENCES users(id));
                                         """)
                await db_session.commit()

        bot = Bot(token=TOKEN)

        dp = Dispatcher(storage=storage, db=db_session, session=http_session, bot=bot)

        dp.include_router(admin_router)
        dp.include_router(form_router)

        await dp.start_polling(bot, polling_timeout=5)


# Run the main function, set up logging
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
