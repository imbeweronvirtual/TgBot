DEFAULT_HELLO='Hello\nThis is a stocks Telegram bot, that allows you to look if you\'re a good trader'

SEND_SYMBOL_CHECK='Send me symbol of stock, price of which you want to check'

INVALID_SYMBOL='<b>Invalid symbol. Please try again.</b>'

CURRENT_PRICE='Current price of <b>{symbol}</b> is <b>{price}</b>$.'
CURRENT_BALANCE='Your balance is <b>{price:.2f}</b>'

SEND_SYMBOL_BUY='Send me symbol of stock, which you want to buy'
SEND_AMOUNT_BUY='How many stocks do you want to buy? (send me a number)'
CONFIRM_BUY='<b>Price of {symbol} has changed from {old_price}$ to {new_price}$. Please confirm the purchase again.</b>'
NO_MONEY_BUY='<b>You don\'t have enough money to buy {amount} of {symbol}. Your balance is {balance:.2f}$</b>'
BUY_SUCCESSFUL='<b>You have successfully bought {amount} of {symbol} for {total_price}$.</b>'

SEND_SYMBOL_SELL='Send me a symbol of the stock, which you want to sell'
NO_STOCK_SELL='<b>You don\'t own any stocks of {symbol}. Please try again.</b>'
SEND_AMOUNT_SELL='How many stocks do you want to sell? (send me a number)'
NOT_ENOUGHT_STOCKS='<b>You don\'t have enough shares of {symbol} to sell. You have {amount} shares.</b>'
CONFIRM_SELL='<b>Price of {symbol} has changed from {old_price}$ to {new_price}$. Please confirm the sell again.</b>'
SELL_SUCCESSFUL='<b>Successfully sold {amount} shares of {symbol} at {price}$.</b>'

NO_STOCKS='You don\'t have any stocks yet'

ANY_ERROR='An error occured, try again later'
SERVER_ERROR_PRICE='Error fetching stock price. Please try again later.'
INVALID_AMOUNT='Amount must be a positive integer. Please try again.'