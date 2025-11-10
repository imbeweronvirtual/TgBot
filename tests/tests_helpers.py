from unittest.mock import AsyncMock

import aiosqlite
import pytest
import asyncio
import aiohttp

from aiogram.types import Message, CallbackQuery, User
from pytest_mock import mocker

from config.config import ALPHA_API
from helpers import check_stock_price, calc_profit, fetch_stock_data, username_db_check

pytestmark = pytest.mark.asyncio

async def test_check_stock_price(mocker):
    json_response = {
            "Meta Data": {
                "1. Information": "Daily Prices (open, high, low, close) and Volumes",
                "2. Symbol": "IBM",
                "3. Last Refreshed": "2025-11-06",
                "4. Output Size": "Compact",
                "5. Time Zone": "US/Eastern"
            },
            "Time Series (Daily)": {
                "2025-11-06": {
                    "1. open": "306.7500",
                    "2. high": "315.4400",
                    "3. low": "301.0900",
                    "4. close": "312.4200",
                    "5. volume": "6818521"
                },
                "2025-11-05": {
                    "1. open": "301.3800",
                    "2. high": "307.2000",
                    "3. low": "299.7100",
                    "4. close": "306.7700",
                    "5. volume": "4633195"
                },
                "2025-11-04": {
                    "1. open": "300.0000",
                    "2. high": "303.1700",
                    "3. low": "296.0000",
                    "4. close": "300.8500",
                    "5. volume": "5677330"
                },
            }
    }


    mock_response = mocker.AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = json_response

    mock_get_context = mocker.AsyncMock()
    mock_get_context.__aenter__.return_value = mock_response
    mock_get_context.__aexit__.return_value = None

    mock_session = mocker.AsyncMock(spec=aiohttp.ClientSession)

    mock_session.get.return_value = mock_get_context

    price = await check_stock_price('IBM', session=mock_session)

    assert price == "312.4200"

    mock_session.get.assert_called_once_with(f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol=IBM&apikey={ALPHA_API}')

async def test_check_stock_price_status(mocker):
    mock_response = mocker.AsyncMock()
    mock_response.status = 404

    mock_get_context = mocker.AsyncMock()
    mock_get_context.__aenter__.return_value = mock_response
    mock_get_context.__aexit__.return_value = None

    mock_session = mocker.AsyncMock(spec=aiohttp.ClientSession)
    mock_session.get.return_value = mock_get_context

    price = await check_stock_price('IBM', session=mock_session)

    assert price is None

    mock_session.get.assert_called_once_with(f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol=IBM&apikey={ALPHA_API}')

async def test_calc_profit(mocker, db):
    USER_ID = 1
    STOCK = 'AAPL'
    query = 'INSERT INTO history (user_id, stock, price, quantity) VALUES (?, ?, ?, ?)'

    trade_history = [
        (USER_ID, STOCK, '254.04', 4),
        (USER_ID, STOCK, '245.27', -2),
        (USER_ID, STOCK, '252.29', 10),
        (USER_ID, 'IBM', '200.00', 100),
        (2, STOCK, '200.00', -1000),
        (USER_ID, STOCK, '262.23', -8)
    ]
    quantity_user_has = 4

    await db.executemany(query, trade_history)
    await db.commit()

    spent = await calc_profit(USER_ID, quantity_yet=quantity_user_has, stock=STOCK, db=db)

    assert spent == 1009.16

async def test_fetch_stock_data(mocker, db):
    USER_ID = 1
    STOCK = 'AAPL'
    quantity = 4
    json_response = {
        "Meta Data": {
            "1. Information": "Daily Prices (open, high, low, close) and Volumes",
            "2. Symbol": "AAPL",
            "3. Last Refreshed": "2025-11-06",
            "4. Output Size": "Compact",
            "5. Time Zone": "US/Eastern"
        },
        "Time Series (Daily)": {
            "2025-11-06": {
                "1. open": "306.7500",
                "2. high": "315.4400",
                "3. low": "301.0900",
                "4. close": "192.4200",
                "5. volume": "6818521"
            },
            "2025-11-05": {
                "1. open": "301.3800",
                "2. high": "307.2000",
                "3. low": "299.7100",
                "4. close": "306.7700",
                "5. volume": "4633195"
            },
            "2025-11-04": {
                "1. open": "300.0000",
                "2. high": "303.1700",
                "3. low": "296.0000",
                "4. close": "300.8500",
                "5. volume": "5677330"
            },
        }
    }

    mock_response = mocker.AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = json_response

    mock_get_context = mocker.AsyncMock()
    mock_get_context.__aenter__.return_value = mock_response
    mock_get_context.__aexit__.return_value = None

    mock_session = mocker.AsyncMock(spec=aiohttp.ClientSession)

    mock_session.get.return_value = mock_get_context

    trade_history = [
        (USER_ID, STOCK, '254.04', 4),
        (USER_ID, STOCK, '245.27', -2),
        (USER_ID, STOCK, '252.29', 10),
        (USER_ID, 'IBM', '200.00', 100),
        (2, STOCK, '200.00', -1000),
        (USER_ID, STOCK, '262.23', -8)
    ]
    query = 'INSERT INTO history (user_id, stock, price, quantity) VALUES (?, ?, ?, ?)'

    await db.executemany(query, trade_history)
    await db.commit()

    stock_data = await fetch_stock_data(USER_ID, STOCK, quantity, session=mock_session, db=db)

    assert stock_data == "  • <b>AAPL:</b> 4pcs. (Total: <b>$769.68</b> / Profit: <b>$-239.48</b>)"

async def test_username_db_check_message(mocker, db):
    await db.execute('INSERT INTO users (id, username) VALUES (?, ?)', (1, 'other'))
    await db.commit()

    mock_user = mocker.Mock(spec=User)
    mock_user.id = 1
    mock_user.username = 'test'

    mock_message = mocker.Mock(spec=Message)
    mock_message.from_user = mock_user

    await username_db_check(mock_message, db=db)

    async with db.execute('SELECT COUNT(*) FROM users WHERE username = ?', ('test',)) as query:
        data = await query.fetchone()

    assert data[0] == 1

async def test_username_db_check_callback(mocker, db):
    await db.execute('INSERT INTO users (id, username) VALUES (?, ?)', (1, 'other'))
    await db.commit()

    mock_user = mocker.Mock(spec=User)
    mock_user.id = 1
    mock_user.username = 'test'

    mock_message = mocker.Mock(spec=CallbackQuery)
    mock_message.from_user = mock_user

    await username_db_check(mock_message, db=db)

    async with db.execute('SELECT COUNT(*) FROM users WHERE username = ?', ('test',)) as query:
        data = await query.fetchone()

    assert data[0] == 1









