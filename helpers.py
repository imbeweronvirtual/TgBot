import logging

from config.config import ALPHA_API

from aiogram import Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest

import aiohttp

# Function to check stock price using Alpha Vantage API
async def check_stock_price(symbol: str, session: aiohttp.ClientSession):
    # Convert symbol to uppercase to match API requirements
    ticker = symbol.upper()
    # Standard URL for Alpha Vantage API to get daily time series data
    url = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={ticker}&apikey={ALPHA_API}'

    async with session.get(url) as response:
        if response.status != 200:
            return None
        data = await response.json()
    
    try:
        # Extract the closing price from the most recent trading day
        time_series = data["Time Series (Daily)"]
        close_price = time_series[max(time_series.keys())]["4. close"]
        return close_price

    except Exception:
        return None
    
async def edit_bot_message(text:str, event: Message | CallbackQuery, message_id: int | None = None, bot: Bot | None = None, markup: InlineKeyboardMarkup | None = None):
    if bot and message_id:
        try:
            if isinstance(event, Message):
                await bot.edit_message_text(
                    text=text,
                    chat_id=event.chat.id,
                    message_id=message_id,
                    reply_markup=markup,
                    parse_mode='HTML'
                )
                return
            else:
                await bot.edit_message_text(
                    text=text,
                    chat_id=event.message.chat.id,
                    message_id=message_id,
                    reply_markup=markup,
                    parse_mode='HTML'
                )
                return
        except TelegramBadRequest as e:
            logging.warning(f'Failed to edit {message_id}: {e}')
            await event.answer(text, reply_markup=markup, parse_mode='HTML')
            return
    elif isinstance(event, CallbackQuery):
        try:
            await event.message.edit_text(text=text, reply_markup=markup, parse_mode='HTML')
            return
        except TelegramBadRequest as e:
            logging.warning(f'Failed to edit {message_id}: {e}')
            await event.answer(text, reply_markup=markup, parse_mode='HTML')
            return
        
    await event.answer(text, reply_markup=markup, parse_mode='HTML')
    
    