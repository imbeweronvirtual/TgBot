import asyncio
import logging
import aiohttp

import aiosqlite

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from config.config import TOKEN
from bot.handlers import form_router

# Initialize storage and router
storage = MemoryStorage()





# Define main function to start the bot
async def main():
    bot = Bot(token=TOKEN)
    
    dp = Dispatcher(storage=storage)
    
    dp.include_router(form_router)
    
    await dp.start_polling(bot)


# Run the main function, set up logging
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
