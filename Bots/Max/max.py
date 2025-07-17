import asyncio
from maxgram import MaxBot, MaxDispatcher, types

# ---- Настройки ----
API_TOKEN = "ВАШ_MAX_ТОКЕН"
bot = MaxBot(token=API_TOKEN)
dp = MaxDispatcher()

# ---- Данные ----
SOCIAL_LINKS = [
    ("Instagram", "https://instagram.com/your_profile"),
    ("VK", "https://vk.com/your_profile")
]
OFFICIAL_SITE = "https://ваш-сайт.ру"

# --- Простое хранение записей пользователей
user_appointments = {}

# ---- Клавиатуры ----

from maxgram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def main_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Запись на приём")],
            [KeyboardButton(text="🌐 Оф. сайт"), KeyboardButton(text="🔖 Мои записи")],
            [KeyboardButton(text="🌍 Соц.сети")]
        ],
        resize_keyboard=True, one_time_keyboard=False
    )

def services_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💆 Массаж")],
            [KeyboardButton(text="💇 Парикмахер")],
            [KeyboardButton(text="💅 Ногти")],
            [KeyboardButton(text="◀️ Назад")]
        ],
        resize_keyboard=True, one_time_keyboard=True
    )

def social_keyboard():
    # Клавиатура для соцсетей
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=name, url=url)] for name, url in SOCIAL_LINKS
        ]
    )

def records_keyboard(records):
    # Показывает записи с кнопками отмены
    btns = [
        [InlineKeyboardButton(text=f"Отмена: {rec}", callback_data=f"cancel:{rec}")]
        for rec in records
    ]
    return InlineKeyboardMarkup(inline_keyboard=btns) if btns else None

# ---- Обработчики ----

@bot.message("start")
async def handle_start(msg):
    await msg.answer("Добро пожаловать! Выберите действие:", reply_markup=main_menu_keyboard())

@bot.message()
async def handle_menu(msg):
    text = (msg.text or "").strip()
    user_id = msg.from_user.id

    if text == "📝 Запись на приём":
        await msg.answer("Выберите направление:", reply_markup=services_keyboard())

    elif text == "💆 Массаж":
        # ВСТАВЬТЕ СЮДА ВАШ КОД ОТРАБОТКИ МАССАЖА (ваш поток диалогов, подбор даты и т.д.)
        await msg.answer("Выберите специалиста и время — ваш сценарий здесь.")

    elif text == "💇 Парикмахер":
        await msg.answer("Запись к парикмахеру будет доступна скоро.")

    elif text == "💅 Ногти":
        await msg.answer("Запись на ногти будет доступна скоро.")

    elif text == "🌐 Оф. сайт":
        await msg.answer(f"Наш официальный сайт: {OFFICIAL_SITE}")

    elif text == "🌍 Соц.сети":
        await msg.answer("Мы в соцсетях:", reply_markup=social_keyboard())

    elif text == "🔖 Мои записи":
        records = user_appointments.get(user_id, [])
        if not records:
            await msg.answer("У вас пока нет записей.")
            return
        await msg.answer(
            "Ваши записи:",
            reply_markup=records_keyboard(records)
        )

    elif text == "◀️ Назад":
        await msg.answer("Главное меню:", reply_markup=main_menu_keyboard())
    else:
        await msg.answer("Пожалуйста, используйте кнопки меню.")

# ---- Callback для отмены записи ----

@bot.callback()
async def handle_callback(call):
    if call.data.startswith("cancel:"):
        record = call.data.split(":", 1)[1]
        user_id = call.from_user.id
        recs = user_appointments.get(user_id, [])
        if record in recs:
            recs.remove(record)
            user_appointments[user_id] = recs
            await call.message.edit_text("Запись отменена.")
        else:
            await call.message.edit_text("Запись не найдена.")

# ---- Точка входа ----

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
