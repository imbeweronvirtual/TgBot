from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config.callbacks import BALANCE_CB, MY_STOCKS_CB, BUY_CB, SELL_CB, PRICE_CB, RETURN_CB

class Keyboards:
    # Initialize default keyboard
    @staticmethod
    def default_keyboard():
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text='👤 Profile', callback_data=MY_STOCKS_CB), 
                ],
                [
                    InlineKeyboardButton(text='Buy stocks', callback_data=BUY_CB),
                    InlineKeyboardButton(text='Sell stocks', callback_data=SELL_CB)
                ],
                [InlineKeyboardButton(text='Check stocks price', callback_data=PRICE_CB)],
            ]
        )
    @staticmethod
    def return_keyboard():
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text='◀️ Go to the main', callback_data=RETURN_CB)]
            ]
        )