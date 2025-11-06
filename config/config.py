import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN") # Bot token from @BotFather
ALPHA_API = os.getenv("ALPHA_API") # Alpha Vantage API key
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x] # List of admin IDs

IGNORE_SENDER = False # Sends a message to admin that has initiated broadcasting if false, otherwise skips that admin
