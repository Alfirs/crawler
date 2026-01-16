from aiogram.fsm.state import State, StatesGroup


class FitSession(StatesGroup):
    waiting_for_car = State()
    waiting_for_wheel = State()
    ready_for_generation = State()
