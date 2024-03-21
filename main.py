from telegram.ext import Updater, CommandHandler, CallbackContext, ConversationHandler, CallbackQueryHandler
from telegram.ext import MessageHandler, Filters
from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from messages_ru import messages_ru
from messages_en import messages_en
from datetime import datetime
from telegram import Update
import requests
import psycopg2
import config
from translate import Translator
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import numpy as np
import os
from matplotlib.font_manager import FontProperties
from telegram.error import NetworkError

GET_LANGUAGE = 0
GETTING_SEX = 1
GETTING_AGE = 2
GET_CITY = 3
GETTING_MOOD = 4
translator = Translator(to_lang="ru")


# Connecting to PostgreSQL
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


def start(update: Update, context: CallbackContext) -> int:
    print('Heymood_bot is running')
    user_id = update.message.from_user.id

    if user_exists(user_id):
        lang = get_user_lang_from_database(user_id)
        if lang == 'ru':
            update.message.reply_text(messages_ru['existing_user'])
        elif lang == 'en':
            update.message.reply_text(messages_en['existing_user'])
        else:
            update.message.reply_text(messages_ru['existing_user'])
        return ConversationHandler.END

    # The user launches the bot for the first time, selecting a language, registering
    update.message.reply_text("🌐\nChoose your language for communication/Выберите язык общения",
                              reply_markup=ReplyKeyboardMarkup([
                                  [KeyboardButton('ru'), KeyboardButton('en')]
                              ], one_time_keyboard=True, resize_keyboard=True))

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

    lang = context.user_data.get('lang', 'ru')  # Russian by default

    if lang == 'ru':
        update.message.reply_text(messages_ru['start'])
    elif lang == 'en':
        update.message.reply_text(messages_en['start'])
    else:
        update.message.reply_text(messages_ru['start'])

    context.job_queue.run_once(get_sex, 1, context={'lang': lang, 'chat_id': update.message.chat_id})
    return GETTING_SEX


def get_sex(context: CallbackContext) -> None:
    lang = context.job.context.get('lang', 'ru')  # Russian by default
    chat_id = context.job.context.get('chat_id')

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
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    )


def get_age(update: Update, context: CallbackContext) -> int:
    sex = update.message.text
    context.user_data['sex'] = sex
    lang = context.user_data.get('lang', 'ru')  # Russian by default

    if lang == 'ru':
        update.message.reply_text(messages_ru['age_ask'])
    elif lang == 'en':
        update.message.reply_text(messages_en['age_ask'])
    else:
        update.message.reply_text(messages_ru['age_ask'])
    return GETTING_AGE


def save_user_info(update: Update, context: CallbackContext) -> int:
    age = update.message.text
    lang = context.user_data.get('lang','ru')  # Russian by default

    if not age.isdigit():
        if lang == 'ru':
            update.message.reply_text(messages_ru['age_ask_again'])
        elif lang == 'en':
            update.message.reply_text(messages_en['age_ask_again'])
        else:
            update.message.reply_text(messages_ru['age_ask_again'])
        return GETTING_AGE

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
    print(f'New user: {user_id}, {sex}, {age}, {lang}.')


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


def update_user_lang_in_database(user_id, lang):
    conn = connect_to_database()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users_info SET lang = %s WHERE user_id = %s
    ''', (lang, user_id))
    conn.commit()
    conn.close()


def changelang_command(update, context):
    keyboard = [
        [
            InlineKeyboardButton("Русский", callback_data='ru'),
            InlineKeyboardButton("English", callback_data='en'),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('Выбери язык/Choose language:', reply_markup=reply_markup)


def button(update, context):
    query = update.callback_query
    query.answer()

    new_lang = query.data
    update_user_lang_in_database(query.from_user.id, new_lang)
    if new_lang == 'ru':
        query.edit_message_text(text=f"Язык интерфейса изменен на {new_lang}.")
    elif new_lang == 'en':
        query.edit_message_text(text=f"Interface language has been changed to {new_lang}.")


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
        temperature = weather_data["main"].get("temp", "-")
        humidity = weather_data["main"].get("humidity", "-")
        wind_speed = weather_data["wind"].get("speed", "-")
        visibility = weather_data.get("visibility", "-")
        pressure = weather_data["main"].get("pressure", "-")
        description = weather_data["weather"][0].get("description", "-")
        if lang == 'ru':
            description_ru = translate_text_with_external_library(description)
            message = messages_ru['get_weather'].format(city_name=city_name, temperature=temperature, humidity=humidity,
                                                        wind_speed=wind_speed, visibility=visibility, pressure=pressure,
                                                        description=description_ru)
        elif lang == 'en':
            message = messages_en['get_weather'].format(city_name=city_name, temperature=temperature, humidity=humidity,
                                                        wind_speed=wind_speed, visibility=visibility, pressure=pressure,
                                                        description=description)
        else:
            message = messages_ru['get_weather'].format(city_name=city_name, temperature=temperature, humidity=humidity,
                                                        wind_speed=wind_speed, visibility=visibility, pressure=pressure,
                                                        description=description)
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
    buttons = [
        [KeyboardButton('1'), KeyboardButton('2'), KeyboardButton('3')],
        [KeyboardButton('4'), KeyboardButton('5'), KeyboardButton('6')],
        [KeyboardButton('7'), KeyboardButton('8'), KeyboardButton('9')],
        [KeyboardButton('10')]
    ]

    if lang == 'ru':
        reply_keyboard = buttons
        update.message.reply_text(
            messages_ru['select_mood'],
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
        )
    elif lang == 'en':
        reply_keyboard = buttons
        update.message.reply_text(
            messages_en['select_mood'],
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
        )
    else:
        reply_keyboard = buttons
        update.message.reply_text(
            messages_ru['select_mood'],
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
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

    context.job_queue.run_once(send_advice, 3, context={'update': update, 'mood': mood})
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
        elif 5 <= mood <= 7:
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


def translate_text_with_external_library(text):
    translated_text = translator.translate(text)
    return translated_text


def fetch_user_moods(user_id):
    conn = connect_to_database()
    cursor = conn.cursor()

    current_day = datetime.now().date()
    week_ago = current_day - timedelta(days=6)

    query = """
        SELECT date, AVG(mood) 
        FROM user_moods 
        WHERE user_id = %s AND date BETWEEN %s AND %s 
        GROUP BY date
    """

    cursor.execute(query, (user_id, week_ago, current_day))
    mood_data = cursor.fetchall()
    conn.close()
    all_dates = [current_day - timedelta(days=i) for i in range(6, -1, -1)]

    filled_mood_data = []
    for date in all_dates:
        found = False
        for mood_entry in mood_data:
            if mood_entry[0] == date:
                filled_mood_data.append(mood_entry)
                found = True
                break
        if not found:
            filled_mood_data.append((date, 0))

    return filled_mood_data


def test_plot_mood(update, context, user_id):
    mood_data = fetch_user_moods(user_id)
    lang = get_user_lang_from_database(user_id)
    dates = [entry[0] for entry in mood_data]
    moods = [entry[1] for entry in mood_data]

    plt.figure(figsize=(8, 6))
    print(f'{user_id} got his mood plot')
    plt.plot(dates, moods, color='teal', alpha=0.7, marker='o', linewidth=8, solid_capstyle='round')
    if lang == 'ru':
        update.message.reply_text('Формирую график...')
        plt.title('Динамика настроения за неделю', fontproperties=FontProperties(family="monospace", style="italic", weight="heavy", size=20))
        plt.xlabel('Дата', fontsize=14, color='darkslategrey')
        plt.ylabel('Настроение', fontsize=14, color='darkslategrey')
    elif lang == 'en':
        update.message.reply_text('Generating the plot...')
        plt.title('Weekly mood dynamics', fontdict={'fontsize': 19, 'color': 'midnightblue'})
        plt.xlabel('Date', fontsize=14, color='darkslategrey')
        plt.ylabel('Mood', fontsize=14, color='darkslategrey')
    plt.ylim(0, 10)
    plt.grid(True)
    if lang == 'ru':
        x_labels = [translate_text_with_external_library(date.strftime('%A\n%b %d')) for date in dates]
    elif lang == 'en':
        x_labels = [date.strftime('%A\n%b %d') for date in dates]
    plt.xticks(dates, x_labels, rotation=45, fontsize=13, color='black')
    plt.yticks(np.arange(0, 12, 1), ['' if tick == 11 else str(tick) for tick in range(12)], fontsize=13, color='black')
    plt.tight_layout()
    plt.subplots_adjust(top=0.9)
    plt.gca().set_facecolor('whitesmoke')

    temp_file_path = "test_plot.png"
    plt.savefig(temp_file_path)
    plt.close()
    update.message.reply_photo(photo=open(temp_file_path, 'rb'))
    if lang == 'ru':
        update.message.reply_text(messages_ru['after_plot'])
    elif lang == 'en':
        update.message.reply_text(messages_en['after_plot'])

    os.remove(temp_file_path)


def get_plot(update, context):
    user_id = str(update.message.chat_id)
    test_plot_mood(update, context, user_id)


def main() -> None:
    updater = Updater(token=config.TELEGRAM_TOKEN, use_context=True)

    dp = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start),
                      CommandHandler('weather', start_weather),
                      CommandHandler('mood', select_mood),
                      CommandHandler('mood', save_mood)],
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
    dp.add_handler(CommandHandler('changelang', changelang_command))
    dp.add_handler(CommandHandler('getplot', get_plot))
    dp.add_handler(CallbackQueryHandler(button))

    try:
        updater.start_polling()
        updater.idle()
    except NetworkError as e:
        print('Error')
        time.sleep(60)
        main()


if __name__ == '__main__':
    main()