from config import ALPHA_API
import aiohttp

async def check_stock_price(symbol):
    ticker = symbol.upper()
    url = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={ticker}&apikey={ALPHA_API}'

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                return None
            data = await response.json()
    
    try:
        time_series = data["Time Series (Daily)"]
        close_price = time_series[max(time_series.keys())]["4. close"]
        return close_price

    except Exception:
        return None