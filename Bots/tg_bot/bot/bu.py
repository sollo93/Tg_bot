from aiogram.fsm.state import StatesGroup, State

class Appointment(StatesGroup):
    specialist = State()
    service = State()
    date = State()
    time = State()
    contact = State()
