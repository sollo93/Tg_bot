import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

import data
from bu import Appointment

logging.basicConfig(level=logging.INFO)

API_TOKEN = "7823462739:AAGbT9TVD3Squqi6urJ092on-ktRZxjU3ao"

bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Команда /start — приветствие и главное меню
@dp.message(Command("start"))
async def start(message: types.Message):
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Перейти на сайт")],
            [KeyboardButton(text="Записаться на приём")],
            [KeyboardButton(text="Отказаться от записи")],
            [KeyboardButton(text="Список групп и каналов")]
        ],
        resize_keyboard=True
    )
    await message.answer(
        "Добро пожаловать! Выберите действие:",
        reply_markup=keyboard
    )

# Обработка кнопок главного меню
@dp.message()
async def menu_handler(message: types.Message, state: FSMContext):
    text = message.text

    if text == "Перейти на сайт":
        await message.answer(f"Перейдите по ссылке: {data.WEBSITE_URL}")

    elif text == "Записаться на приём":
        # Начинаем FSM
        await message.answer("Выберите специалиста:", reply_markup=create_keyboard(data.SPECIALISTS))
        await state.set_state(Appointment.specialist)

    elif text == "Отказаться от записи":
        await message.answer("Пожалуйста, введите контактную информацию, чтобы отменить запись:")
        await state.set_state(Appointment.contact)  # Используем contact для ввода отмены

    elif text == "Список групп и каналов":
        text = "Наши группы и каналы:\n"
        for group in data.GROUPS:
            text += f"{group['name']}: {group['link']}\n"
        await message.answer(text)

    else:
        await message.answer("Пожалуйста, выберите действие из меню.")

# Вспомогательная функция для создания клавиатуры из списка
def create_keyboard(options: list):
    buttons = [[KeyboardButton(text=opt)] for opt in options]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True)

# FSM: выбор специалиста
@dp.message(Appointment.specialist)
async def choose_specialist(message: types.Message, state: FSMContext):
    if message.text not in data.SPECIALISTS:
        await message.answer("Пожалуйста, выберите специалиста из списка.")
        return
    await state.update_data(specialist=message.text)
    await message.answer("Выберите услугу:", reply_markup=create_keyboard(data.SERVICES))
    await state.set_state(Appointment.service)

# FSM: выбор услуги
@dp.message(Appointment.service)
async def choose_service(message: types.Message, state: FSMContext):
    if message.text not in data.SERVICES:
        await message.answer("Пожалуйста, выберите услугу из списка.")
        return
    await state.update_data(service=message.text)
    await message.answer("Введите дату приёма в формате ДД.ММ.ГГГГ:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Appointment.date)

# FSM: ввод даты
@dp.message(Appointment.date)
async def input_date(message: types.Message, state: FSMContext):
    # Здесь можно добавить проверку формата даты
    await state.update_data(date=message.text)
    await message.answer("Введите время приёма (например, 15:30):")
    await state.set_state(Appointment.time)

# FSM: ввод времени
@dp.message(Appointment.time)
async def input_time(message: types.Message, state: FSMContext):
    # Можно добавить проверку формата времени
    await state.update_data(time=message.text)
    await message.answer("Введите контактную информацию (телефон или email):")
    await state.set_state(Appointment.contact)

# FSM: ввод контакта и подтверждение записи
@dp.message(Appointment.contact)
async def input_contact(message: types.Message, state: FSMContext):
    data_ = await state.get_data()
    if "specialist" in data_:
        # Это запись на приём
        data_["contact"] = message.text
        await message.answer(
            f"Спасибо! Ваша запись:\n"
            f"Специалист: {data_['specialist']}\n"
            f"Услуга: {data_['service']}\n"
            f"Дата: {data_['date']}\n"
            f"Время: {data_['time']}\n"
            f"Контакт: {data_['contact']}\n\n"
            "Мы свяжемся с вами для подтверждения."
        )
        # Здесь можно сохранить запись в базу или отправить администратору
        await state.clear()
    else:
        # Это отказ от записи — просто подтверждаем
        contact_info = message.text
        await message.answer(f"Запись с контактом {contact_info} отменена. Спасибо!")
        # Здесь можно обработать отмену в базе
        await state.clear()

# Запуск бота
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
