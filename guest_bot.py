from environs import Env
from textwrap import dedent
from dateparser import parse
from datetime import datetime

from telebot import TeleBot, custom_filters, ext
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from telebot.handler_backends import State, StatesGroup
from telebot.storage import StateMemoryStorage
from telebot.formatting import hbold
from telebot.types import LabeledPrice

import meetup.db_operations as db


env = Env()
env.read_env()


API_TOKEN = env.str('BOT_TOKEN')

PAYMENTS_TOKEN = env.str('PAYMENTS_TOKEN')

state_storage = StateMemoryStorage()
bot = TeleBot(API_TOKEN, state_storage=state_storage)

admin_ids = env.list('ADMIN_IDS', default=[], subcast=int)

guest_data = {}
payment_data = {}


class NewEventStates(StatesGroup):
    date = State()
    name = State()
    guest_name = State()
    guest_phone = State()
    guest_email = State()
    guest_kind = State()
    guest_projects = State()
    guest_public = State()


@bot.message_handler(commands=['help', 'start'])
def send_welcome(message):
    print(message.chat.id)
    
    start_keyboard = InlineKeyboardMarkup(
        keyboard=[
            [InlineKeyboardButton('Зарегистрироваться', callback_data='register')],
            [InlineKeyboardButton('Я - администратор', callback_data='admin')],
            [InlineKeyboardButton('Donate', callback_data='make_donate')]
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






@bot.callback_query_handler(func=lambda call: call.data == 'register')
def guest_registration(call):
    guest_data = {}
    chat_id = call.from_user.id
    bot.set_state(chat_id, state=NewEventStates.guest_phone)
    bot.send_message(chat_id, 'Введите ваше имя и фамилию. ')


@bot.message_handler(state=NewEventStates.guest_phone)
def guest_registration(message):
    guest_data['name'] = message.text
    chat_id = message.chat.id
    bot.set_state(chat_id, state=NewEventStates.guest_email)
    bot.send_message(chat_id, 'Введите ваш телефон. ')


@bot.message_handler(state=NewEventStates.guest_email)
def guest_registration(message):
    guest_data['phone'] = message.text
    chat_id = message.chat.id
    bot.set_state(chat_id, state=NewEventStates.guest_kind)
    bot.send_message(chat_id, 'Введите ваш e-mail. ')


@bot.message_handler(state=NewEventStates.guest_kind)
def guest_registration(message):
    guest_data['email'] = message.text
    chat_id = message.chat.id
    bot.set_state(chat_id, state=NewEventStates.guest_projects)
    bot.send_message(chat_id, 'Введите ваш вид деятельности. ')


@bot.message_handler(state=NewEventStates.guest_projects)
def guest_registration(message):
    guest_data['kind'] = message.text
    chat_id = message.chat.id
    bot.set_state(chat_id, state=NewEventStates.guest_public)
    bot.send_message(chat_id, 'Введите ваши текущие проекты. ')


@bot.message_handler(state=NewEventStates.guest_public)
def guest_registration(message):
    guest_data['projects'] = message.text
    keyboard = get_keyboard(
       [
            ('Да', 'create_guest_yes'),
            ('Нет', 'create_guest_no')
        ]
    )
    bot.send_message(
        chat_id=message.chat.id,
        text= 'Вы готовы к обмену данными?.',
        reply_markup=keyboard
    ),


@bot.callback_query_handler(func=lambda call: call.data.startswith('create_guest'))
def guest_registration(call):
    telegram_id = call.from_user.id
    if call == 'create_guest_yes':
        guest_data['public'] = True
    else:
        guest_data['public'] = False

    keyboard = get_keyboard(
       [
            ('Да', 'db_create_guest'),
            ('Нет', 'register')
        ]
    )
    bot.send_message(
        chat_id=telegram_id,
        text=f'Проверьте ваши данные, и нажмите Да чтобы продолжть.. {guest_data}',
        reply_markup=keyboard
    ),


@bot.callback_query_handler(func=lambda call: call.data.startswith('db_create_guest'))
def guest_registration(call):
    db.create_guest(
        guest_data['name'],
        guest_data['phone'],
        guest_data['email'],
        guest_data['kind'],
        guest_data['projects'],
        guest_data['public'],
        call.from_user.id
    )





# start payment block
@bot.callback_query_handler(func=lambda call: call.data == 'make_donate')
def donat_payment(call):
    payment_data = {}
    chat_id = call.from_user.id
    bot.set_state(chat_id, state='make_payment')
    bot.send_message(chat_id, 'Введите сумму. ')


@bot.message_handler(state='make_payment')
def donat_payment(message):
    payment_data['amount'] = int(message.text)
    chat_id = message.chat.id
    # bot.set_state(chat_id, state=NewEventStates.guest_public)
    # bot.send_message(chat_id, 'Введите ваши текущие проекты. ')
    amount = payment_data['amount']
    price = []
    price.append(LabeledPrice(label=f'Пожертвование ', amount=amount * 100))
    bot.send_invoice(
        chat_id,
        'Пожертвование',
        'Пожертвование',
        'HAPPY FRIDAYS COUPON',
        PAYMENTS_TOKEN,
        'rub',
        prices=price,
        photo_url='',
        photo_height=512,
        photo_width=512,
        photo_size=512,
        is_flexible=False,
        start_parameter='service-example')


@bot.shipping_query_handler(func=lambda query: True)
def shipping(shipping_query):
    pass


@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True,
                                  error_message="Произошла ошибка при оплате, попробуйте еще раз.")


@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):

    db.set_payment(record=payment_data)
    bot.send_message(message.chat.id,
                     'Срасибо за платеж! Мы будем рады видеть вас в нашем салоне! '.format(
                         message.successful_payment.total_amount / 100, message.successful_payment.currency),
                     parse_mode='Markdown')


# end payment block








def get_keyboard(keys):
    buttons = []
    for key in keys:
        buttons.append([InlineKeyboardButton(key[0], callback_data=key[1])])
    return InlineKeyboardMarkup(keyboard=buttons)


bot.add_custom_filter(custom_filters.StateFilter(bot))

bot.infinity_polling()