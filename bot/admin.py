import asyncio
import logging

import aiosqlite
import aiohttp

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from .handlers import delete_unwanted
from config.config import ADMIN_IDS
from .keyboards import Keyboards
from config.callbacks import CHECK_USER_CB, BROADCAST_CB, DELETE_USER_CB
from helpers import get_full_user_report

admin_router = Router()

class AdminStates(StatesGroup):
    waiting_user_id_check = State()


@admin_router.message(Command('admin'))
async def admin_init(message: Message):
    if message.from_user.id in ADMIN_IDS:
        await message.answer('Select action', reply_markup=Keyboards.admin_keyboard())
    else:
        await delete_unwanted(message)
    return


@admin_router.callback_query(F.data==CHECK_USER_CB)
async def check_user_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_user_id_check)
    await callback.message.answer('Type user id of user you want to check')
    await callback.answer()
    

@admin_router.message(AdminStates.waiting_user_id_check)
async def get_user_info(message: Message, state: FSMContext, db: aiosqlite.Connection):
    try:
        user_id = int(message.text)
    except Exception:
        #TODO
        return
    
    report = await get_full_user_report(user_id=user_id, db=db)
    
    if not report:
        #TODO
        return
    
    main_info = report['user_info']
    
    response = [f"All information about user <code>{user_id}</code>:\n"]
    
    response.append(f"User_id: {main_info['id']}\nCurrent balance: {main_info['cash']}\nCreated: {main_info['created']}\n")
    
    response.append('User\'s portfolio:')
    if not report['savings']:
        response.append('User doesn\'t have any stocks\n')
    else:
        for stock, quantity in report['savings']:
            response.append(f'  • {stock}: {quantity} pcs')
            
    response.append('\nUser\'s history(Last 5 transactions):')
    if not report['history']:
        response.append('User didn\'t make any transactions yet')
        #TODO
        return
    else:
        for id, stock, price, quantity, time in report['history'][-5:]:
            action = 'Bought' if quantity > 0 else 'Sold'
            response.append(f'  • Transaction id: {id}. {action} {stock}: {abs(quantity)} pcs. Price for 1: {price}. Time: {time}')
            
    await state.clear()
    await message.answer(text='\n'.join(response), reply_markup=Keyboards.admin_keyboard(), parse_mode='HTML')
            
    