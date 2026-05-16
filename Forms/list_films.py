from aiogram.fsm.state import State, StatesGroup

class Form(StatesGroup):
    waiting_for_movie_name = State()
    waiting_for_movie_selection = State()
    waiting_for_delete_number = State()
    waiting_for_delete_confirm = State()



