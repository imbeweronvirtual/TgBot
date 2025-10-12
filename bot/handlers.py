import asyncio
import logging

import aiosqlite
import aiohttp

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.types import Message, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from config.config import TOKEN, ALPHA_API
from helpers import check_stock_price

from config.callbacks import BALANCE_CB, MY_STOCKS_CB, BUY_CB, SELL_CB, PRICE_CB
from bot.keyboards import Keyboards

# Initialize states
class StockStates(StatesGroup):
    waiting_symbol = State()
    waiting_symbol_buy = State()
    waiting_amount_buy = State()
    waiting_symbol_sell = State()
    waiting_amount_sell = State()
    
# Initialize router and default keyboard
form_router = Router()
default_keyboard = Keyboards()



# Define first /start command handler
@form_router.message(CommandStart())
async def cmd_start(message: Message, db: aiosqlite.Connection):
    # Check if user exists in DB, if not add them with default balance of 10000$
    async with db.execute('SELECT * FROM users WHERE id = ?', (message.from_user.id,)) as query:
        if not await query.fetchone():
            await db.execute('INSERT INTO users (id) VALUES (?)', (message.from_user.id,))
            await db.commit()
    await message.answer(f'Hello, {message.from_user.full_name}\nThis is a stocks Telegram bot, that allows you to look if you\'re a good trader', 
                         reply_markup=Keyboards.default_keyboard())
    
    
# Define /cancel command handler and "cancel" text handler to cancel any ongoing state    
@form_router.message(Command("cancel"))
@form_router.message(F.text.casefold() == "cancel")
async def cancel_handler(message: Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state is None:
        return

    logging.info("Cancelling state %r", current_state)
    await state.clear()
    await message.answer(
        "Cancelled.",
        reply_markup=Keyboards.default_keyboard(),
    )
    
    
# Define price check handler
@form_router.callback_query(F.data==PRICE_CB)
async def price_callback(callback: CallbackQuery, state: FSMContext):
    await state.set_state(StockStates.waiting_symbol)
    await callback.message.answer('Send me symbol of stock, price of which you want to check')
    await callback.answer()


# Check stock price handler after user sends symbol
@form_router.message(StockStates.waiting_symbol, F.text.regexp(r"^[A-Za-z]{1,5}$"))
async def check_price(message: Message, state: FSMContext, session: aiohttp.ClientSession):
    price = await check_stock_price(message.text, session)
    # If price is None then response from API was invalid(any error)
    if price == None:
        await message.answer('Invalid symbol. Please try again.', reply_markup=Keyboards.default_keyboard())
        await state.clear()
        return
    await message.answer(f'Current price of {message.text.upper()} is {price}$', reply_markup=Keyboards.default_keyboard())
    await state.clear()
    

# Define balance check handler
@form_router.callback_query(F.data==BALANCE_CB)
async def balance_callback(callback: CallbackQuery, state: FSMContext, db: aiosqlite.Connection):
    current_state = await state.get_state()
    if current_state is not None:
        await state.clear()
        
    async with db.execute('SELECT cash FROM users WHERE id = ?', (callback.from_user.id,)) as query:
        balance = await query.fetchone()
        await callback.message.answer(f'Your balance is {"{:.2f}".format(balance[0])}$', reply_markup=Keyboards.default_keyboard())
    await callback.answer()
    

# Define buy stocks handlers
@form_router.callback_query(F.data==BUY_CB)
async def start_buy_callback(callback_or_message: CallbackQuery | Message, state: FSMContext):
    # Important!
    # This handler can be called either from Callback(inline button) or manually by other hadler
    # So we need to check the type of the first argument and respond accordingly. If was called manually
    # this function should not call .answer() method on CallbackQuery object, because it doesn't exist
    if isinstance(callback_or_message, Message):
        await callback_or_message.answer('Send me symbol of stock, which you want to buy')
        await state.set_state(StockStates.waiting_symbol_buy)
        return
    else:
        await callback_or_message.message.answer('Send me symbol of stock, which you want to buy')
        await state.set_state(StockStates.waiting_symbol_buy)
        await callback_or_message.answer()


# Buy stock symbol handler after user sends symbol. Check if symbol is valid and get its price.
# Then ask for amount to buy
@form_router.message(StockStates.waiting_symbol_buy, F.text.regexp(r"^[A-Za-z]{1,5}$"))
async def buy_symbol(message: Message, state: FSMContext, session: aiohttp.ClientSession):
    price = await check_stock_price(message.text, session)
    if price == None:
        await message.answer('Invalid symbol. Please try again.', reply_markup=Keyboards.default_keyboard())
        await state.clear()
        return
    await state.update_data(symbol=message.text.upper(), price=price)
    await state.set_state(StockStates.waiting_amount_buy)
    await message.answer(f'Current price of {message.text.upper()} is {price}$. How many stocks do you want to buy? (send me a number)')
    
    
# Buy stock amount handler after user sends amount. Check if user has enough balance and complete the purchase
@form_router.message(StockStates.waiting_amount_buy, F.text.regexp(r"^\d+$"))
async def buy_amount(message: Message, state: FSMContext, db: aiosqlite.Connection, session: aiohttp.ClientSession):
    amount = int(message.text)
    if amount <= 0:
        await message.answer('Amount must be a positive integer. Please try again.', reply_markup=Keyboards.default_keyboard())
        await state.clear()
        return
    
    data = await state.get_data()
    # Check if price has changed since user sent symbol. If it has, ask to confirm purchase again
    price = await check_stock_price(data['symbol'], session)
    if price is None:
        await message.answer('Error fetching stock price. Please try again later.', reply_markup=Keyboards.default_keyboard())
        await state.clear()
        return
    if price != data['price']:
        await message.answer(f'Price of {data["symbol"]} has changed from {data["price"]}$ to {price}$. Please confirm the purchase again.')
        await state.clear()
        # Restart the buy process so user can confirm the new price
        await start_buy_callback(message, state)
        return
    total_price = amount * float(price)

    # Check if user has enough balance
    await db.execute('PRAGMA foreign_keys = ON')
    try:
        await db.execute('BEGIN')
        async with db.execute('SELECT cash FROM users WHERE id = ?', (message.from_user.id,)) as query:
            balance = await query.fetchone()
            if int(balance[0]) < total_price:
                await message.answer(f'You don\'t have enough money to buy {amount} of {data["symbol"]}. Your balance is {balance[0]}$', reply_markup=Keyboards.default_keyboard())
                return
            # Complete the purchase: deduct money from balance and add stocks to user_savings table
            else:
                await db.execute('UPDATE users SET cash = cash - ? WHERE id = ?', (total_price, message.from_user.id))
                await db.execute('INSERT INTO user_savings (user_id, stock, quantity) VALUES (?, ?, ?) ON CONFLICT(user_id, stock) DO UPDATE SET quantity = quantity + excluded.quantity',
                                (message.from_user.id, data['symbol'], amount,))
                await db.execute('INSERT INTO history (user_id, stock, price, quantity) VALUES (?, ?, ?, ?)',
                                    (message.from_user.id, data['symbol'], price, amount,))
                await db.commit()
                await message.answer(f'You have successfully bought {amount} of {data["symbol"]} for {total_price}$.', reply_markup=Keyboards.default_keyboard())
    except Exception as e:
        await db.rollback()
        logging.error(f'Transaction failed: {e}')
        await message.answer('An error occured, try again later', reply_markup=Keyboards.default_keyboard())
    finally:
        await state.clear()
            
        
            
@form_router.callback_query(F.data==SELL_CB)
async def start_sell_callback(callback_or_message: CallbackQuery | Message, state: FSMContext):
    if isinstance(callback_or_message, Message):
        await callback_or_message.answer('Send me a symbol of the stock, which you want to sell')
        await state.set_state(StockStates.waiting_symbol_sell)
    else:
        await callback_or_message.message.answer("Send me a symbol of stock, which you want to sell")
        await state.set_state(StockStates.waiting_symbol_sell)
        await callback_or_message.answer()
    
    
    
@form_router.message(StockStates.waiting_symbol_sell, F.text.regexp(r"^[A-Za-z]{1,5}$"))
async def sell_symbol(message: Message, state: FSMContext, db: aiosqlite.Connection, session: aiohttp.ClientSession):
    async with db.execute('SELECT stock FROM user_savings WHERE user_id = ? AND stock = ?', (message.from_user.id, message.text.upper())) as query:
        stock = await query.fetchone()
        if not stock:
            await message.answer(f'You don\'t own any stocks of {message.text.upper()}. Please try again.', reply_markup=Keyboards.default_keyboard())
            await state.clear()
            return
    stock = stock[0]

    price = await check_stock_price(stock, session)
    if price == None:
        await message.answer('Failed to retrieve stock price. Please try again.', reply_markup=Keyboards.default_keyboard())
        await state.clear()
        return
    await state.update_data(symbol=stock, price=price)
    await state.set_state(StockStates.waiting_amount_sell)
    await message.answer(f'Current price of {stock} is {price}$. How many stocks do you want to sell? (send me a number)')



@form_router.message(StockStates.waiting_amount_sell, F.text.regexp(r"^\d+$"))
async def sell_amount(message: Message, state: FSMContext, db: aiosqlite.Connection, session: aiohttp.ClientSession):
    data = await state.get_data()
    
    amount = int(message.text)
    
    async with db.execute('SELECT quantity FROM user_savings WHERE user_id = ? AND stock = ?', (message.from_user.id, data['symbol'])) as query:
        available_amount = await query.fetchone()
    
    if amount <= 0:
        await message.answer('Amount must be a positive integer. Please try again.', reply_markup=Keyboards.default_keyboard())
        await state.clear()
        return
    
    if not available_amount or amount > available_amount[0]:
        await message.answer(f'You don\'t have enough shares of {data["symbol"]} to sell. You have {available_amount[0]} shares.', reply_markup=Keyboards.default_keyboard())
        await state.clear()
        return
    
    # Check if price has changed since user sent symbol. If it has, ask to confirm sell again
    price = await check_stock_price(data['symbol'], session)
    if price is None:
        await message.answer('Error fetching stock price. Please try again later.', reply_markup=Keyboards.default_keyboard())
        await state.clear()
        return
    if price < data['price']:
        await message.answer(f'Price of {data["symbol"]} has changed from {data["price"]}$ to {price}$. Please confirm the sell again.')
        await state.clear()
        # Restart the sell process so user can confirm the new price
        await start_sell_callback(message, state)
        return
    
    total_price = amount * float(price)
    
    await db.execute('PRAGMA foreign_keys = ON')
    
    try:
        await db.execute('BEGIN')
        await db.execute('UPDATE users SET cash = cash + ? WHERE id = ?', (total_price, message.from_user.id))
        await db.execute('UPDATE user_savings SET quantity = quantity - ? WHERE user_id = ? AND stock = ?', (amount, message.from_user.id, data['symbol']))
        await db.execute('INSERT INTO history (user_id, stock, price, quantity) VALUES (?, ?, ?, ?)',
                            (message.from_user.id, data['symbol'], price, -amount,))
        await db.commit()
    except Exception as e:
        await db.rollback()
        await message.answer('Error occurred while processing your request. Please try again later.', reply_markup=Keyboards.default_keyboard())
        logging.error(f'Error occurred while selling stock: {e}')
        return

    await message.answer(f'Successfully sold {amount} shares of {data["symbol"]} at {price}$.', reply_markup=Keyboards.default_keyboard())
    await state.clear()
    
    
@form_router.message(StateFilter(None))
async def delete_unwanted(message: Message):
    try:
        await message.delete()
    except Exception:
        logging.info('Cannot delete message')