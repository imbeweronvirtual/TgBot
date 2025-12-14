# 📈 Virtual Stock Trading Telegram Bot

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Aiogram](https://img.shields.io/badge/Aiogram-3.x-blue)

A fully asynchronous Telegram bot that allows users to practice stock trading in a risk-free environment. Users start with **$10,000** in virtual cash and can buy/sell real stocks using real-time market data.

Built with modern Python async libraries to handle high concurrency.

## ✨ Key Features

* **Virtual Economy:** Every new user receives a $10,000 starting balance.
* **Real-Time Data:** Fetches yesterday's stock prices using the Alpha Vantage API.
* **Portfolio Management:** View owned stocks, current value, and profit/loss.
* **Transaction History:** Detailed logs of every buy and sell order.
* **Admin Panel:**
    * Broadcast messages to all users.
    * View user reports and stats.
    * Delete users.
* **Robust Architecture:** Uses FSM (Finite State Machine) for complex user flows and SQLite for data persistence.

## 🛠️ Tech Stack

* **Language:** Python 3.10+
* **Framework:** [aiogram 3.x](https://docs.aiogram.dev/) (Asynchronous Telegram Bot API)
* **Database:** SQLite + [aiosqlite](https://github.com/omnilib/aiosqlite)
* **HTTP Requests:** [aiohttp](https://docs.aiohttp.org/)
* **Testing:** pytest, pytest-asyncio, pytest-mock

## ⚙️ APIs Used

1.  **[Alpha Vantage](https://www.alphavantage.co/)**: For real-time stock market data.
2.  **[Telegram Bot API](https://core.telegram.org/bots#how-do-i-create-a-bot)**: For user interaction.

## 🚀 Installation & Setup

### Prerequisites
* Python 3.10 or higher
* A Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
* An Alpha Vantage API Key

### 1. Clone the repository
```bash
git clone https://github.com/imbeweronvirtual/TgBot.git
cd TgBot
```

### 2. Create a Virtual Environment
```bash
# Linux/macOS
python3 -m venv .venv
source .venv/bin/activate

# Windows
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install Dependencies
```bash
# Install production dependencies
pip install -r requirements.txt
```

### 4. Configuration
Edit the following variables in the .env file:
```ini
BOT_TOKEN=your_telegram_bot_token
ADMIN_IDS=12345678,87654321
ALPHA_API=your_alpha_vantage_key
```

### 5. Run the Bot
```bash
python run.py
```

## 📂 Project Structure

```text
Telegram Bot/
├── bot/
│   ├── admin.py         # Admin command handlers
│   ├── handlers.py      # User command handlers
│   └── keyboards.py     # Inline keyboards
├── config/
│   ├── callbacks.py     # Callback data factories
│   ├── config.py        # Environment variable loader
│   ├── strings.py       # User-facing text messages
│   └── strings_admin.py # Admin-facing text messages
├── database/
│   ├── bot_db.db        # SQLite Database
│   └── schema.sql       # DB schema
├── tests/
│   ├── conftest.py      # Pytest fixtures (DB, Event Loop)
│   ├── test_handlers.py # Integration tests for bot handlers
│   └── test_helpers.py  # Unit tests for helper functions
├── .env                 # API keys and environment variables
├── helpers.py           # Utility functions (API calls, calculations)
├── requirements.txt     # Dependencies
└── run.py               # Application entry point
```

## 🗄️ Database Schema

The bot uses a relational SQLite database structure:

![Database Schema](https://github.com/user-attachments/assets/01d73336-b185-4742-addd-c1937b1cb3fe)
