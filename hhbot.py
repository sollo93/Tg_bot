import os
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, ConversationHandler,
    MessageHandler, filters, CallbackQueryHandler
)
import logging
import asyncio

# ========== Загрузка переменных окружения ==========
load_dotenv()

# --- Telegram настройки ---
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_TOKEN')

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/117.0.0.0 Safari/537.36'
}

# --- Состояния для ConversationHandler-а
SEARCH, SET_SALARY, SET_REGION = range(3)

# --- Память пользователей
user_settings = {}

# --- Справочные данные
REGIONS = {
    'Россия': '113',
    'Москва': '1',
    'Санкт-Петербург': '2',
    'Новосибирск': '4'
    # можно добавить больше регионов по необходимости
}

def get_user(chat_id):
    if chat_id not in user_settings:
        user_settings[chat_id] = {
            'keywords': [
                'удаленная работа', 'без опыта', 'для студентов',
                'мама в декрете', 'инвалид', 'подработка'
            ],
            'salary': None,
            'region': '113',  # Россия
            'page_hh': 0,
            'page_avito': 0
        }
    return user_settings[chat_id]

async def get_hh_jobs(keywords, salary=None, region='113', page=0):
    keywords_str = ' '.join(keywords)
    params = {
        'text': keywords_str,
        'area': region,
        'per_page': 5,
        'experience': 'noExperience',
        'schedule': 'remote',
        'page': page
    }
    if salary is not None:
        params['salary'] = salary
    try:
        resp = requests.get('https://api.hh.ru/vacancies', params=params, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        await asyncio.sleep(1)
        jobs = []
        items = resp.json().get('items', [])
        for job in items:
            name = job.get('name', 'Название не указано')
            description = job.get('snippet', {}).get('requirement', '') + job.get('snippet', {}).get('responsibility', '')
            combined_text = (name + ' ' + description).lower()
            if any(kw.lower() in combined_text for kw in keywords):
                company = job.get('employer', {}).get('name', 'Компания не указана')
                url = job.get('alternate_url', '#')
                salary_s = "ЗП: не указана"
                salary_field = job.get('salary')
                if salary_field:
                    if salary_field.get('from') and salary_field.get('to'):
                        salary_s = f"ЗП: {salary_field['from']} - {salary_field['to']} {salary_field.get('currency', '')}"
                    elif salary_field.get('from'):
                        salary_s = f"ЗП: от {salary_field['from']} {salary_field.get('currency', '')}"
                    elif salary_field.get('to'):
                        salary_s = f"ЗП: до {salary_field['to']} {salary_field.get('currency', '')}"
                jobs.append(f"{name} | {company} | {salary_s} | {url}")
        return jobs
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка HH: {e}")
        return []

async def get_avito_jobs(keywords, page=0):
    query = '+'.join(keywords)
    url = f'https://www.avito.ru/all/vakansii?cd=1&q={query}&remote=1&p={page + 1}'
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        await asyncio.sleep(1)
        soup = BeautifulSoup(resp.content, 'html.parser')
        jobs = []
        ads = soup.find_all('div', {'data-marker': 'item'}, limit=5)
        for ad in ads:
            title_tag = ad.find('h3')
            if not title_tag:
                continue
            title = title_tag.text.strip()
            link_tag = ad.find('a', {'data-marker': 'item-title'})
            salary_tag = ad.find('span', {'data-marker': 'item-price'})
            link = 'https://www.avito.ru' + link_tag.get('href') if link_tag else '#'
            salary = salary_tag.text.strip() if salary_tag else 'ЗП: не указана'
            jobs.append(f"{title} | {salary} | {link}")
        return jobs
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка Avito: {e}")
        return []

# --- Команды бота ---

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/start - старт поиска\n"
        "/search - задать ключевые слова\n"
        "/salary - выбрать минимальную зарплату\n"
        "/region - выбрать регион поиска\n"
        "/next - показать следующую страницу\n"
        "/prev - показать предыдущую страницу\n"
        "/help - показать это сообщение"
    )

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = get_user(chat_id)
    user['page_hh'] = 0
    user['page_avito'] = 0
    await update.message.reply_text(
        "Поиск удалённой подработки без опыта.\n"
        f"Текущие ключевые слова: {', '.join(user['keywords'])}\n"
        "Используйте /search, чтобы изменить"
    )
    await send_jobs_now(chat_id, context)

async def search_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите ключевые слова для поиска через пробел:")
    return SEARCH

async def search_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    keywords = list(set(text.lower().split()))
    user = get_user(chat_id)
    user['keywords'] = keywords
    user['page_hh'] = 0
    user['page_avito'] = 0
    await update.message.reply_text(f"Новые ключевые слова: {', '.join(keywords)}")
    await send_jobs_now(chat_id, context)
    return ConversationHandler.END

async def salary_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите минимальную зарплату (число), либо 0 чтобы сбросить:")
    return SET_SALARY

async def salary_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    try:
        salary = int(text)
    except ValueError:
        await update.message.reply_text("Введите только число!")
        return SET_SALARY
    user = get_user(chat_id)
    user['salary'] = None if salary == 0 else salary
    user['page_hh'] = 0
    await update.message.reply_text(f"Установлена минимальная зарплата: {salary if salary > 0 else 'отсутствует'}")
    await send_jobs_now(chat_id, context)
    return ConversationHandler.END

async def region_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(region, callback_data=code)]
        for region, code in REGIONS.items()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Выберите регион:', reply_markup=reply_markup)
    return SET_REGION

async def region_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    query = update.callback_query
    await query.answer()
    region_code = query.data
    region_name = [r for r, c in REGIONS.items() if c == region_code][0]
    user = get_user(chat_id)
    user['region'] = region_code
    user['page_hh'] = 0
    await query.edit_message_text(f"Регион поиска: {region_name}")
    await send_jobs_now(chat_id, context)
    return ConversationHandler.END

async def send_jobs_now(chat_id, context):
    user = get_user(chat_id)
    msg = f"Ключевые слова: {', '.join(user['keywords'])}\nРегион: {next(r for r,c in REGIONS.items() if c == user['region'])}\n"
    if user['salary']:
        msg += f"Мин. зарплата: {user['salary']}\n"
    else:
        msg += "Мин. зарплата: любая\n"
    msg += "Результаты:\n\n"

    jobs_hh = await get_hh_jobs(user['keywords'], user['salary'], user['region'], user['page_hh'])
    jobs_avito = await get_avito_jobs(user['keywords'], user['page_avito'])

    msg += "💼 hh.ru:\n"
    msg += "\n".join([f"🔹 {j}" for j in jobs_hh]) if jobs_hh else "❌ Нет вакансий"
    msg += "\n\n🛒 Avito:\n"
    msg += "\n".join([f"🔸 {j}" for j in jobs_avito]) if jobs_avito else "❌ Нет вакансий"
    # Добавим кнопки пагинации
    keyboard = [
        [
            InlineKeyboardButton("⬅️ Назад", callback_data="prev"),
            InlineKeyboardButton("➡️ Дальше", callback_data="next"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=chat_id, text=msg, reply_markup=reply_markup, disable_web_page_preview=True)

async def pagination_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    query = update.callback_query
    await query.answer()
    user = get_user(chat_id)
    if query.data == "next":
        user['page_hh'] += 1
        user['page_avito'] += 1
    elif query.data == "prev" and user['page_hh'] > 0 and user['page_avito'] > 0:
        user['page_hh'] -= 1
        user['page_avito'] -= 1
    await send_jobs_now(chat_id, context)
    await query.delete_message()

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Операция отменена.')
    return ConversationHandler.END


if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler('start', start_command))
    app.add_handler(CommandHandler('help', help_command))

    search_handler = ConversationHandler(
        entry_points=[CommandHandler('search', search_start)],
        states={SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_receive)]},
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    app.add_handler(search_handler)

    salary_handler = ConversationHandler(
        entry_points=[CommandHandler('salary', salary_start)],
        states={SET_SALARY: [MessageHandler(filters.TEXT & ~filters.COMMAND, salary_receive)]},
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    app.add_handler(salary_handler)

    region_handler = ConversationHandler(
        entry_points=[CommandHandler('region', region_command)],
        states={SET_REGION: [CallbackQueryHandler(region_receive)]},
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    app.add_handler(region_handler)

    app.add_handler(CallbackQueryHandler(pagination_callback, pattern='next|prev'))

    logger.info("Бот запущен. Ожидает команды /start, /help, /search, /salary, /region ...")
    app.run_polling()
