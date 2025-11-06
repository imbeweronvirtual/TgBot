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
async def check_stock_price(symbol: str, session: aiohttp.ClientSession) -> str | None:
    """
    Fetches the latest closing stock price for a given stock symbol using the Alpha Vantage API.

    This function retrieves daily time series stock data for the given symbol and extracts
    the most recent "4. close" price. It uses asynchronous requests to fetch data from the
    API and ensures proper handling of errors. If the API request fails or the required data
    is unavailable, the function returns None.

    Parameters:
        symbol: str
            The stock ticker symbol to fetch data for.
        session: aiohttp.ClientSession
            An open aiohttp ClientSession to perform the HTTP request.

    Returns:
        str or None
            The latest closing stock price as a string if available. Returns None in case of
            an error while fetching or processing the data.
    """
    # Convert symbol to uppercase to match API requirements
    ticker = symbol.upper()
    # Standard URL for Alpha Vantage API to get daily time series data
    url = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={ticker}&apikey={ALPHA_API}'

    async with session.get(url) as response:
        if response.status != 200:
            logging.warning(f'check_stock_price status code: {response.status}')
            return None
        data = await response.json()
    
    try:
        # Extract the closing price from the most recent trading day
        time_series = data["Time Series (Daily)"]
        close_price = time_series[max(time_series.keys())]["4. close"]
        return close_price

    except Exception as e:
        logging.warning(f'check_stock_price price get error: {e}')
        return None
    
async def edit_bot_message(text:str, event: Message | CallbackQuery, message_id: int | None = None, bot: Bot | None = None, reply_markup: InlineKeyboardMarkup | None = None) -> None:
    """
    Edits a bot message for a given event or falls back to answering the event if editing fails.

    This function allows editing the content of an existing bot message. It handles both cases
    when event is a `Message` or a `CallbackQuery`. If the bot and message ID are provided,
    it attempts to edit the message. If editing fails or if parameters for `bot` and `message_id`
    are not provided, it falls back to answering the event instead with the supplied text.

    Parameters:
        text: str
            The new text content for the bot message.
        event: Message | CallbackQuery
            The event triggering the operation. Could be either a message or a callback query.
        message_id: int | None, optional
            The ID of the message to edit. Default is None, meaning it will not attempt
            direct editing based on message ID.
        bot: Bot | None, optional
            The bot instance used for editing the message when `message_id` is provided.
            Default is None.
        reply_markup: InlineKeyboardMarkup | None, optional
            Optional inline keyboard markup to include with the edited message. Defaults to None.

    Raises:
        TelegramBadRequest
            If editing the message fails due to an invalid request.

    Returns:
        None
    """
    if bot and message_id:
        try:
            if isinstance(event, Message):
                await bot.edit_message_text(
                    text=text,
                    chat_id=event.chat.id,
                    message_id=message_id,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
                return
            else:
                await bot.edit_message_text(
                    text=text,
                    chat_id=event.message.chat.id,
                    message_id=message_id,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
                return
        except TelegramBadRequest as e:
            logging.warning(f'Failed to edit {message_id}: {e}')
            await event.answer(text, reply_markup=reply_markup, parse_mode='HTML')
            return
    elif isinstance(event, CallbackQuery):
        try:
            await event.message.edit_text(text=text, reply_markup=reply_markup, parse_mode='HTML')
            return
        except TelegramBadRequest as e:
            logging.warning(f'Failed to edit {message_id}: {e}')
            await event.answer(text, reply_markup=reply_markup, parse_mode='HTML')
            return
        
    await event.answer(text, reply_markup=reply_markup, parse_mode='HTML')
    

async def calc_profit(user_id: int, stock: str, db: aiosqlite.Connection) -> float:
    """
    Calculate the profit remaining for a specific user and stock based on transaction history.

    The function retrieves transaction history for the specified user and stock from the database
    and processes the transactions to compute the remaining profit. Positive quantities denote
    stocks bought, and negative quantities denote stocks sold. The function simulates a
    last-in-first-out (LIFO) method for handling transactions to calculate the remaining profit
    for unprocessed quantities.

    Parameters:
    user_id (int): The ID of the user whose profit is being calculated.
    stock (str): The stock symbol for which the profit is being calculated.
    db (aiosqlite.Connection): The database connection instance.

    Returns:
    float: The total remaining profit for the user and the specified stock.
    """
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

async def fetch_stock_data(user_id: int, stock: str, quantity: int, session: aiohttp.ClientSession, db: aiosqlite.Connection) -> str:
    """
    Fetches stock data, calculates the total value, and computes the profit or loss for a given stock.

    This asynchronous function retrieves the price of a stock using an external API, calculates its total value
    based on the quantity specified, and determines profit or loss by subtracting the earned amount fetched
    from the database. The function returns a formatted string containing the stock details.

    Parameters:
        user_id (int): Unique identifier of the user for whom stock data is being processed.
        stock (str): The stock symbol to be queried and processed.
        quantity (int): Quantity of the stock owned by the user.
        session (aiohttp.ClientSession): An aiohttp session instance for making API calls.
        db (aiosqlite.Connection): The SQLite database connection for querying user's profit data.

    Returns:
        str: A formatted string representing the stock details (quantity, total value, and profit/loss).

    Raises:
        Exception: Raised when an error occurs during stock price retrieval, profit calculation, or other operations.
    """
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
    """
    Retrieves a comprehensive user report containing user information, portfolio, and transaction history
    from the database based on either user ID or username.

    Parameters:
    db (aiosqlite.Connection): An asynchronous SQLite database connection object used for database access.
    user_id (int | None): The unique identifier of the user. Optional; either user_id or username is required.
    username (str | None): The username of the user. Optional; either username or user_id is required.

    Returns:
    dict | None: A dictionary containing the following structure:
        user_info: Dictionary with details about the user, including:
            - id: The user ID.
            - cash: The user's cash balance represented as a string formatted with commas and two decimal places.
            - created: Timestamp of when the user was created.
        savings: List of tuples where each tuple represents stock savings with stock name and quantity.
        history: List of tuples representing the transaction history with stock name, price, quantity, and timestamp.
        Returns None if no user is found or if both user_id and username are not provided.
    """
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
        async with db.execute('SELECT id, stock, price, quantity, time FROM history WHERE user_id = ? ORDER BY time ASC', (main_info[0],)) as query:
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


async def username_db_check(event: Message | CallbackQuery, db: aiosqlite.Connection) -> None:
    """
    Checks and updates the user's username in the database if it has changed.

    This function retrieves the username and user ID from the provided event (either
    `Message` or `CallbackQuery`). It checks the stored username in the database
    associated with the user and updates the database if the current username differs
    from the stored one.

    Parameters:
    event (Message | CallbackQuery): The incoming event object, which could either
        be a Message or a CallbackQuery, containing user details.
    db (aiosqlite.Connection): The asynchronous SQLite database connection used for
        executing queries.

    Raises:
    None

    Returns:
    None
    """
    if isinstance(event, Message):
        username = event.from_user.username
        user_id = event.from_user.id
    else:
        username = event.from_user.username
        user_id = event.from_user.id

    if username is None:
        return

    async with db.execute('SELECT username FROM users WHERE id = ?', (user_id,)) as query:
        username_db = await query.fetchone()

    if not username_db:
        return

    if username_db[0] != username:
       await db.execute('UPDATE users SET username = ? WHERE id = ?', (username, user_id,))
       await db.commit()