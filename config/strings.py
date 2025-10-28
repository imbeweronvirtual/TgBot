# === Welcome ===
DEFAULT_HELLO=(
    "👋 <b>Welcome to the Stocks Trading Bot!</b>\n\n"
    "I'm here to help you practice your trading skills in a realistic, real-time environment. \n"
    "<b>Here's what you can do:</b>\n"
    "  •  <b>Check Price:</b> Get real-time prices for any stock.\n"
    "  •  <b>Buy Stocks:</b> Purchase shares with your virtual cash.\n"
    "  •  <b>Sell Stocks:</b> Sell shares from your portfolio.\n"
    "  •  <b>Profile:</b> View all the stocks and the balance you currently own.\n\n"
    "Use the menu below to get started!"
)

# === Price Check ===
SEND_SYMBOL_CHECK='⌨️ Please enter a stock symbol to check its price (e.g., AAPL).'
INVALID_SYMBOL='❌ <b>Invalid Symbol.</b> Please check the ticker and try again.'
CURRENT_PRICE='💹 <b>{symbol}</b>: <code>${price}</code>'
CURRENT_BALANCE='💰 Your balance is <b>${price:.2f}</b>'

# === Buying ===
SEND_SYMBOL_BUY='🛒 What stock would you like to buy? (e.g., TSLA)\n<b>💵 Balance of your account: {balance:.2f}$</b>'
SEND_AMOUNT_BUY='🔢 Please enter the amount you wish to buy (e.g., 5)'
CONFIRM_BUY='⚠️ <b>Attention!</b>\nThe price of <b>{symbol}</b> has changed from ${old_price} to <b>${new_price}</b>.\n\nPlease confirm the purchase at the new price.'
NO_MONEY_BUY='😥 <b>Insufficient Funds.</b>\nYou tried to buy {amount} <b>{symbol}</b>, but you only have <b>${balance:.2f}</b> in your account.'
BUY_SUCCESSFUL='✅ <b>Purchase Successful!</b>\nYou bought {amount} <b>{symbol}</b> for <b>${total_price}</b>.'

# === Selling ===
SEND_SYMBOL_SELL='🏷️ Which stock from your portfolio would you like to sell?'
NO_STOCK_SELL='❌ <b>Stock Not Found.</b>\nYou do not own any <b>{symbol}</b> shares.'
SEND_AMOUNT_SELL='🔢 How many shares of <b>{symbol}</b> would you like to sell?'
NOT_ENOUGH_STOCKS= '⚠️ <b>Not Enough Shares.</b>\nYou are trying to sell {asked_amount} <b>{symbol}</b>, but you only own <b>{owned_amount} shares.</b>'
CONFIRM_SELL='⚠️ <b>Attention!</b>\nThe price of <b>{symbol}</b> has changed from ${old_price} to <b>${new_price}</b>.\n\nPlease confirm the sale at the new price.'
SELL_SUCCESSFUL='💸 <b>Sale Successful!</b>\nYou sold {amount} <b>{symbol}</b> for <b>${price}</b>.'

# === Portfolio ===
NO_STOCKS='🗂️ Your portfolio is empty. Time to start trading!'

# === Errors & General ===
ANY_ERROR='🛠️ <b>An error occurred.</b> Please try again in a few moments.'
SERVER_ERROR_PRICE='📡 Failed to fetch stock price. The external service may be down. Please try again later.'
INVALID_AMOUNT='❌ Please enter a valid positive number (e.g., 1, 5, or 10).'