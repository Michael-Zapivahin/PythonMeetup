from environs import Env
from textwrap import dedent


from telebot import TeleBot, custom_filters
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from telebot.storage import StateMemoryStorage
from telebot.types import LabeledPrice

import meetup.db_operations as db
from meetup.models import Donation, Event

from django.shortcuts import get_object_or_404
from django.http import Http404

env = Env()
env.read_env()
API_TOKEN = env.str('BOT_TOKEN')
PAYMENTS_TOKEN = env.str('PAYMENTS_TOKEN')

state_storage = StateMemoryStorage()
bot = TeleBot(API_TOKEN, state_storage=state_storage)
admin_ids = env.list('ADMIN_IDS', default=[], subcast=int)

guest_data = {}
payment_data = {}


@bot.message_handler(commands=['help', 'start'])
def send_welcome(message):
    guest = db.get_guest(message.chat.id)
    keyboard = []
    if guest:
        keyboard.append([InlineKeyboardButton('Переход в меню', callback_data='guest_menu')])
    else:
        keyboard.append([InlineKeyboardButton('Зарегистрироваться', callback_data='register')])
        keyboard.append([InlineKeyboardButton('Переход в меню  без регистрации', callback_data='guest_menu')])

    start_keyboard = InlineKeyboardMarkup(keyboard=keyboard)

    active_event_name = 'Чат-боты: ожидание и реальность'  # TODO: запрос из БД
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


@bot.callback_query_handler(func=lambda call: call.data == 'register')
def guest_registration(call):
    guest_data = {}
    chat_id = call.from_user.id
    bot.set_state(chat_id, state='guest_phone')
    bot.send_message(chat_id, 'Введите ваше имя и фамилию. ')


@bot.message_handler(state='guest_phone')
def guest_registration(message):
    guest_data['name'] = message.text
    chat_id = message.chat.id
    bot.set_state(chat_id, state='guest_kind')
    bot.send_message(chat_id, 'Введите ваш телефон. ')


@bot.message_handler(state='guest_kind')
def guest_registration(message):
    guest_data['phone'] = message.text
    chat_id = message.chat.id
    bot.set_state(chat_id, state='guest_projects')
    bot.send_message(chat_id, 'Введите ваш вид деятельности. ')


@bot.message_handler(state='guest_projects')
def guest_registration(message):
    guest_data['kind'] = message.text
    chat_id = message.chat.id
    bot.set_state(chat_id, state='guest_public')
    bot.send_message(chat_id, 'Введите ваши текущие проекты. ')


@bot.message_handler(state='guest_public')
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
        text='Вы готовы к обмену данными?.',
        reply_markup=keyboard
    ),


@bot.callback_query_handler(func=lambda call: call.data.startswith('create_guest'))
def guest_registration(call):
    telegram_id = call.from_user.id
    if call.data == 'create_guest_yes':
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
        text=dedent(
            f'''
            Проверьте ваши данные, и нажмите Да чтобы продолжить: 
            \nИмя, Фамилия - {guest_data.get('name')}
            \nТелефон - {guest_data.get('phone')}
            \nВид деятельности - {guest_data.get('kind')}
            \nПроекты - {guest_data.get('projects')}
            \nОткрыт к общению - {"Да" if guest_data.get('public') else "Нет"}
            '''),
        reply_markup=keyboard
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('db_create_guest'))
def guest_registration(call):
    telegram_id = call.from_user.id
    db.create_guest(
        guest_data['name'],
        guest_data['phone'],
        guest_data['kind'],
        guest_data['projects'],
        guest_data['public'],
        call.from_user.id
    )
    keyboard = get_keyboard(
        [
            ('ОК', 'guest_menu'),
        ]
    )
    bot.send_message(
        chat_id=telegram_id,
        text=dedent(
            f'''Регистрация прошла успешно'''
        ),
        reply_markup=keyboard
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('guest_menu'))
def guest_menu(call):
    telegram_id = call.from_user.id
    keyboard = get_keyboard(
        [
            ('1. Узнать информацию о мероприятии', 'event'),
            ('2. Расписание выступления спикеров', 'schedule'),
            ('3. Получить информацию о следующих мероприятиях.', 'next_event'),
            ('4. Донат', 'donat'),
            ('5. Задать вопрос выступающему спикеру', 'question'),
            ('6. Найти новые деловые контакты', 'find_contacts'),

        ]
    )
    bot.send_message(
        chat_id=telegram_id,
        text=dedent(
            f'''
            Главное меню
            '''),
        reply_markup=keyboard
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('event'))
def guest_menu(call):
    event = get_active_event()
    telegram_id = call.from_user.id
    keyboard = get_keyboard(
        [
            ('Назад', 'guest_menu'),
        ]
    )
    if event:
        event_about = event.topic
    else:
        event_about = 'Сегодня встреч нет.'

    bot.send_message(  # TODO: Брать информацию из базы
        chat_id=telegram_id,
        text=dedent(
            f'''
            Информация о мероприятии {event_about}
            '''),
        reply_markup=keyboard
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('schedule'))
def guest_menu(call):
    event = get_active_event()
    schedules_info = ''
    if event:
        for schedule in event.schedules.all():
            schedules_info += f'''
                        Тема: {schedule.topic}
                        \n  Спикер: {schedule.speaker}  активное {schedule.active}
                        \n Время начала {schedule.start_at}  Время окончания {schedule.end_at}
            '''
    else:
        schedules_info = 'На сегодня докладов нет'

    telegram_id = call.from_user.id
    keyboard = get_keyboard(
        [
            ('Назад', 'guest_menu'),
        ]
    )
    bot.send_message(
        chat_id=telegram_id,
        text=dedent(
            f'''
            Расписание: \n {schedules_info}
            '''),
        reply_markup=keyboard
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('next_event'))
def guest_menu(call):
    events = db.get_all_events()
    events_about = ''
    for event in events:
        events_about += f'Дата {event.date}, Тема {event.topic} \n'

    telegram_id = call.from_user.id
    keyboard = get_keyboard(
        [
            ('Назад', 'guest_menu'),
        ]
    )
    bot.send_message(  # TODO: Брать информацию из базы
        chat_id=telegram_id,
        text=dedent(
            f'''
            Информацию о следующих мероприятиях {events_about}
            '''),
        reply_markup=keyboard
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('donat'))
def guest_menu(call):
    telegram_id = call.from_user.id
    keyboard = get_keyboard(
        [
            # ('100', 'make_donate'),
            # ('500', 'make_donate'),
            # ('1000', 'make_donate'),
            ('Любая сумма', 'make_donate'),
            ('Назад', 'guest_menu'),
        ]
    )
    bot.send_message(  # TODO: подключить оплату
        chat_id=telegram_id,
        text=dedent(
            f'''
            Укажите сумму доната
            '''),
        reply_markup=keyboard
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('question'))
def guest_menu(call):
    chat_id = call.from_user.id
    schedule = db.get_active_schedule()
    if schedule:
        speaker = schedule.speaker
        bot.set_state(chat_id, state=f'make_question')
        speaker_text = f'Введите вопрос для докладчика {speaker}'
    else:
        bot.set_state(chat_id, state='guest_menu')
        speaker_text = 'Нет активных докладчиков'

    bot.send_message(chat_id, speaker_text)


@bot.message_handler(state='make_question')
def make_question(message):
    chat_id = message.chat.id
    question = message.text
    guest = db.get_guest(chat_id)
    schedule = db.get_active_schedule()

    db.create_question(question, schedule, guest)
    # bot.set_state(chat_id, state='guest_menu')
    keyboard = get_keyboard(
        [
            ('Назад', 'guest_menu'),
        ]
    )
    bot.send_message(chat_id, 'Ваш вопрос успешно отправлен.', reply_markup=keyboard)


@bot.callback_query_handler(func=lambda call: call.data.startswith('find_contacts'))
def guest_menu(call):
    telegram_id = call.from_user.id
    keyboard = get_keyboard(
        [
            ('Назад', 'guest_menu'),
        ]
    )
    bot.send_message(  # TODO: настроить вывод контактов из БД
        chat_id=telegram_id,
        text=dedent(
            f'''
            КУонтакты:
            \n1. ...
            \n2. ...
            \n3. ...
            '''),
        reply_markup=keyboard
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
    save_payment(payment_data['amount'], db.get_active_schedule(), db.get_guest(message.chat.id))
    bot.send_message(message.chat.id,
                     'Срасибо за платеж! Мы будем рады видеть вас на наших мероприятих! '.format(
                         message.successful_payment.total_amount / 100, message.successful_payment.currency),
                     parse_mode='Markdown')


# end payment block

def get_keyboard(keys):
    buttons = []
    for key in keys:
        buttons.append([InlineKeyboardButton(key[0], callback_data=key[1])])
    return InlineKeyboardMarkup(keyboard=buttons)


def save_payment(amount, schedule, guest):
    Donation.object.create(amount=amount, schedule=schedule, guest=guest)


def get_active_event():
    try:
        return get_object_or_404(Event, active=True)
    except Http404:
        return None


bot.add_custom_filter(custom_filters.StateFilter(bot))

bot.infinity_polling()