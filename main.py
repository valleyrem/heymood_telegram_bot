from datetime import datetime
from matplotlib import pyplot as plt
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler
from pytz import timezone
from telegram import ReplyKeyboardMarkup, KeyboardButton
import requests
from telegram.ext import MessageHandler, Filters
import config
import psycopg2
from bs4 import BeautifulSoup
from messages_ru import messages_ru
from messages_en import messages_en

# Подключение к базе данных PostgreSQL
def connect_to_database():
    conn = psycopg2.connect(
        dbname=config.DB_NAME,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        host=config.DB_HOST,
        port=config.DB_PORT
    )
    return conn

def help_command(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    lang = get_user_lang_from_database(user_id)
    if lang == 'ru':
        help_text = messages_ru['help']
    elif lang == 'en':
        help_text = messages_en['help']
    else:
        help_text = messages_ru['help']
    update.message.reply_text(help_text)

GET_LANGUAGE = 0
GETTING_SEX = 1
GETTING_AGE = 2
GET_CITY = 3
GETTING_MOOD = 4


def start(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id

    # Проверяем, есть ли пользователь уже в базе данных
    if user_exists(user_id):
        lang = get_user_lang_from_database(user_id)
        if lang == 'ru':
            update.message.reply_text(messages_ru['existing_user'])
        elif lang == 'en':
            update.message.reply_text(messages_en['existing_user'])
        else:
            update.message.reply_text(messages_ru['existing_user'])
        return ConversationHandler.END

    # Пользователь впервые запускает бота, выбор языка, регистрация
    update.message.reply_text("Hi. Choose your language for communication\nПривет. Выберите язык общения",
                               reply_markup=ReplyKeyboardMarkup([['ru', 'en']], one_time_keyboard=True))

    return GET_LANGUAGE


def get_language(update: Update, context: CallbackContext) -> int:
    chosen_lang = update.message.text
    context.user_data['lang'] = chosen_lang
    if chosen_lang == 'ru':
        update.message.reply_text(f"Выбранный язык: Русский")
    elif chosen_lang == 'en':
        update.message.reply_text(f"Selected language: English")
    else:
        update.message.reply_text(f"Выбранный язык: Русский")
    user_id = update.message.from_user.id
    context.user_data['user_id'] = user_id

    lang = context.user_data.get('lang', 'ru')  # Получаем выбранный язык (если не выбран, используем русский по умолчанию)
    if lang == 'ru':
        update.message.reply_text(messages_ru['start'])
    elif lang == 'en':
        update.message.reply_text(messages_en['start'])
    else:
        update.message.reply_text(messages_ru['start'])

    context.job_queue.run_once(get_sex, 1, context={'lang': lang, 'chat_id': update.message.chat_id})
    return GETTING_SEX


def get_sex(context: CallbackContext) -> None:
    lang = context.job.context.get('lang',
                                   'ru')  # Получаем выбранный язык (если не выбран, используем русский по умолчанию)
    chat_id = context.job.context.get('chat_id')  # Получаем идентификатор чата

    if lang == 'ru':
        reply_keyboard = [
            ['мужской'],
            ['женский'],
            ['не хочу сообщать']
        ]
        text = messages_ru['sex_ask']
    elif lang == 'en':
        reply_keyboard = [
            ['male'],
            ['female'],
            ['prefer not to say']
        ]
        text = messages_en['sex_ask']
    else:
        reply_keyboard = [
            ['мужской'],
            ['женский'],
            ['не хочу сообщать']
        ]
        text = messages_ru['sex_ask']

    context.bot.send_message(
        chat_id,
        text=text,
        reply_markup=ReplyKeyboardMarkup(reply_keyboard)
    )

def get_age(update: Update, context: CallbackContext) -> int:
    sex = update.message.text
    context.user_data['sex'] = sex
    lang = context.user_data.get('lang', 'ru')  # Получаем выбранный язык (если не выбран, используем русский по умолчанию)
    if lang == 'ru':
        update.message.reply_text(messages_ru['age_ask'])
    elif lang == 'en':
        update.message.reply_text(messages_en['age_ask'])
    else:
        update.message.reply_text(messages_ru['age_ask'])
    return GETTING_AGE


def save_user_info(update: Update, context: CallbackContext) -> int:
    age = update.message.text
    lang = context.user_data.get('lang',
                                 'ru')  # Получаем выбранный язык (если не выбран, используем русский по умолчанию)

    if not age.isdigit():
        if lang == 'ru':
            update.message.reply_text(messages_ru['age_ask_again'])
        elif lang == 'en':
            update.message.reply_text(messages_en['age_ask_again'])
        else:
            update.message.reply_text(messages_ru['age_ask_again'])
        return GETTING_AGE  # Повторный запрос возраста

    age = int(age)
    user_id = context.user_data['user_id']
    sex = context.user_data['sex']

    if not user_exists(user_id):
        add_user_to_database(user_id, sex, age, lang)
    else:
        update_user_in_database(user_id, sex, age)

    if lang == 'ru':
        update.message.reply_text(messages_ru['success_save'])
    elif lang == 'en':
        update.message.reply_text(messages_en['success_save'])
    else:
        update.message.reply_text(messages_ru['success_save'])
    return ConversationHandler.END


def user_exists(user_id):
    conn = connect_to_database()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT 1 FROM users_info WHERE user_id = %s
    ''', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def add_user_to_database(user_id: int, sex: str, age: int, lang: str) -> None:
    conn = connect_to_database()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO users_info (user_id, sex, age, lang) VALUES (%s, %s, %s, %s)
    ''', (user_id, sex, age, lang))
    conn.commit()
    conn.close()

def update_user_in_database(user_id: int, sex: str, age: int) -> None:
    conn = connect_to_database()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users_info
        SET sex = %s, age = %s
        WHERE user_id = %s
    ''', (sex, age, user_id))
    conn.commit()
    conn.close()

def get_user_lang_from_database(user_id):
    conn = connect_to_database()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT lang FROM users_info WHERE user_id = %s
    ''', (user_id,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return result[0]
    else:
        return None

def me(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    conn = connect_to_database()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT sex, age, lang
        FROM users_info
        WHERE user_id = %s
    ''', (user_id,))
    result = cursor.fetchone()
    conn.close()

    if result is None:
        update.message.reply_text(messages_ru['no_saved_info'])
        return

    sex, age, lang = result
    lang = lang
    if lang == 'ru':
        update.message.reply_text(messages_ru['about_me'].format(sex=sex, age=age))
    elif lang == 'en':
        update.message.reply_text(messages_en['about_me'].format(sex=sex, age=age))
    else:
        update.message.reply_text(messages_ru['about_me'].format(sex=sex, age=age))

def start_weather(update, context):
    user_id = update.message.from_user.id
    lang = get_user_lang_from_database(user_id)
    if lang == 'ru':
        update.message.reply_text(messages_ru['start_weather'])
    elif lang == 'en':
        update.message.reply_text(messages_en['start_weather'])
    else:
        update.message.reply_text(messages_ru['start_weather'])

    return GET_CITY

def get_weather(city_name, api_key):
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city_name}&appid={api_key}&units=metric"
    response = requests.get(url)
    data = response.json()
    return data

def receive_city(update, context):
    user_id = update.message.from_user.id
    lang = get_user_lang_from_database(user_id)
    city_name = update.message.text
    api_key = config.OPEN_WEATHER_API
    weather_data = get_weather(city_name, api_key)
    if weather_data["cod"] == 200:
        temperature = weather_data["main"]["temp"]
        humidity = weather_data["main"]["humidity"]
        wind_speed = weather_data["wind"]["speed"]
        visibility = weather_data["visibility"]
        pressure = weather_data["main"]["pressure"]
        description = weather_data["weather"][0]["description"]

        if lang == 'ru':
            message = messages_ru['get_weather'].format(city_name=city_name, temperature=temperature, humidity=humidity, wind_speed=wind_speed, visibility=visibility, pressure=pressure, description=description)
        elif lang == 'en':
            message = messages_en['get_weather'].format(city_name=city_name, temperature=temperature, humidity=humidity, wind_speed=wind_speed, visibility=visibility, pressure=pressure, description=description)
        else:
            message = messages_ru['get_weather'].format(city_name=city_name, temperature=temperature, humidity=humidity, wind_speed=wind_speed, visibility=visibility, pressure=pressure, description=description)
    else:
        if lang == 'ru':
            message = messages_ru['no_weather']
        elif lang == 'en':
            message = messages_en['no_weather']
        else:
            message = messages_ru['no_weather']

    update.message.reply_text(message)
    return ConversationHandler.END

def select_mood(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    lang = get_user_lang_from_database(user_id)

    if lang == 'ru':
        reply_keyboard = [
            ['1', '2', '3', '4', '5'],
            ['6', '7', '8', '9', '10']
        ]
        update.message.reply_text(
            messages_ru['select_mood'],
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
        )
    elif lang == 'en':
        reply_keyboard = [
            ['1', '2', '3', '4', '5'],
            ['6', '7', '8', '9', '10']
        ]
        update.message.reply_text(
            messages_en['select_mood'],
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
        )
    else:
        reply_keyboard = [
            ['1', '2', '3', '4', '5'],
            ['6', '7', '8', '9', '10']
        ]
        update.message.reply_text(
            messages_ru['select_mood'],
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
        )
    return GETTING_MOOD


def save_mood(update: Update, context: CallbackContext) -> int:
    mood = int(update.message.text)
    user_id = update.message.from_user.id
    lang = get_user_lang_from_database(user_id)

    if lang == 'ru':
        update.message.reply_text(messages_ru['saved_mood'])
    elif lang == 'en':
        update.message.reply_text(messages_en['saved_mood'])
    else:
        update.message.reply_text(messages_ru['saved_mood'])

    # Запускаем функцию для отправки советов через 2 секунды
    context.job_queue.run_once(send_advice, 2, context={'update': update, 'mood': mood})
    save_mood_to_database(user_id, mood)
    return ConversationHandler.END

def send_advice(context: CallbackContext):
    update = context.job.context['update']
    mood = context.job.context['mood']
    lang = get_user_lang_from_database(update.message.from_user.id)

    if lang == 'ru':
        if 1 <= mood <= 4:
            advice_text = messages_ru['low_mood_advice']
        elif 5 <= mood <= 6:
            advice_text = messages_ru['medium_mood_advice']
        else:
            advice_text = messages_ru['high_mood_advice']
    elif lang == 'en':
        if 1 <= mood <= 4:
            advice_text = messages_en['low_mood_advice']
        elif 5 <= mood <= 6:
            advice_text = messages_en['medium_mood_advice']
        else:
            advice_text = messages_en['high_mood_advice']
    else:
        if 1 <= mood <= 4:
            advice_text = messages_ru['low_mood_advice']
        elif 5 <= mood <= 6:
            advice_text = messages_ru['medium_mood_advice']
        else:
            advice_text = messages_ru['high_mood_advice']

    update.message.reply_text(advice_text)


def save_mood_to_database(user_id: int, mood: int) -> None:
    conn = connect_to_database()
    cursor = conn.cursor()
    current_time = datetime.now()
    date = current_time.date()
    time = current_time.time()
    day_of_week = current_time.strftime('%A')
    cursor.execute('''
        INSERT INTO user_moods (user_id, mood, date, day_of_week, time) VALUES (%s, %s, %s, %s, %s)
    ''', (user_id, mood, date, day_of_week, time))
    conn.commit()
    conn.close()


def main() -> None:
    updater = Updater(token=config.TELEGRAM_TOKEN, use_context=True)

    dp = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start), CommandHandler('weather', start_weather), CommandHandler('mood', select_mood), CommandHandler('mood', save_mood)],
        states={
            GET_LANGUAGE: [MessageHandler(Filters.regex(r'^(ru|en)$'), get_language)],
            GETTING_SEX: [MessageHandler(Filters.text & ~Filters.command, get_age)],
            GETTING_AGE: [MessageHandler(Filters.text & ~Filters.command, save_user_info)],
            GET_CITY: [MessageHandler(Filters.text & ~Filters.command, receive_city)],
            GETTING_MOOD: [MessageHandler(Filters.text & ~Filters.command, save_mood)],
        },
        fallbacks=[],
    )

    dp.add_handler(conv_handler)
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler("me", me))
    dp.add_handler(CommandHandler("weather", start_weather))
    dp.add_handler(CommandHandler("mood", select_mood))
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
