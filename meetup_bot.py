import shelve
import logging
from textwrap import dedent
from datetime import datetime
from environs import Env
from telegram import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    LabeledPrice
)
from telegram.ext import Filters, Updater
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler, PreCheckoutQueryHandler


logger = logging.getLogger(__name__)


def start(update, context):

    chat_id = update.message.chat_id
    context.user_data['chat_id'] = chat_id

    update.message.reply_text(
        text='Добро пожаловать на Python Meetup'
        )

    return 'START'


def start_payment_callback(update, context):

    query = update.callback_query
    chat_id = query.message.chat_id

    if query.data == 'Оплатить':

        payment_provider_token = context.bot_data['payment_provider_token']

        title = 'Payment Example'
        description = 'Оплата заказа пиццы'
        payload = 'Custom-Payload'
        currency = "RUB"

        price = context.user_data['total']
        # price * 100 so as to include 2 decimal points
        prices = [LabeledPrice("Test", price * 100)]

        # optionally pass need_name=True, need_phone_number=True,
        # need_email=True, need_shipping_address=True, is_flexible=True
        context.bot.send_invoice(
            chat_id, title, description, payload, payment_provider_token, currency, prices
        )

    else:
        text = dedent(
            '''
            Спасибо, что выбрали нашу компанию.

            До новых встреч!
            '''
        )
        reply_markup = ReplyKeyboardRemove()

        context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup
        )

        return 'START'


def precheckout_callback(update, context):
    query = update.pre_checkout_query
    if query.invoice_payload != 'Custom-Payload':
        query.answer(ok=False, error_message="Что-то пошло не так...")
    else:
        query.answer(ok=True)


def successful_payment_callback(update, context):

    update.message.reply_text("Спасибо за оплату!")


def cancel(update, context):
    if update.message:
        chat_id = update.message.chat_id
    elif update.callback_query:
        chat_id = update.callback_query.message.chat_id

    text = dedent(
        '''
        Спасибо, что выбрали наше мероприятие.

        До новых встреч!
        '''
    )
    reply_markup = ReplyKeyboardRemove()

    context.bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup
    )


def handle_users_reply(update, context):
    if update.message:
        user_reply = update.message.text
        chat_id = update.message.chat_id
    elif update.callback_query:
        user_reply = update.callback_query.data
        chat_id = update.callback_query.message.chat_id
    else:
        return
    if user_reply == '/start':
        user_state = 'START'
    elif user_reply == '/cancel':
        user_state = 'CANCEL'

    else:
        with shelve.open('state') as db:
            user_state = db[str(chat_id)]

    states_functions = {
        'START': start,
        'CANCEL': cancel,
        'START_PAYMENT': start_payment_callback
    }
    state_handler = states_functions[user_state]

    try:
        next_state = state_handler(update, context)
        with shelve.open('state') as db:
            db[str(chat_id)] = next_state
    except Exception as err:
        print(err)
        logger.error(err)


if __name__ == '__main__':

    env = Env()
    env.read_env()

    logger.setLevel(logging.INFO)
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    logger.info('Запущен meetup-bot')

    token = env.str('BOT_TOKEN')
    is_production = env.bool('PRODUCTION', False)
    updater = Updater(token=token, use_context=True)
    dispatcher = updater.dispatcher


    dispatcher.add_handler(MessageHandler(Filters.successful_payment, successful_payment_callback))
    dispatcher.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    dispatcher.add_handler(CallbackQueryHandler(handle_users_reply, pass_job_queue=True))
    dispatcher.add_handler(MessageHandler(Filters.text, handle_users_reply))
    dispatcher.add_handler(MessageHandler(Filters.location, handle_users_reply))
    dispatcher.add_handler(CommandHandler('start', handle_users_reply))


    if is_production:
        updater.start_webhook(
            listen='127.0.0.1',
            port=5000,
            url_path=token,
            webhook_url=f'https://kruser.site/{token}',
        )
    else:
        updater.start_polling()

    updater.idle()
