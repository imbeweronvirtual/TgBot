import asyncio
import logging

from config.config import ALPHA_API

from aiogram import Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramAPIError,
    TelegramRetryAfter,
    TelegramForbiddenError,
)

import aiohttp
import aiosqlite

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

    except Exception as e:
        logging.warning(e)
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
    

async def calc_profit(user_id: int, stock: str, db: aiosqlite.Connection) -> float:
    async with db.execute('SELECT quantity, price FROM history WHERE user_id = ? AND stock = ?', (user_id, stock,)) as query:
        transactions = await query.fetchall()
         
    transactions_stack = []
    profit = 0.0
    
    for quantity, price in transactions:
        if quantity > 0:
            transactions_stack.append([quantity, price])
        if quantity < 0:
            quantity = -quantity
            
            while quantity > 0 and transactions_stack:
                diff = min(quantity, transactions_stack[0][0])
                
                transactions_stack[0][0] -= diff
                quantity -= diff
                
                if transactions_stack[0][0] == 0:
                    transactions_stack.pop(0)
    
    for quantity, price in transactions_stack:
        profit += quantity * price
    
    return profit

async def fetch_stock_data(user_id: int, stock: str, quantity: int, session: aiohttp.ClientSession, db: aiosqlite.Connection):
    try:
        price_str = await check_stock_price(stock, session)
        price = float(price_str) if price_str else 0.0
        
        if price == 0:
            logging.warning(f"Got zero price for {stock}, skipping calculation.")
            return f"  • <b>{stock}:</b> {quantity}pcs. (Error: <code>Price is $0.00</code>)"
        
        earned = await calc_profit(user_id=user_id, stock=stock, db=db)
        
        total = price * quantity
        pure_profit = total - earned
        
        # Return the final string for this one stock
        return f"  • <b>{stock}:</b> {quantity}pcs. (Total: <b>${total:,.2f}</b> / Profit: <b>${pure_profit:,.2f}</b>)"
    except Exception as e:
        logging.error(f"Failed to fetch data for {stock}: {e}")
        return f"  • <b>{stock}:</b> {quantity}pcs. (Unable to calculate profit)"
    
async def get_full_user_report(db: aiosqlite.Connection, user_id: int | None = None, username: str | None = None) -> dict | None:
    if not (user_id or username):
        return None

    if user_id:
        async with db.execute('SELECT id, cash, created FROM users WHERE id = ?', (user_id,)) as query:
            main_info = await query.fetchone()
    else:
        async with db.execute('SELECT id, cash, created FROM users WHERE username = ?', (username,)) as query:
            main_info = await query.fetchone()
        
    if not main_info:
        return None
    
    async def get_portfolio():
        async with db.execute('SELECT stock, quantity FROM user_savings WHERE user_id = ?', (main_info[0],)) as query:
            return await query.fetchall()
        
    async def get_history():
        async with db.execute('SELECT id, stock, price, quantity, time FROM history WHERE user_id = ?', (main_info[0],)) as query:
            return await query.fetchall()
    
    savings, history = await asyncio.gather(get_portfolio(), get_history())
    
    
    report = {
        'user_info': {
            'id': main_info[0],
            'cash': f"{main_info[1]:,.2f}",
            'created': main_info[2]
        },
       'savings': savings,
       'history': history
    }
    
    return report
    
    
async def send_message(bot: Bot, user_id: int, text: str, disable_notification: bool = False) -> bool:
    """
    Safe messages sender for broadcasting (aiogram 3.x version)

    :param bot: The bot instance (must be passed in).
    :param user_id: The target user's ID.
    :param text: The message text to send.
    :param disable_notification: Send silently.
    :return: True if sent, False if failed.
    """
    try:
        await bot.send_message(user_id, text, disable_notification=disable_notification, parse_mode="HTML")
        
    except TelegramRetryAfter as e:
        # Flood limit exceeded. Sleep for the specified time and retry.
        logging.error(f"Target [ID:{user_id}]: Flood limit exceeded. Sleep {e.timeout} seconds.")
        await asyncio.sleep(e.timeout)
        return await send_message(bot, user_id, text, disable_notification)  # Recursive call

    except (TelegramForbiddenError, TelegramBadRequest) as e:
        # Catches BotBlocked, UserDeactivated, and ChatNotFound.
        # These users are unreachable, so we log and move on.
        logging.error(f"Target [ID:{user_id}]: Unreachable. {e.message}")
        
    except TelegramAPIError as e:
        # Catch any other unexpected Telegram error
        logging.exception(f"Target [ID:{user_id}]: Failed with unhandled TelegramAPIError: {e}")
        
    except Exception as e:
        # Catch non-Telegram errors (e.g., network issues)
        logging.exception(f"Target [ID:{user_id}]: Failed with a non-Telegram error: {e}")
        
    else:
        # Only log success if no exceptions were raised
        logging.info(f"Target [ID:{user_id}]: success")
        return True
        
    return False