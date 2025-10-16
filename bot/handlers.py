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
from aiogram.methods import EditMessageText

from config.config import TOKEN, ALPHA_API
from helpers import check_stock_price, edit_bot_message

from config.strings import (
    DEFAULT_HELLO,
    SEND_SYMBOL_BUY,
    INVALID_SYMBOL,
    INVALID_AMOUNT,
    CURRENT_PRICE,
    CURRENT_BALANCE,
    SEND_AMOUNT_BUY,
    SERVER_ERROR_PRICE,
    CONFIRM_BUY,
    CONFIRM_SELL,
    NO_MONEY_BUY,
    NO_STOCK_SELL,
    NOT_ENOUGHT_STOCKS,
    BUY_SUCCESSFUL,
    SELL_SUCCESSFUL,
    SEND_AMOUNT_SELL,
    SEND_SYMBOL_CHECK,
    SEND_SYMBOL_SELL,
    NO_STOCKS,
    ANY_ERROR,
)
from config.callbacks import BALANCE_CB, MY_STOCKS_CB, BUY_CB, SELL_CB, PRICE_CB, RETURN_CB
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
    await message.answer(DEFAULT_HELLO, reply_markup=Keyboards.default_keyboard())
    
    
# Define /cancel command handler and "cancel" text handler to cancel any ongoing state if return button fails   
@form_router.message(Command("cancel"))
@form_router.message(F.text.casefold() == "cancel")
async def cancel_handler(message: Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state is None:
        await delete_unwanted(message)
        return

    logging.info("Cancelling state %r", current_state)
    await state.clear()
    
    text = DEFAULT_HELLO.format(name = message.from_user.full_name)
    await message.answer(
        "Cancelled.\n" + text,
        reply_markup=Keyboards.default_keyboard(),
    )
    
    
@form_router.callback_query(F.data==RETURN_CB)
async def return_main(callback: CallbackQuery, state: FSMContext):
    await edit_bot_message(
        text=DEFAULT_HELLO,
        event=callback,
        markup=Keyboards.default_keyboard()
    )
    
    current_state = await state.get_state()

    if current_state is not None:
        state.clear()

    callback.answer()
    
    
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
    data = await state.get_data()
    
    price = await check_stock_price(message.text, session)
    # If price is None then response from API was invalid(any error)
    if price == None:
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
async def start_buy_callback(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await edit_bot_message(
        text=SEND_SYMBOL_BUY,
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
    if price == None:
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
    if price != data['price']:
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
async def start_sell_callback(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await edit_bot_message(
        text=SEND_SYMBOL_SELL,
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
    if price == None:
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
    text = [CURRENT_PRICE.format(symbol=stock[0], price=price), SEND_AMOUNT_SELL]
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
        text = [NOT_ENOUGHT_STOCKS.format(symbol=data['symbol'], amount=available_amount[0]), DEFAULT_HELLO]
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
async def check_savings(callback: CallbackQuery, db: aiosqlite.Connection):
    # Query that joins two tables, firsrt - users, for receiving balance of account, second = user_savings to receive stocks owned
    async with db.execute('SELECT s.stock, s.quantity, u.cash FROM users u LEFT JOIN user_savings s ON u.id = s.user_id WHERE u.id = ?;', (callback.from_user.id,)) as query:
        savings = await query.fetchall()
        
    if not savings[0][0]:
        try:
            await callback.message.edit_text('You don\'t have any stocks yet', reply_markup=Keyboards.default_keyboard())
        except Exception:
            await callback.message.answer('You don\'t have any stocks yet', reply_markup=Keyboards.default_keyboard())
        finally:
            await callback.answer()
        return
    else:
        formatted_message = [f"<b>💵 Balance of your account: {"{:.2f}".format(savings[0][2])}$</b>\n\n"]
        formatted_message.append("<b>💼 Your stock portfolio:</b>\n")
        for stock, quantity, _ in savings:
            formatted_message.append(f'\t• <b>{stock}:</b> {quantity}pcs.')
            
        formatted_message = '\n'.join(formatted_message)
        
        try:
            await callback.message.edit_text(formatted_message, parse_mode='HTML', reply_markup=Keyboards.return_keyboard())
        except Exception as e:
            logging.warning(e)
        finally:
            await callback.answer()
        
    
    
@form_router.message(StateFilter(None))
async def delete_unwanted(message: Message):
    try:
        await message.delete()
    except Exception:
        logging.info('Cannot delete message')