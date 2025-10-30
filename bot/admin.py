import logging

import aiosqlite

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from .handlers import delete_unwanted
from config.config import ADMIN_IDS, IGNORE_SENDER
from .keyboards import Keyboards
from config.callbacks import CHECK_USER_CB, SHOW_ALL_CB, BROADCAST_CB, DELETE_USER_CB
from helpers import get_full_user_report, send_message
from config.strings import DEFAULT_HELLO

admin_router = Router()

class AdminStates(StatesGroup):
    waiting_user_id_check = State()
    waiting_text_broadcast = State()
    waiting_user_id_delete = State()
    confirmation_user_delete = State()


# Define /cancel command handler and "cancel" text handler to cancel any ongoing state if callback button fails
@admin_router.message(Command("cancel"))
@admin_router.message(F.text.casefold() == "cancel")
async def cancel_handler(message: Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state is None:
        await delete_unwanted(message)
        return

    logging.info("Cancelling state %r", current_state)
    await state.clear()

    text = DEFAULT_HELLO.format(name=message.from_user.full_name)
    await message.answer(
        "Cancelled.\n" + text,
        reply_markup=Keyboards.default_keyboard(),
        parse_mode='HTML',
    )

@admin_router.message(Command('admin'), F.from_user.id.in_(ADMIN_IDS))
async def admin_init(message: Message):
    await message.answer('Select action you want to do:', reply_markup=Keyboards.admin_keyboard())


@admin_router.callback_query(F.data==SHOW_ALL_CB, F.from_user.id.in_(ADMIN_IDS))
async def show_all_users(callback: CallbackQuery, db: aiosqlite.Connection):
    try:
        async with db.execute('SELECT * FROM users') as query:
            users_list = await query.fetchall()

        if users_list is None:
            await callback.message.answer('You don\'t have any users yet', reply_markup=Keyboards.admin_keyboard())

        formatted_message = [f'Found {len(users_list)} users:\n']

        for user_id, cash, created, username in users_list:
            formatted_message.append(f'User_id: <code>{user_id}</code>, Username: @{username}, Balance: <code>{cash:.2f}</code>, created: <code>{created}</code>')
            formatted_message.append(f'--------------')

        await callback.message.answer('\n'.join(formatted_message), reply_markup=Keyboards.admin_keyboard(), parse_mode='HTML')
    except Exception as e:
        logging.error(f'Error in show_all_users: {e}')
        await callback.message.answer(f'Could not get users', reply_markup=Keyboards.admin_keyboard())
    finally:
        await callback.answer()



@admin_router.callback_query(F.data==CHECK_USER_CB, F.from_user.id.in_(ADMIN_IDS))
async def check_user_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_user_id_check)
    await callback.message.answer('Type user id or username of user you want to check')
    await callback.answer()
    

@admin_router.message(AdminStates.waiting_user_id_check, F.from_user.id.in_(ADMIN_IDS))
async def get_user_info(message: Message, state: FSMContext, db: aiosqlite.Connection):
    user_id = None
    username = None

    try:
        user_id = int(message.text)
    except ValueError:
        username = message.text

        if username[0] == '@':
            username = username[1:]
    
    report = await get_full_user_report(db=db, user_id=user_id, username=username)
    
    if not report:
        await message.answer(f"User with ID or Username <code>{user_id if user_id else username}</code> not found.",
                             reply_markup=Keyboards.admin_keyboard(),
                             parse_mode="HTML"
        )
        await state.clear()
        return
    
    main_info = report['user_info']
    
    response = [f"All information about user <code>{user_id if user_id else username}</code>:\n",
                f"ID: {main_info['id']}\nCurrent balance: {main_info['cash']}\nCreated: {main_info['created']}\n",
                'User\'s portfolio:']

    if not report['savings']:
        response.append('User doesn\'t have any stocks\n')
    else:
        for stock, quantity in report['savings']:
            response.append(f'  • {stock}: {quantity} pcs')
            
    response.append('\nUser\'s history(Last 5 transactions):')
    if not report['history']:
        response.append('User didn\'t make any transactions yet')
        await state.clear()
        await message.answer('\n'.join(response), reply_markup=Keyboards.admin_keyboard(), parse_mode='HTML')
        return
    else:
        for transaction_id, stock, price, quantity, time in report['history'][-5:]:
            action = 'Bought' if quantity > 0 else 'Sold'
            response.append(f'  • Transaction id: {transaction_id}. {action} {stock}: {abs(quantity)} pcs. Price for 1: {price}. Time: {time}')
            
    await state.clear()
    await message.answer(text='\n'.join(response), reply_markup=Keyboards.admin_keyboard(), parse_mode='HTML')
    
    
@admin_router.callback_query(F.data==BROADCAST_CB, F.from_user.id.in_(ADMIN_IDS))
async def broadcast_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_text_broadcast)
    await callback.message.answer('Type text you want to send all users')
    await callback.answer()
    

@admin_router.message(AdminStates.waiting_text_broadcast, F.from_user.id.in_(ADMIN_IDS))
#TODO: ignore_sender arg
async def broadcast_send(message: Message, db: aiosqlite.Connection, state: FSMContext, bot: Bot, ignore_sender = IGNORE_SENDER):
    try:
        if ignore_sender:
            async with db.execute('SELECT id FROM users WHERE id != ?', (message.from_user.id,)) as query:
                user_ids = await query.fetchall()
        else:
            async with db.execute('SELECT id FROM users') as query:
                user_ids = await query.fetchall()
    except Exception as e:
        logging.error(f'Error in broadcast_send: {e}')
        await message.answer(f'Could not get users from database', reply_markup=Keyboards.admin_keyboard())
    
    if not user_ids:
        await state.clear()
        await message.answer('No users found, can\'t be completed', reply_markup=Keyboards.admin_keyboard())
        return
    
    count = 0
    
    for (user_id,) in user_ids:
        if await send_message(bot=bot, user_id=user_id, text=message.text):
            count += 1
    
    await state.clear()
    await message.answer(f'Message:\n <code>{message.text}</code>\n\n was sent {count} users!',
                         reply_markup=Keyboards.admin_keyboard(),
                         parse_mode='HTML'
    )
    

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
    await state.set_state(AdminStates.confirmation_user_delete)
    await message.answer(f'Confirm your action to delete user {user_id[0]} with \"yes\" if you want to delete or type anything else if you want to cancel')
    

@admin_router.message(AdminStates.confirmation_user_delete, F.from_user.id.in_(ADMIN_IDS))
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
        
        await message.answer(f'✅ Successfully deleted all data for user {data['id']}',
                             reply_markup=Keyboards.admin_keyboard()
        )

    except Exception as e:
        logging.error(f"Failed to delete user {data['id']}: {e}")
        await db.rollback()
        await message.answer(f"Error during deletion: {e}\nAll changes have been rolled back.",
                             reply_markup=Keyboards.admin_keyboard()
        )

    finally:
        await state.clear()
    