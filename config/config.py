import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
ALPHA_API = os.getenv("ALPHA_API")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]

IGNORE_SENDER = False # Sends a message to admin that has initiated broadcasting if false, otherwise skips that admin
