import aiohttp
import pytest
import aiosqlite
import asyncio

from aiogram.types import Message, User, Chat
from aiogram import Bot
from aiogram.fsm.context import FSMContext

from bot.handlers import cmd_start, buy_amount, sell_amount
from config.strings import DEFAULT_HELLO
from bot.keyboards import Keyboards

pytestmark = pytest.mark.asyncio

async def test_cmd_start_new_user(db, mocker):
    mock_user = mocker.Mock(spec=User)
    mock_user.id = 1
    mock_user.username = None

    mock_message = mocker.Mock(spec=Message)
    mock_message.from_user = mock_user
    mock_message.answer = mocker.AsyncMock()

    await cmd_start(message=mock_message, db=db)

    async with db.execute('SELECT id, cash, username FROM users WHERE id=1') as query:
        data = await query.fetchone()

    assert data[0] == 1
    assert data[1] == 10000.00
    assert data[2] == 'N/A'

    mock_message.answer.assert_called_once_with(
        DEFAULT_HELLO,
        reply_markup=Keyboards.default_keyboard(),
        parse_mode='HTML'
    )

    await cmd_start(message=mock_message, db=db)

    async with db.execute('SELECT COUNT(*) FROM users') as query:
        data = await query.fetchone()

    assert data[0] == 1

async def test_cmd_start_existing_user(db, mocker):
    mock_user = mocker.Mock(spec=User)
    mock_user.id = 1
    mock_user.username = 'test'

    mock_message = mocker.Mock(spec=Message)
    mock_message.from_user = mock_user
    mock_message.answer = mocker.AsyncMock()

    await db.execute('INSERT INTO users (id, username) VALUES (?, ?)', (mock_message.from_user.id, mock_message.from_user.username,))
    await db.commit()

    await cmd_start(message=mock_message, db=db)

    async with db.execute('SELECT id, cash, username FROM users WHERE id=1') as query:
        data = await query.fetchone()

    assert data[0] == 1
    assert data[1] == 10000.00
    assert data[2] == 'test'

    mock_message.answer.assert_called_once_with(
        DEFAULT_HELLO,
        reply_markup=Keyboards.default_keyboard(),
        parse_mode='HTML'
    )

async def test_buy_amount(db, mocker):
    mock_state = mocker.Mock(spec=FSMContext)
    mock_state.get_data = mocker.AsyncMock()
    mock_state.get_data.return_value = {'symbol': 'AAPL', 'price': 152.90, 'bot_message_id': 1}

    mock_user = mocker.Mock(spec=User)
    mock_user.id = 1

    mock_message = mocker.Mock(spec=Message)
    mock_message.from_user = mock_user
    mock_message.text = 10
    mock_message.chat = mocker.Mock(spec=Chat)
    mock_message.chat.id = 123

    mock_bot = mocker.Mock(spec=Bot)
    mock_conn = mocker.AsyncMock(spec=aiohttp.ClientSession)

    mock_check_price = mocker.patch(
        'bot.handlers.check_stock_price',
        return_value = 152.90
    )

    await db.execute('INSERT INTO users (id, username) VALUES (?, ?)', (mock_user.id, 'test'))
    await db.commit()

    await buy_amount(mock_message, mock_state, db=db, session=mock_conn, bot=mock_bot)

    mock_check_price.assert_called_once_with('AAPL', mock_conn)

    async with db.execute('SELECT cash FROM users') as query:
        user_cash = await query.fetchone()

    async with db.execute('SELECT quantity FROM history') as query:
        quantity_history = await query.fetchone()

    async with db.execute('SELECT quantity FROM user_savings') as query:
        quantity_savings = await query.fetchone()

    assert 8471 == user_cash[0]
    assert 10 == quantity_history[0]
    assert 10 == quantity_savings[0]

async def test_buy_amount_changed_price(db, mocker):
    mock_state = mocker.Mock(spec=FSMContext)
    mock_state.get_data = mocker.AsyncMock()
    mock_state.get_data.return_value = {'symbol': 'AAPL', 'price': 140.90, 'bot_message_id': 1}

    mock_user = mocker.Mock(spec=User)
    mock_user.id = 1

    mock_message = mocker.Mock(spec=Message)
    mock_message.from_user = mock_user
    mock_message.text = 10
    mock_message.chat = mocker.Mock(spec=Chat)
    mock_message.chat.id = 123

    mock_bot = mocker.Mock(spec=Bot)
    mock_conn = mocker.AsyncMock(spec=aiohttp.ClientSession)

    mock_check_price = mocker.patch(
        'bot.handlers.check_stock_price',
        return_value = 152.90
    )

    await db.execute('INSERT INTO users (id, username) VALUES (?, ?)', (mock_user.id, 'test'))
    await db.commit()

    await buy_amount(mock_message, mock_state, db=db, session=mock_conn, bot=mock_bot)

    mock_check_price.assert_called_once_with('AAPL', mock_conn)

    async with db.execute('SELECT cash FROM users') as query:
        user_cash = await query.fetchone()

    assert user_cash[0] == 10000.00

async def test_sell_amount(db, mocker):
    mock_state = mocker.Mock(spec=FSMContext)
    mock_state.get_data = mocker.AsyncMock()
    mock_state.get_data.return_value = {'symbol': 'AAPL', 'price': 152.90, 'bot_message_id': 1}

    mock_user = mocker.Mock(spec=User)
    mock_user.id = 1

    mock_message = mocker.Mock(spec=Message)
    mock_message.from_user = mock_user
    mock_message.text = 10
    mock_message.chat = mocker.Mock(spec=Chat)
    mock_message.chat.id = 123

    mock_bot = mocker.Mock(spec=Bot)
    mock_conn = mocker.AsyncMock(spec=aiohttp.ClientSession)

    mock_check_price = mocker.patch(
        'bot.handlers.check_stock_price',
        return_value = 160.00 # Important! Price here is bigger than in mock_state
        # because user would sell his stock if the price is now bigger as it was earlier
    )

    await db.execute('INSERT INTO users (id, username) VALUES (?, ?)', (mock_user.id, 'test'))
    await db.execute('INSERT INTO user_savings (user_id, stock, quantity) VALUES (?, ?, ?)',
                     (mock_user.id, 'AAPL', 12)
                     )
    await db.commit()

    await sell_amount(mock_message, mock_state, db=db, session=mock_conn, bot=mock_bot)

    mock_check_price.assert_called_once_with('AAPL', mock_conn)

    async with db.execute('SELECT cash FROM users') as query:
        user_cash = await query.fetchone()

    async with db.execute('SELECT quantity FROM user_savings') as query:
        user_stocks = await query.fetchone()

    async with db.execute('SELECT quantity FROM history') as query:
        selled_stocks = await query.fetchone()

    assert user_cash[0] == 11600.00
    assert user_stocks[0] == 2
    assert selled_stocks[0] == -10
