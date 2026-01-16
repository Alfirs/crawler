from aiogram.fsm.state import State, StatesGroup


class BookingState(StatesGroup):
    pick_service = State()
    pick_staff = State()
    pick_date = State()
    pick_time = State()
    enter_client = State()
