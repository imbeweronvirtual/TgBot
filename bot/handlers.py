import asyncio
import logging

import aiosqlite
import aiohttp

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from helpers import check_stock_price, edit_bot_message, fetch_stock_data, username_db_check

from config.strings import (
    DEFAULT_HELLO,
    SEND_SYMBOL_BUY,
    INVALID_SYMBOL,
    INVALID_AMOUNT,
    CURRENT_PRICE,
    SEND_AMOUNT_BUY,
    SERVER_ERROR_PRICE,
    CONFIRM_BUY,
    CONFIRM_SELL,
    NO_MONEY_BUY,
    NO_STOCK_SELL,
    NOT_ENOUGH_STOCKS,
    BUY_SUCCESSFUL,
    SELL_SUCCESSFUL,
    SEND_AMOUNT_SELL,
    SEND_SYMBOL_CHECK,
    SEND_SYMBOL_SELL,
    NO_STOCKS,
    ANY_ERROR,
)
from config.callbacks import MY_STOCKS_CB, BUY_CB, SELL_CB, PRICE_CB, RETURN_CB
from bot.keyboards import Keyboards

# Initialize states
class StockStates(StatesGroup):
    waiting_symbol = State()
    waiting_symbol_buy = State()
    waiting_amount_buy = State()
    waiting_symbol_sell = State()
    waiting_amount_sell = State()
    
    waiting_user_id_check = State()
    
# Initialize router and default keyboard
form_router = Router()
default_keyboard = Keyboards()



# Define first /start command handler
@form_router.message(CommandStart())
async def cmd_start(message: Message, db: aiosqlite.Connection):
    # Check if user exists in DB, if not, add them with a default balance of 10 000$
    async with db.execute('SELECT * FROM users WHERE id = ?', (message.from_user.id,)) as query:
        if not await query.fetchone():
            await db.execute('INSERT INTO users (id, username) VALUES (?, ?)', (message.from_user.id, message.from_user.username if message.from_user.username else 'N/A',))
            await db.commit()
    await message.answer(DEFAULT_HELLO, reply_markup=Keyboards.default_keyboard(), parse_mode='HTML')
    
    

    
    
@form_router.callback_query(F.data==RETURN_CB)
async def return_main(callback: CallbackQuery, state: FSMContext, db: aiosqlite.Connection):
    await edit_bot_message(
        text=DEFAULT_HELLO,
        event=callback,
        markup=Keyboards.default_keyboard()
    )
    
    current_state = await state.get_state()

    if current_state is not None:
        await state.clear()

    await username_db_check(event=callback, db=db)

    await callback.answer()
    
    
# Define price check handler
@form_router.callback_query(F.data==PRICE_CB)
async def price_callback(callback: CallbackQuery, state: FSMContext):
    await state.set_state(StockStates.waiting_symbol)
    await state.update_data(bot_message_id=callback.message.message_id)
    await edit_bot_message(
        text=SEND_SYMBOL_CHECK,
        event=callback,
        markup=Keyboards.return_keyboard()
    )
    await callback.answer()


# Check stock price handler after user sends symbol
@form_router.message(StockStates.waiting_symbol, F.text.regexp(r"^[A-Za-z]{1,5}$"))
async def check_price(message: Message, state: FSMContext, session: aiohttp.ClientSession, bot: Bot):
    await delete_unwanted(message)
    
    data = await state.get_data()
    
    price = await check_stock_price(message.text, session)
    # If price is None then response from API was invalid(any error)
    if price is None:
        text = [ANY_ERROR, DEFAULT_HELLO]
        await edit_bot_message(
            text='\n\n'.join(text),
            event=message,
            message_id=data.get('bot_message_id'),
            bot=bot,
            markup=Keyboards.default_keyboard()
        )
        await state.clear()
        return
    text = [CURRENT_PRICE.format(symbol=message.text.upper(), price=price), DEFAULT_HELLO]
    await edit_bot_message(
        text='\n\n'.join(text),
        event=message,
        message_id=data.get('bot_message_id'),
        bot=bot,
        markup=Keyboards.default_keyboard()
    )
    await state.clear()
    

# Define buy stocks handlers
@form_router.callback_query(F.data==BUY_CB)
async def start_buy_callback(callback: CallbackQuery, state: FSMContext, bot: Bot, db: aiosqlite.Connection):
    async with db.execute('SELECT cash FROM users WHERE id = ?', (callback.from_user.id,)) as query:
        balance = await query.fetchone()
    await edit_bot_message(
        text=SEND_SYMBOL_BUY.format(balance=balance[0] if balance else 0),
        event=callback,
        message_id=callback.message.message_id,
        bot=bot,
        markup=Keyboards.return_keyboard()
    )
    await state.set_state(StockStates.waiting_symbol_buy)
    await callback.answer()
    await state.update_data(bot_message_id=callback.message.message_id)


# Buy stock symbol handler after user sends symbol. Check if symbol is valid and get its price.
# Then ask for amount to buy
@form_router.message(StockStates.waiting_symbol_buy, F.text.regexp(r"^[A-Za-z]{1,5}$"))
async def buy_symbol(message: Message, state: FSMContext, session: aiohttp.ClientSession, bot: Bot):
    await delete_unwanted(message)
    
    data = await state.get_data()
    
    price = await check_stock_price(message.text, session)
    if price is None:
        await edit_bot_message(
            text='\n\n'.join([INVALID_SYMBOL, DEFAULT_HELLO]),
            event=message,
            message_id=data.get('bot_message_id'),
            bot=bot,
            markup=Keyboards.default_keyboard()
        )
        await state.clear()
        return
    await state.update_data(symbol=message.text.upper(), price=price)
    await state.set_state(StockStates.waiting_amount_buy)
    
    text = [CURRENT_PRICE.format(symbol=message.text.upper(), price=price), SEND_AMOUNT_BUY]
    await edit_bot_message(
        text=" ".join(text),
        event=message,    
        message_id=data.get('bot_message_id'),
        bot=bot,
        markup=Keyboards.return_keyboard()
    )
    
    
# Buy stock amount handler after user sends amount. Check if user has enough balance and complete the purchase
@form_router.message(StockStates.waiting_amount_buy, F.text.regexp(r"^\d+$"))
async def buy_amount(message: Message, state: FSMContext, db: aiosqlite.Connection, session: aiohttp.ClientSession, bot: Bot):
    await delete_unwanted(message)
    
    data = await state.get_data()
    
    amount = int(message.text)
    if amount <= 0:
        await edit_bot_message(
            text='\n\n'.join([INVALID_AMOUNT, DEFAULT_HELLO]),
            event=message,
            message_id=data.get('bot_message_id'),
            bot=bot,
            markup=Keyboards.default_keyboard()
        )
        await state.clear()
        return

    # Check if price has changed since user sent symbol. If it has, ask to confirm purchase again
    price = await check_stock_price(data['symbol'], session)
    if price is None:
        await edit_bot_message(
            text='\n\n'.join([SERVER_ERROR_PRICE, DEFAULT_HELLO]),
            event=message,
            message_id=data.get('bot_message_id'),
            bot=bot,
            markup=Keyboards.default_keyboard()
        )
        await state.clear()
        return
    if price > data['price']:
        text = [CONFIRM_BUY.format(symbol=data["symbol"], old_price=data["price"], new_price=price), DEFAULT_HELLO]
        await edit_bot_message(
            text='\n\n'.join(text),
            event=message,
            message_id=data.get('bot_message_id'),
            bot=bot,
            markup=Keyboards.default_keyboard()
        )
        await state.clear()
        return
    total_price = amount * float(price)

    # Check if user has enough balance
    await db.execute('PRAGMA foreign_keys = ON')
    try:
        await db.execute('BEGIN')
        async with db.execute('SELECT cash FROM users WHERE id = ?', (message.from_user.id,)) as query:
            balance = await query.fetchone()
            if int(balance[0]) < total_price:
                text = [NO_MONEY_BUY.format(amount=amount, symbol=data["symbol"], balance=balance[0]), DEFAULT_HELLO]
                await edit_bot_message(
                    text='\n\n'.join(text),
                    event=message,
                    message_id=data.get('bot_message_id'),
                    bot=bot,
                    markup=Keyboards.default_keyboard()
                )
                return
            # Complete the purchase: deduct money from balance and add stocks to user_savings table
            else:
                await db.execute('UPDATE users SET cash = cash - ? WHERE id = ?', (total_price, message.from_user.id))
                await db.execute('INSERT INTO user_savings (user_id, stock, quantity) VALUES (?, ?, ?) ON CONFLICT(user_id, stock) DO UPDATE SET quantity = quantity + excluded.quantity',
                                (message.from_user.id, data['symbol'], amount,))
                await db.execute('INSERT INTO history (user_id, stock, price, quantity) VALUES (?, ?, ?, ?)',
                                    (message.from_user.id, data['symbol'], price, amount,))
                await db.commit()
                
                text = [BUY_SUCCESSFUL.format(amount=amount, symbol=data['symbol'], total_price=total_price), DEFAULT_HELLO]
                await edit_bot_message(
                    text='\n\n'.join(text),
                    event=message,
                    message_id=data.get('bot_message_id'),
                    bot=bot,
                    markup=Keyboards.default_keyboard()
                )
    except Exception as e:
        await db.rollback()
        logging.error(f'Transaction failed: {e}')
        await edit_bot_message(
            text='\n\n'.join([ANY_ERROR, DEFAULT_HELLO]),
            event=message,
            message_id=data.get('bot_message_id'),
            bot=bot,
            markup=Keyboards.default_keyboard()
        )
    finally:
        await state.clear()
            
        
            
@form_router.callback_query(F.data==SELL_CB)
async def start_sell_callback(callback: CallbackQuery, state: FSMContext, bot: Bot, db: aiosqlite.Connection):
    async with db.execute('SELECT stock, quantity FROM user_savings WHERE user_id = ?', (callback.from_user.id,)) as query:
        savings = await query.fetchall()
        
    if not savings:
        await edit_bot_message(
            text=NO_STOCKS,
            event=callback,
            markup=Keyboards.return_keyboard()
        )
        return
    else:
        formatted_message = [SEND_SYMBOL_SELL + "\n\n", "<b>💼 Your stock portfolio:</b>\n"]
        for stock, quantity in savings:
            formatted_message.append(f'  • <b>{stock}:</b> {quantity}pcs.')
        formatted_message = '\n'.join(formatted_message)
        
        await edit_bot_message(
            text=formatted_message,
            event=callback,
            message_id=callback.message.message_id,
            bot=bot,
            markup=Keyboards.return_keyboard()
        )
        
        await state.set_state(StockStates.waiting_symbol_sell)
        await state.update_data(bot_message_id=callback.message.message_id)
        
    await callback.answer()
        
    
    
    
    
    
    
@form_router.message(StockStates.waiting_symbol_sell, F.text.regexp(r"^[A-Za-z]{1,5}$"))
async def sell_symbol(message: Message, state: FSMContext, db: aiosqlite.Connection, session: aiohttp.ClientSession, bot: Bot):
    await delete_unwanted(message)
    
    data = await state.get_data()
    
    async with db.execute('SELECT stock FROM user_savings WHERE user_id = ? AND stock = ?', (message.from_user.id, message.text.upper())) as query:
        stock = await query.fetchone()
        if not stock:
            text = [NO_STOCK_SELL.format(symbol=message.text.upper()), DEFAULT_HELLO]
            await edit_bot_message(
                text='\n\n'.join(text),
                event=message,
                message_id=data.get('bot_message_id'),
                bot=bot,
                markup=Keyboards.default_keyboard()
            )
            await state.clear()
            return

    price = await check_stock_price(stock[0], session)
    if price is None:
        await edit_bot_message(
            text='\n\n'.join([ANY_ERROR, DEFAULT_HELLO]),
            event=message,
            message_id=data.get('bot_message_id'),
            bot=bot,
            markup=Keyboards.default_keyboard()
        )
        await state.clear()
        return
    await state.update_data(symbol=stock[0], price=price)
    await state.set_state(StockStates.waiting_amount_sell)
    text = [CURRENT_PRICE.format(symbol=stock[0], price=price), SEND_AMOUNT_SELL.format(symbol=stock[0])]
    await edit_bot_message(
        text=' '.join(text),
        event=message,
        message_id=data.get('bot_message_id'),
        bot=bot,
        markup=Keyboards.return_keyboard()
    )


@form_router.message(StockStates.waiting_amount_sell, F.text.regexp(r"^\d+$"))
async def sell_amount(message: Message, state: FSMContext, db: aiosqlite.Connection, session: aiohttp.ClientSession, bot: Bot):
    await delete_unwanted(message)
    
    data = await state.get_data()
    
    amount = int(message.text)
    
    async with db.execute('SELECT quantity FROM user_savings WHERE user_id = ? AND stock = ?', (message.from_user.id, data['symbol'])) as query:
        available_amount = await query.fetchone()
    
    if amount <= 0:
        await edit_bot_message(
            text='\n\n'.join([INVALID_AMOUNT, DEFAULT_HELLO]),
            event=message,
            message_id=data.get('bot_message_id'),
            bot=bot,
            markup=Keyboards.default_keyboard()
        )
        await state.clear()
        return
    
    if not available_amount or amount > available_amount[0]:
        text = [NOT_ENOUGH_STOCKS.format(symbol=data['symbol'], asked_amount=amount, owned_amount=available_amount[0]), DEFAULT_HELLO]
        await edit_bot_message(
            text='\n\n'.join(text),
            event=message,
            message_id=data.get('bot_message_id'),
            bot=bot,
            markup=Keyboards.default_keyboard()
        )
        await state.clear()
        return
    
    # Check if price has changed since user sent symbol. If it has, ask to confirm sell again
    price = await check_stock_price(data['symbol'], session)
    if price is None:
        await edit_bot_message(
            text='\n\n'.join([ANY_ERROR, DEFAULT_HELLO]),
            event=message,
            message_id=data.get('bot_message_id'),
            bot=bot,
            markup=Keyboards.default_keyboard()
        )
        await state.clear()
        return
    if price < data['price']:
        text = [CONFIRM_SELL.format(symbol=data['symbol'], old_price=data['price'], new_price=price), DEFAULT_HELLO]
        await edit_bot_message(
            text='\n\n'.join(text),
            event=message,
            message_id=data.get('bot_message_id'),
            bot=bot,
            markup=Keyboards.default_keyboard()
        )
        await state.clear()
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
        await edit_bot_message(
            text='\n\n'.join([ANY_ERROR, DEFAULT_HELLO]),
            event=message,
            message_id=data.get('bot_message_id'),
            bot=bot,
            markup=Keyboards.default_keyboard()
        )
        logging.error(f'Error occurred while selling stock: {e}')
        return
    
    text = [SELL_SUCCESSFUL.format(amount=amount, symbol=data['symbol'], price=price), DEFAULT_HELLO]
    await edit_bot_message(
            text='\n\n'.join(text),
            event=message,
            message_id=data.get('bot_message_id'),
            bot=bot,
            markup=Keyboards.default_keyboard()
        )
    await state.clear()
    

@form_router.callback_query(F.data==MY_STOCKS_CB)
async def check_savings(callback: CallbackQuery, db: aiosqlite.Connection, session: aiohttp.ClientSession):
    # Query that joins two tables, first - users, for receiving balance of account, second = user_savings to receive stocks owned
    async with db.execute('SELECT s.stock, s.quantity, u.cash FROM users u LEFT JOIN user_savings s ON u.id = s.user_id WHERE u.id = ?;', (callback.from_user.id,)) as query:
        savings = await query.fetchall()
        
    formatted_message = [f"<b>💵 Balance of your account: {"{:.2f}".format(savings[0][2])}$</b>\n\n"]
    if not savings[0][0]:
        formatted_message.append("<b>💼 You don't have any stocks yet.</b>")
    else:
        formatted_message.append("<b>💼 Your stock portfolio:</b>\n")
        
        tasks = []
        
        for stock, quantity, _ in savings:
            tasks.append(fetch_stock_data(user_id=callback.from_user.id, stock=stock, quantity=quantity, session=session, db=db))
            
        try:
            stock_lines = await asyncio.gather(*tasks)
            formatted_message.extend(stock_lines)
        except Exception as e:
            logging.error(f'Error during gather: {e}')
            formatted_message.append('\n❌ Service not available now')
        
    
    await edit_bot_message(text='\n'.join(formatted_message), event=callback, markup=Keyboards.return_keyboard())
    await callback.answer()
        
    
    
@form_router.message()
async def delete_unwanted(message: Message):
    try:
        await message.delete()
    except Exception as e:
        logging.info(f'Cannot delete message: {e}')