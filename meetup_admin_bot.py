from environs import Env
from textwrap import dedent
from dateparser import parse
from datetime import datetime

from telebot import TeleBot, custom_filters
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from telebot.handler_backends import State, StatesGroup
from telebot.storage import StateMemoryStorage
from telebot.formatting import hbold

import meetup.db_operations as db

env = Env()
env.read_env()



API_TOKEN = env.str('BOT_TOKEN')
state_storage = StateMemoryStorage()
bot = TeleBot(API_TOKEN, state_storage=state_storage)

admin_ids = env.list('ADMIN_IDS', default=[], subcast=int)


class NewEventStates(StatesGroup):
    date = State()
    name = State()


@bot.message_handler(commands=['help', 'start'])
def send_welcome(message):
    print(message.chat.id)
    
    start_keyboard = InlineKeyboardMarkup(
        keyboard=[
            [InlineKeyboardButton('Зарегистрироваться', callback_data='register')],
            [InlineKeyboardButton('Я - администратор', callback_data='admin')]
        ]
    )

    active_event_name = 'Чат-боты: ожидание и реальность'  #запрос из БД
    bot.send_message(
        chat_id=message.chat.id, 
        text=dedent(
            f'''
            Привествую тебя в Python Meetup!
            
            Тема мероприятия:
            {active_event_name}
            
            * Будь в курсе событий текущего мероприятия.
            * Следи за выступлениями спикеров.
            * Задавай вопросы прямо в чат-боте.
            * Найди новые контакты.
            
            '''
        ),
        reply_markup=start_keyboard   
    )

# меню выбора мероприятия
@bot.callback_query_handler(func=lambda call: call.data == 'admin')
def admin_root(call):
    chat_id = call.from_user.id
    
    if chat_id in admin_ids:
        events = db.get_all_events()
        event_keyboard = InlineKeyboardMarkup(row_width=1)
        for event in events:
            text = f'{event.date:%d-%m-%Y} "{event.topic}"'
            event_keyboard.add(
                InlineKeyboardButton(text, callback_data=f'event_{event.id}')
            )
        
        event_keyboard.add(InlineKeyboardButton('Создать новое мероприятие', callback_data='new_event'))
        
        bot.send_message(
            chat_id=chat_id,
            text='Выберите мероприятие или создайте новое',
            reply_markup=event_keyboard
        )
          
    else:
        bot.send_message(chat_id, 'Доступ только для администратора')    


@bot.callback_query_handler(func=lambda call: call.data == 'new_event')
def admin_request_new_event(call):
    """запрос создания нового мероприятия"""
    
    chat_id = call.from_user.id
    bot.set_state(chat_id, NewEventStates.date, chat_id)
    bot.send_message(chat_id, 'Введите дату мероприятия')


@bot.message_handler(state=NewEventStates.date)
def admin_request_new_event_date(message):
    """Создание нового мероприятия - Шаг.1 Получение даты"""
    
    bot.send_message(message.chat.id, 'Введите название мероприятия')
    bot.set_state(message.from_user.id, NewEventStates.name, message.chat.id)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        parsed_data = parse(
            message.text,
            languages=['ru',],
            settings={'PREFER_DATES_FROM': 'future', 'DATE_ORDER': 'DMY'}
        )
        data['date'] = parsed_data.date() if parsed_data else datetime.now().date()

@bot.message_handler(state=NewEventStates.name)
def admin_request_new_event_name(message):
    """Создание нового мероприятия - Шаг.2 Получение наименования"""

    keyboard = InlineKeyboardMarkup(
        keyboard=[
            [
                InlineKeyboardButton('Создать', callback_data='create_event'),
                InlineKeyboardButton('Отмена', callback_data='admin')
            ]
        ]
    )
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['name'] = message.text
        bot.send_message(
            chat_id=message.chat.id,
            text=dedent(
                f'''
                Подтвердите введенные данные:
                
                Название: {data["name"]}
                Дата: {data["date"]}
                
                '''
            ),
            reply_markup=keyboard
        )
    
    # 


@bot.callback_query_handler(func=lambda call: call.data == 'create_event')
def admin_create_new_event(call):
    """Создание нового мероприятия"""    
    chat_id = call.from_user.id
    with bot.retrieve_data(chat_id, chat_id) as data:
        # Запись мероприятия в базу данных
        db.create_new_event(topic=data['name'], date=data['date'])
        
    bot.delete_state(chat_id, chat_id)
    
    # Переход на меню выбора мероприятий
    class AdminRoot(object):
        def __init__(self):
            self.message = call.message  # либо call.message
            self.data = 'admin'
            self.from_user = call.from_user
    admin_root(AdminRoot())


# меню работы с мероприятиями

def admin_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton('Изменить расписание', callback_data='edit_schedule')],
            [InlineKeyboardButton('Контроль выступлений', callback_data='control_schedule')],
            [InlineKeyboardButton('Отправка уведомления об изменениях', callback_data='send_schedule')],
            [InlineKeyboardButton('Массовая рассылка сообщений', callback_data='send_message')],
            [InlineKeyboardButton('Донаты на мероприятии', callback_data='donates_event')],
            [InlineKeyboardButton('Удалить мероприятие', callback_data='delete_event')],
        ]
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('event_'))
def admin_event_menu(call):
    chat_id = call.from_user.id
    event = db.get_event_by_id(call.data.split('_')[-1])
    
    text = dedent(
        f'''
        Текущее мероприятие:
        
        {hbold(event.topic)}
        
        '''
    )
    
    bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode='HTML',
        reply_markup=admin_keyboard()
    )


bot.add_custom_filter(custom_filters.StateFilter(bot))

bot.infinity_polling()