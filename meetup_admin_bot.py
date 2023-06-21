from environs import Env
from textwrap import dedent

from telebot import TeleBot, custom_filters
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from telebot.handler_backends import State, StatesGroup
from telebot.storage import StateMemoryStorage


env = Env()
env.read_env()



API_TOKEN = env.str('BOT_TOKEN')
bot = TeleBot(API_TOKEN, state_storage=StateMemoryStorage())

admin_ids = env.list('ADMIN_IDS', subcast=int)


class NewEventStates(StatesGroup):
    date = State()
    name = State()


@bot.message_handler(commands=['help', 'start'])
def send_welcome(message):

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
            f"""
            Привествую тебя в Python Meetup!
            
            Тема мероприятия:
            {active_event_name}
            
            * Будь в курсе событий текущего мероприятия.
            * Следи за выступлениями спикеров.
            * Задавай вопросы прямо в чат-боте.
            * Найди новые контакты.
            
            """
        ),
        reply_markup=start_keyboard   
    )


@bot.callback_query_handler(func=lambda call: call.data == 'admin')
def admin_root(call):
    chat_id = call.from_user.id
    
    if chat_id in admin_ids:
        events = [] # список  мероприятий
        event_keyboard = InlineKeyboardMarkup(row_width=1)
        for event in events:
            event_keyboard.add(InlineKeyboardButton(event.name, callback_data=f'event_{event.id}'))
        
        event_keyboard.add(InlineKeyboardButton('Создать новое мероприятие', callback_data='new_event'))
        
        bot.send_message(
            chat_id=chat_id,
            text='Выберите мероприятие или создайте новое',
            reply_markup=event_keyboard
        )
          
    else:
        bot.send_message(chat_id, 'Доступ только для администратора')    


@bot.callback_query_handler(func=lambda call: call.data == 'new_event')
def admin_create_new_event(call):
    """Создание нового мероприятия"""
    
    chat_id = call.from_user.id
    bot.set_state(chat_id, NewEventStates.date)
    bot.send_message(chat_id, 'Введите дату мероприятия в формате ММ.ДД.ГГГГ')


@bot.message_handler(state=NewEventStates.date)
def admin_create_new_event_date(message):
    """Создание нового мероприятия - Шаг.1 Получение даты"""
    
    bot.send_message(message.chat.id, 'Введите название мероприятия')
    bot.set_state(message.from_user.id, NewEventStates.name, message.chat.id)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['date'] = message.text


@bot.message_handler(state=NewEventStates.name)
def admin_create_new_event_name(message):
    """Создание нового мероприятия - Шаг.2 Получение наименования"""

    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['name'] = message.text
        bot.send_message(
            chat_id=message.chat.id,
            text=f'Дата: {data["date"]}\n Наименование: {data["name"]}')
    
    bot.delete_state(message.from_user.id, message.chat.id)

bot.infinity_polling()