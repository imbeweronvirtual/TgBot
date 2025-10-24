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
from helpers import get_full_user_report, send_message

admin_router = Router()

class AdminStates(StatesGroup):
    waiting_user_id_check = State()
    waiting_text_broadcast = State()
    waiting_user_id_delete = State()
    confimation_user_delete = State()


@admin_router.message(Command('admin'), F.from_user.id.in_(ADMIN_IDS))
async def admin_init(message: Message):
    await message.answer('Select action', reply_markup=Keyboards.admin_keyboard())


@admin_router.callback_query(F.data==CHECK_USER_CB, F.from_user.id.in_(ADMIN_IDS))
async def check_user_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_user_id_check)
    await callback.message.answer('Type user id of user you want to check')
    await callback.answer()
    

@admin_router.message(AdminStates.waiting_user_id_check, F.from_user.id.in_(ADMIN_IDS))
async def get_user_info(message: Message, state: FSMContext, db: aiosqlite.Connection):
    try:
        user_id = int(message.text)
    except ValueError:
        await message.answer("Invalid ID. Please send only numbers.")
        return
    
    report = await get_full_user_report(user_id=user_id, db=db)
    
    if not report:
        await message.answer(f"User with ID <code>{user_id}</code> not found.", reply_markup=Keyboards.admin_keyboard(), parse_mode="HTML")
        await state.clear()
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
    
    
@admin_router.callback_query(F.data==BROADCAST_CB, F.from_user.id.in_(ADMIN_IDS))
async def broadcast_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_text_broadcast)
    await callback.message.answer('Type text you want to send all users')
    await callback.answer()
    

@admin_router.message(AdminStates.waiting_text_broadcast, F.from_user.id.in_(ADMIN_IDS))
async def broadcast_send(message: Message, db: aiosqlite.Connection, state: FSMContext, bot: Bot):
    async with db.execute('SELECT id FROM users') as query:
        user_ids = await query.fetchall()
    
    if not user_ids:
        await state.clear()
        await message.answer('No users found, can\'t be completed', reply_markup=Keyboards.admin_keyboard())
        return
    
    count = 0
    
    for (id,) in user_ids:
        if await send_message(bot=bot, user_id=id, text=message.text):
            count += 1
    
    await state.clear()
    await message.answer(f'Message:\n <code>{message.text}</code>\n\n was sent {count} users!', reply_markup=Keyboards.admin_keyboard(), parse_mode='HTML')
    

@admin_router.callback_query(F.data==DELETE_USER_CB, F.from_user.id.in_(ADMIN_IDS))
async def delete_user_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_user_id_delete)
    await callback.message.answer('Type user id of user you want to delete')
    await callback.answer()
    

@admin_router.message(AdminStates.waiting_user_id_delete, F.from_user.id.in_(ADMIN_IDS))
async def confirm_user_delete(message: Message, state: FSMContext, db: aiosqlite.Connection):
    async with db.execute('SELECT id FROM users WHERE id = ?', (message.text,)) as query:
        user_id = await query.fetchone()
        
    if not user_id:
        await state.clear()
        await message.answer(f'User {message.text} not found', reply_markup=Keyboards.admin_keyboard())
        return
    
    await state.update_data(id=user_id[0])
    await state.set_state(AdminStates.confimation_user_delete)
    await message.answer(f'Confirm your action to delete user {user_id[0]} with \"yes\" if you want to delete or type anything else if you want to cancel')
    

@admin_router.message(AdminStates.confimation_user_delete, F.from_user.id.in_(ADMIN_IDS))
async def user_delete(message: Message, state: FSMContext, db: aiosqlite.Connection):
    if message.text.lower().strip() != 'yes':
        await message.answer('Cancelled.', reply_markup=Keyboards.admin_keyboard())
        await state.clear()
        return
    
    data = await state.get_data()
    
    
    try:
        await db.execute('BEGIN')

        await db.execute('DELETE FROM user_savings WHERE user_id = ?', (data['id'],))
        await db.execute('DELETE FROM history WHERE user_id = ?', (data['id'],))
        await db.execute('DELETE FROM users WHERE id = ?', (data['id'],))

        await db.commit()
        
        await message.answer(f'✅ Successfully deleted all data for user {data['id']}', reply_markup=Keyboards.admin_keyboard())

    except Exception as e:
        logging.error(f"Failed to delete user {data['id']}: {e}")
        await db.rollback()
        await message.answer(f"Error during deletion: {e}\nAll changes have been rolled back.", reply_markup=Keyboards.admin_keyboard())

    finally:
        await state.clear()
    