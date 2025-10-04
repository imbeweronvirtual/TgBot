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

from config import TOKEN, ALPHA_API
from helpers import check_stock_price

# Initialize storage and router
storage = MemoryStorage()
form_router = Router()

# Define callback data constants
HELP_CB='help_me'
PRICE_CB='check_price'
BALANCE_CB='check_balance'
MY_STOCKS_CB='check_owned_stocks'
BUY_CB='buy_stocks'
SELL_CB='sell_stocks'

# Initialize states
class StockStates(StatesGroup):
    waiting_symbol = State()
    waiting_symbol_buy = State()
    waiting_amount_buy = State()

# Initialize default keyboard
def default_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text='Balance', callback_data=BALANCE_CB),
                InlineKeyboardButton(text='My stocks', callback_data=MY_STOCKS_CB), 
            ],
            [
                InlineKeyboardButton(text='Buy stocks', callback_data=BUY_CB),
                InlineKeyboardButton(text='Sell stocks', callback_data=SELL_CB)
            ],
            [InlineKeyboardButton(text='Check stocks price', callback_data=PRICE_CB)],
        ]
    )


# Define first /start command handler
@form_router.message(CommandStart())
async def cmd_start(message: Message):
    # Check if user exists in DB, if not add them with default balance of 10000$
    async with aiosqlite.connect('bot_db.db') as db:
        async with db.execute('SELECT * FROM users WHERE id = ?', (message.from_user.id,)) as query:
            if not await query.fetchone():
                await db.execute('INSERT INTO users (id) VALUES (?)', (message.from_user.id,))
                await db.commit()
    await message.answer(f'Hello, {message.from_user.full_name}\nThis is a stocks Telegram bot, that allows you to look if you\'re a good trader', 
                         reply_markup=default_keyboard())
    
    
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
        reply_markup=default_keyboard(),
    )
    
    
# Define price check handler
@form_router.callback_query(F.data==PRICE_CB)
async def price_callback(callback: CallbackQuery, state: FSMContext):
    await state.set_state(StockStates.waiting_symbol)
    await callback.message.answer('Send me symbol of stock, price of which you want to check')
    await callback.answer()


# Check stock price handler after user sends symbol
@form_router.message(StockStates.waiting_symbol, F.text.regexp(r"^[A-Za-z]{1,5}$"))
async def check_price(message: Message, state: FSMContext):
    price = await check_stock_price(message.text)
    # If price is None then response from API was invalid(any error)
    if price == None:
        await message.answer('Invalid symbol. Please try again.', reply_markup=default_keyboard())
        await state.clear()
        return
    await message.answer(f'Current price of {message.text.upper()} is {price}$', reply_markup=default_keyboard())
    await state.clear()
    

# Define balance check handler
@form_router.callback_query(F.data==BALANCE_CB)
async def balance_callback(callback: CallbackQuery):
    async with aiosqlite.connect('bot_db.db') as db:
        async with db.execute('SELECT cash FROM users WHERE id = ?', (callback.from_user.id,)) as query:
            balance = await query.fetchone()
            await callback.message.answer(f'Your balance is {balance[0]}$', reply_markup=default_keyboard())
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
async def buy_symbol(message: Message, state: FSMContext):
    price = await check_stock_price(message.text)
    if price == None:
        await message.answer('Invalid symbol. Please try again.', reply_markup=default_keyboard())
        await state.clear()
        return
    await state.update_data(symbol=message.text.upper(), price=price)
    await state.set_state(StockStates.waiting_amount_buy)
    await message.answer(f'Current price of {message.text.upper()} is {price}$. How many stocks do you want to buy? (send me a number)')
    
    
# Buy stock amount handler after user sends amount. Check if user has enough balance and complete the purchase
@form_router.message(StockStates.waiting_amount_buy, F.text.regexp(r"^\d+$"))
async def buy_amount(message: Message, state: FSMContext):
    amount = int(message.text)
    if amount <= 0:
        await message.answer('Amount must be a positive integer. Please try again.', reply_markup=default_keyboard())
        await state.clear()
        return
    
    data = await state.get_data()
    # Check if price has changed since user sent symbol. If it has, ask to confirm purchase again
    price = await check_stock_price(data['symbol'])
    if price is None:
        await message.answer('Error fetching stock price. Please try again later.', reply_markup=default_keyboard())
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
    async with aiosqlite.connect('bot_db.db') as db:
        await db.execute('PRAGMA foreign_keys = ON;')
        async with db.execute('SELECT cash FROM users WHERE id = ?', (message.from_user.id,)) as query:
            balance = await query.fetchone()
            if int(balance[0]) < total_price:
                await message.answer(f'You don\'t have enough money to buy {amount} of {data["symbol"]}. Your balance is {balance[0]}$', reply_markup=default_keyboard())
                await state.clear()
                return
            # Complete the purchase: deduct money from balance and add stocks to user_savings table
            else:
                await db.execute('UPDATE users SET cash = cash - ? WHERE id = ?', (total_price, message.from_user.id))
                await db.execute('INSERT INTO user_savings (user_id, stock, quantity) VALUES (?, ?, ?) ON CONFLICT(user_id, stock) DO UPDATE SET quantity = quantity + excluded.quantity',
                                 (message.from_user.id, data['symbol'], amount))
                await db.commit()
                await message.answer(f'You have successfully bought {amount} of {data["symbol"]} for {total_price}$.', reply_markup=default_keyboard())
    

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
