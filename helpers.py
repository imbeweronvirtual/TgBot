from config.config import ALPHA_API
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