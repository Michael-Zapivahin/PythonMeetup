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

env = Env()
env.read_env()


API_TOKEN = env.str('BOT_TOKEN')
state_storage = StateMemoryStorage()
bot = TeleBot(API_TOKEN, state_storage=state_storage)

admin_ids = env.list('ADMIN_IDS', default=[], subcast=int)

class NewEventStates(StatesGroup):
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
            if event.active:
                text = '✅ ' + text
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
    bot.delete_message(call.from_user.id, call.message.id)


@bot.callback_query_handler(func=lambda call: call.data == 'new_event')
def admin_request_new_event(call):
    """запрос создания нового мероприятия"""
    
    chat_id = call.from_user.id
    bot.set_state(chat_id, NewEventStates.date, chat_id)
    bot.send_message(
        chat_id=chat_id,
        text=dedent(
            '''
            Введите дату мероприятия в формате ММ.ДД.ГГГГ
            (возможны варианты: "завтра", "в пятницу", "через неделю")
            
            '''
            )
    )


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
    bot.answer_callback_query(call.id, 'Мероприятие успешно создано')    
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
            InlineKeyboardButton('Изменить расписание', callback_data=f'show_schedule_{event_id}'),
            InlineKeyboardButton('Контроль выступлений', callback_data=f'control_schedule_{event_id}'),
            InlineKeyboardButton('Отправка уведомления об изменениях', callback_data=f'send_schedule_{event_id}'),
            InlineKeyboardButton('Массовая рассылка сообщений', callback_data=f'send_message_{event_id}'),
            InlineKeyboardButton('Донаты на мероприятии', callback_data=f'donates_event_{event_id}'),
            InlineKeyboardButton('Удалить мероприятие', callback_data=f'delete_event_{event_id}'),
            InlineKeyboardButton('Назад', callback_data='admin'),
        )
    
    return keyboard


@bot.callback_query_handler(func=lambda call: call.data.startswith('event_'))
def admin_event_menu(call):
    chat_id = call.from_user.id
    event_id = call.data.split('_')[-1]
    event = db.get_event(event_id)
    active = '✅ Текущее' if event.active else 'Архивное'
    
    text = dedent(
        f'''
        Мероприятие: {hcode(event.topic)}
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
            Мероприятие: {hcode(event.topic)}
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
            {hcode(event.topic)}
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
        Редактор расписания: {hcode(event.topic)}       
        
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
                InlineKeyboardButton('Изменить начало',callback_data=f'edit_speech_start_{speech.id}'),
                InlineKeyboardButton('Изменить окончание',callback_data=f'edit_speech_end_{speech.id}') 
            ],
            [
                InlineKeyboardButton('Изменить спикера',callback_data=f'edit_speech_speaker_{speech.id}'),
                InlineKeyboardButton('Изменить тему',callback_data=f'edit_speech_topic_{speech.id}') 
            ],
            [InlineKeyboardButton('Назад',callback_data=f'show_schedule_{speech.event.id}'),],
            [InlineKeyboardButton('Удалить',callback_data=f'delete_speech_{speech.id}'),],
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
        

bot.add_custom_filter(custom_filters.StateFilter(bot))

bot.infinity_polling()