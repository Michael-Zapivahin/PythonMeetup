from environs import Env
from textwrap import dedent
from dateparser import parse
from datetime import datetime

from telebot import TeleBot, custom_filters
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from telebot.handler_backends import State, StatesGroup
from telebot.storage import StateMemoryStorage
from telebot.formatting import hbold, hcode

import meetup.db_operations as db
from telebot.types import LabeledPrice
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


class EventEditStates(StatesGroup):
    date = State()
    name = State()


class SpeechEditStates(StatesGroup):
    speech_edit = State()
    speech_edit_speaker_id = State()
    speech_edit_speaker_name = State()


class AdminCallBackData(object):
    def __init__(self, call, data):
        self.message = call.message  # либо call.message
        self.data = data
        self.from_user = call.from_user


@bot.message_handler(commands=['help', 'start'])
def send_welcome(message):
    start_keyboard = InlineKeyboardMarkup(
        keyboard=[
            [InlineKeyboardButton('Присоединиться', callback_data='guest_menu')],
            [InlineKeyboardButton('Я - администратор', callback_data='admin')],
        ]
    )

    active_event = db.get_active_event()

    if active_event:
        db.add_guest_to_event(message.chat.id, active_event)
        text = dedent(
            f'''
            Привествую тебя в Python Meetup!

            Сегодня: {active_event.date}
            Тема мероприятия: {active_event.topic}

            * Будь в курсе событий текущего мероприятия.
            * Следи за выступлениями спикеров.
            * Задавай вопросы прямо в чат-боте.
            * Найди новые контакты.

            '''
        )
    else:
        text = 'На сегодня активных мероприятий нет'

    bot.send_message(
        chat_id=message.chat.id,
        text=text,
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
            if event.active:
                text = '✅ ' + text
            event_keyboard.add(
                InlineKeyboardButton(text, callback_data=f'event_{event.id}')
            )

        event_keyboard.add(InlineKeyboardButton('Создать новое мероприятие', callback_data='edit_event_new'))

        text = dedent(
            f'''
            Выберите мероприятие или создайте новое.

            '✅ - активное мероприятие'
            '''
        )

        bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=event_keyboard
        )
    else:
        bot.send_message(chat_id, 'Доступ только для администратора')
    bot.delete_message(call.from_user.id, call.message.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_event'))
def admin_request_edit_event(call):
    """запрос создания нового мероприятия"""
    *_, event_id = call.data.split('_')
    chat_id = call.from_user.id
    bot.set_state(chat_id, EventEditStates.date, chat_id)
    bot.add_data(chat_id, chat_id, event_id=event_id)
    bot.send_message(
        chat_id=chat_id,
        text=dedent(
            '''
            Введите дату мероприятия в формате ММ.ДД.ГГГГ
            (возможны варианты: "завтра", "в пятницу", "через неделю")

            '''
        )
    )


@bot.message_handler(state=EventEditStates.date)
def admin_request_new_event_date(message):
    """Создание нового мероприятия - Шаг.1 Получение даты"""

    bot.send_message(message.chat.id, 'Введите название мероприятия')
    bot.set_state(message.from_user.id, EventEditStates.name, message.chat.id)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        parsed_data = parse(
            message.text,
            languages=['ru', ],
            settings={'PREFER_DATES_FROM': 'future', 'DATE_ORDER': 'DMY'}
        )
        data['date'] = parsed_data.date() if parsed_data else datetime.now().date()


@bot.message_handler(state=EventEditStates.name)
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
        if data['event_id'] == 'new':
            db.create_new_event(topic=data['name'], date=data['date'])
        else:
            db.update_event(
                event_id=data['event_id'],
                topic=data['name'],
                date=data['date']
            )
    bot.answer_callback_query(call.id, 'Мероприятие сохранено')
    bot.delete_state(chat_id, chat_id)

    # Переход на меню выбора мероприятий
    admin_root(AdminCallBackData(call, 'admin'))


# меню работы с мероприятиями
def admin_keyboard(event):
    event_id = event.id

    keyboard = InlineKeyboardMarkup(row_width=1)
    if not event.active:
        keyboard.add(InlineKeyboardButton('✅ Сделать активным', callback_data=f'activate_event_{event_id}'))
    keyboard.add(
        InlineKeyboardButton(
            'Редактировать',
            callback_data=f'edit_event_{event_id}'
        ),
        InlineKeyboardButton(
            'Изменить расписание',
            callback_data=f'show_schedule_{event_id}'
        ),
        InlineKeyboardButton(
            'Контроль выступлений',
            callback_data=f'control_schedule_{event_id}'
        ),
        InlineKeyboardButton(
            'Уведомление спикеров',
            callback_data=f'notify_speakers_{event_id}'
        ),
        InlineKeyboardButton(
            'Уведомления гостей об изменениях',
            callback_data=f'notify_guests_{event_id}'
        ),
        InlineKeyboardButton(
            'Массовая рассылка сообщений',
            callback_data=f'send_common_message'
        ),
        InlineKeyboardButton(
            'Отчет по донатам на мероприятии',
            callback_data=f'donates_event_{event_id}'
        ),
        InlineKeyboardButton(
            'Удалить мероприятие',
            callback_data=f'delete_event_{event_id}'
        ),
        InlineKeyboardButton('Назад', callback_data='admin'),
    )

    return keyboard


@bot.callback_query_handler(func=lambda call: call.data.startswith('notify_speakers'))
def admin_notify_speakers(call):
    *_, event_id = call.data.split('_')
    event = db.get_event(event_id)
    ids = db.get_event_speakers_ids(event_id)
    
    text = dedent(
        f'''
        Вас привествует PythonMeetup!
        
        Напоминаем, что Вы вляетесь спикером
        на нашем мероприятии
        
        Дата: {event.date}
        Тема мероприятия:
        {event.topic}
        
        '''
    )
    keyboard = get_keyboard(
        [
            ('Перейти в мероприятие', 'guest_menu')
        ]
    )
    for id in ids:
        bot.send_message(
            chat_id=id,
            text=text,
            reply_markup=keyboard
        )
    bot.answer_callback_query('Уведомления отправлены!')


@bot.callback_query_handler(func=lambda call: call.data.startswith('event_'))
def admin_event_menu(call):
    chat_id = call.from_user.id
    event_id = call.data.split('_')[-1]
    event = db.get_event(event_id)
    active = '✅ Текущее' if event.active else 'Архивное'

    text = dedent(
        f'''
        Меню мероприятия:
        Дата: {event.date}
        Тема: {event.topic}
        ({active})
        '''
    )

    bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode='HTML',
        reply_markup=admin_keyboard(event)
    )
    bot.delete_message(call.from_user.id, call.message.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith('activate_event'))
def admin_set_active_event(call):
    event_id = call.data.split('_')[-1]
    event = db.set_active_event(event_id)
    active = '✅ Текущее' if event.active else 'Архивное'

    bot.edit_message_text(
        chat_id=call.from_user.id,
        message_id=call.message.id,
        text=dedent(
            f'''
            Меню мероприятия:
            Дата: {event.date}
            Тема: {event.topic}
            ({active})
            '''
        ),
        reply_markup=admin_keyboard(event),
        parse_mode='HTML'
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_event'))
def admin_request_delete_event(call):
    event_id = call.data.split('_')[-1]
    event = db.get_event(event_id)

    yes_no_keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton('Да', callback_data=f'confirm_delete_event_{event.id}'),
                InlineKeyboardButton('Отмена', callback_data='admin')
            ]
        ]
    )

    bot.send_message(
        chat_id=call.from_user.id,
        text=dedent(
            f'''
            Вы уверены, что хотите удалить мероприятие:
            Дата: {event.date}
            Тема: {event.topic}
            '''
        ),
        reply_markup=yes_no_keyboard,
        parse_mode='HTML'
    )
    bot.delete_message(call.from_user.id, call.message.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_delete_event'))
def admin_delete_event(call):
    db.delete_event(call.data.split('_')[-1])
    bot.answer_callback_query(call.id, 'Мероприятие успешно удалено')
    admin_root(AdminCallBackData(call, 'admin'))


def speech_keyboard(event_id, control=False):
    schedules = db.get_event_schedules(event_id)
    if control:
        active_speech = db.get_active_event_schedule(event_id)

    keyboard = InlineKeyboardMarkup()
    for speech in schedules:
        text_button = f'{speech.start_at:%H:%M}-{speech.end_at:%H:%M}'
        if speech.speaker:
            text_button += f' {speech.speaker.name}'

        if not control:
            text_button += f' "{speech.topic}"'
            callback_data = f'edit_schedule_{event_id}_{speech.id}'
        else:
            if speech == active_speech:
                text_button += ' ✅'
            callback_data = f'set_active_schedule_{event_id}_{speech.id}'

        buttons = [
            InlineKeyboardButton(
                text_button,
                callback_data=callback_data
            ),
        ]

        keyboard.add(*buttons)
    if not control:
        keyboard.add(InlineKeyboardButton('Добавить выступление', callback_data=f'edit_schedule_{event_id}_new'))
    keyboard.add(InlineKeyboardButton('Назад', callback_data=f'event_{event_id}'))

    return keyboard


@bot.callback_query_handler(func=lambda call: call.data.startswith('show_schedule'))
def admin_edit_event_schedules(call):
    chat_id = call.from_user.id
    event_id = call.data.split('_')[-1]
    event = db.get_event(event_id)

    text = dedent(
        f'''
        Редактор расписания: 
        Дата: {event.date}
        Тема: {event.topic}    

        Расписание:
        '''
    )

    bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode='HTML',
        reply_markup=speech_keyboard(event_id)
    )
    bot.delete_message(call.from_user.id, call.message.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith('control_schedule'))
def admin_control_event_schedules(call):
    chat_id = call.from_user.id
    event_id = call.data.split('_')[-1]
    event = db.get_event(event_id)
    bot.delete_message(call.from_user.id, call.message.id)

    text = dedent(
        f'''
        Контроль хода мероприятия: {hcode(event.topic)}       

        Выбирайте текущее активное выступление:
        '''
    )

    bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode='HTML',
        reply_markup=speech_keyboard(event_id, control=True)
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('set_active_schedule'))
def admin_set_active_schedule(call):
    chat_id = call.from_user.id
    *_, event_id, speech_id = call.data.split('_')
    event = db.get_event(event_id)
    db.set_active_schedule(speech_id)

    text = dedent(
        f'''
        Контроль хода мероприятия: {hcode(event.topic)}       

        Выбирайте текущее активное выступление:
        '''
    )

    bot.edit_message_text(
        chat_id=chat_id,
        text=text,
        message_id=call.message.id,
        parse_mode='HTML',
        reply_markup=speech_keyboard(event_id, control=True)
    )


def speech_edit_keyboard(speech):
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton('Изменить начало', callback_data=f'edit_speech_start_{speech.id}'),
                InlineKeyboardButton('Изменить окончание', callback_data=f'edit_speech_end_{speech.id}')
            ],
            [
                InlineKeyboardButton('Изменить спикера', callback_data=f'edit_speech_speaker_{speech.id}'),
                InlineKeyboardButton('Изменить тему', callback_data=f'edit_speech_topic_{speech.id}')
            ],
            [InlineKeyboardButton('Назад', callback_data=f'show_schedule_{speech.event.id}'), ],
            [InlineKeyboardButton('Удалить', callback_data=f'delete_speech_{speech.id}'), ],
        ]
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_schedule'))
def admin_edit_schedule(call):
    chat_id = call.from_user.id
    *_, event_id, speech_id = call.data.split('_')

    if speech_id == 'new':
        speech = db.create_speech(event_id)
        speech_id = speech.id

    speech = db.get_speech(speech_id)

    speaker = speech.speaker.name if speech.speaker else ''

    text = dedent(
        f'''
        Редактировать выступление:

        Время: {speech.start_at:%H:%M}-{speech.end_at:%H:%M}
        Спикер: {speaker}
        Тема: {speech.topic}
        '''
    )

    bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode='HTML',
        reply_markup=speech_edit_keyboard(speech)
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_speech'))
def admin_edit_speech(call):
    chat_id = call.from_user.id
    *_, action, speech_id = call.data.split('_')
    speech = db.get_speech(speech_id)

    if action == 'start':
        action = 'start_at'
        text = 'Введите время начала выступления (формат НН:ММ):'
        bot.set_state(chat_id, SpeechEditStates.speech_edit)

    elif action == 'end':
        action = 'end_at'
        text = 'Введите время окончания выступления (формат НН:ММ):'
        bot.set_state(chat_id, SpeechEditStates.speech_edit)

    elif action == 'speaker':
        text = 'Введите Телеграм ID спикера:'
        bot.set_state(chat_id, SpeechEditStates.speech_edit_speaker_id)

    elif action == 'topic':
        text = 'Введите тему выступления:'
        bot.set_state(chat_id, SpeechEditStates.speech_edit)

    bot.add_data(chat_id, chat_id, speech=speech, message_id=call.message.id, action=action)
    bot.send_message(chat_id=chat_id, text=text)


@bot.message_handler(
    state=[SpeechEditStates.speech_edit, SpeechEditStates.speech_edit_speaker_id]
)
def admin_speech_edit(message):
    chat_id = message.chat.id
    with bot.retrieve_data(chat_id, chat_id) as data:
        if data['action'] == 'speaker':
            data['speaker_id'] = message.text
            bot.set_state(chat_id, SpeechEditStates.speech_edit_speaker_name)
            bot.send_message(chat_id=chat_id, text='Введите ФИО спикера')

        else:
            speech = data['speech']
            update_speech_data = {
                data['action']: message.text
            }
            speech = db.update_speech(speech.id, update_speech_data)

            speaker = speech.speaker.name if speech.speaker else ''

            text = dedent(
                f'''
                Редактировать выступление:

                Время: {speech.start_at:%H:%M}-{speech.end_at:%H:%M}
                Спикер: {speaker}
                Тема: {speech.topic}
                '''
            )

            bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode='HTML',
                reply_markup=speech_edit_keyboard(speech)
            )

            bot.delete_state(chat_id, chat_id)


@bot.message_handler(state=SpeechEditStates.speech_edit_speaker_name)
def admin_speech_edit_speaker(message):
    chat_id = message.chat.id
    with bot.retrieve_data(chat_id, chat_id) as data:
        data['speaker_name'] = message.text

        speech = data['speech']
        update_speech_data = {
            'speaker_id': int(data['speaker_id']),
            'speaker_name': data['speaker_name'],
        }
        speech = db.update_speech_speaker(speech.id, update_speech_data)

        speaker = speech.speaker.name if speech.speaker else ''

        text = dedent(
            f'''
            Редактировать выступление:

            Время: {speech.start_at:%H:%M}-{speech.end_at:%H:%M}
            Спикер: {speaker}
            Тема: {speech.topic}
            '''
        )

        bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode='HTML',
            reply_markup=speech_edit_keyboard(speech)
        )

    bot.delete_state(chat_id, chat_id)


@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_speech'))
def admin_delete_speech(call):
    speech_id = call.data.split('_')[-1]
    speech = db.get_speech(speech_id)

    db.delete_speech(speech_id)
    bot.answer_callback_query(call.id, 'Выступление удалено')
    bot.delete_message(call.from_user.id, call.message.id)
    admin_edit_event_schedules(AdminCallBackData(call, f'show_schedule_{speech.event.id}'))


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
            ('О нас', 'bot_about'),
            ('1. Заполнить анкету', 'register'),
            ('2. Расписание выступления спикеров', 'schedule'),
            ('3. Получить информацию о следующих мероприятиях.', 'next_event'),
            ('4. Задать вопрос выступающему спикеру', 'question'),
            ('5. Найти новые деловые контакты', 'find_contacts'),
            ('6. Донат', 'make_donate'),

        ]
    )
    bot.send_message(
        chat_id=telegram_id,
        text=dedent(
            f'''
            Главное меню.

            Можете заполить анкету, чтобы найти единомышленников
            '''),
        reply_markup=keyboard
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('event'))
def guest_menu(call):
    event = db.get_active_event()
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
    event = db.get_active_event()
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
    keyboard = get_keyboard(
        [
            ('Назад', 'guest_menu'),
        ]
    )
    bot.send_message(chat_id, 'Ваш вопрос успешно отправлен.', reply_markup=keyboard)


@bot.callback_query_handler(func=lambda call: call.data.startswith('find_contacts'))
def guest_menu(call):
    telegram_id = call.from_user.id
    contacts_per_iteration = 1
    contacts = db.get_contacts(telegram_id)

    text = 'Контакты:'
    for contact in contacts[:5]:
        text += f'\n{contact.name}\n{contact.phone}\n{contact.kind_activity}\nПроекты: {contact.projects}\n'


    if not contacts:
        text += '\n Нет контактов'


    keyboard = get_keyboard(
        [
            ('Назад', 'guest_menu'),
        ]
    )

    bot.send_message(
        chat_id=telegram_id,
        text=text,
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
        f'{db.get_active_event()}',
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
    db.save_payment(payment_data['amount'], db.get_active_event(), db.get_guest(message.chat.id))
    bot.send_message(message.chat.id,
                     'Срасибо за платеж! Мы будем рады видеть вас на наших мероприятих! '.format(
                         message.successful_payment.total_amount / 100, message.successful_payment.currency),
                     parse_mode='Markdown')


# end payment block

@bot.callback_query_handler(func=lambda call: call.data.startswith('bot_about'))
def guest_menu(call):
    telegram_id = call.from_user.id
    keyboard = get_keyboard(
        [
            ('Назад', 'guest_menu'),
        ]
    )
    with open('about.txt', 'r') as file:
        text_about = file.read()
    bot.send_message(
        chat_id=telegram_id,
        text=dedent(text_about),
        reply_markup=keyboard
    )


def get_keyboard(keys):
    buttons = []
    for key in keys:
        buttons.append([InlineKeyboardButton(key[0], callback_data=key[1])])
    return InlineKeyboardMarkup(keyboard=buttons)


bot.add_custom_filter(custom_filters.StateFilter(bot))

bot.infinity_polling()
