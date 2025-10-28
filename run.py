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





# Define main function to start the bot
async def main():
    
    async with aiohttp.ClientSession() as http_session, \
                aiosqlite.connect('database/bot_db.db') as db_session:
        bot = Bot(token=TOKEN)

        dp = Dispatcher(storage=storage, db=db_session, session=http_session, bot=bot)

        dp.include_router(admin_router)
        dp.include_router(form_router)

        await dp.start_polling(bot, polling_timeout=5)


# Run the main function, set up logging
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
