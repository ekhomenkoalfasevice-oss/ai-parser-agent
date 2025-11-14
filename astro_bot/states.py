"""FSM states for onboarding and other flows."""

from aiogram.fsm.state import State, StatesGroup


class Onboarding(StatesGroup):
    waiting_birth_date = State()
    waiting_details = State()
