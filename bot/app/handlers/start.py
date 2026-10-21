from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.config import get_settings
from app.keyboards import open_app_keyboard

router = Router(name="start")

WELCOME = (
    "Привет! Это «Контакт» — тренажёр живого общения.\n\n"
    "Выберите ситуацию и характер собеседника, поговорите с ним, "
    "а после разговора получите разбор: что получилось и что можно сказать иначе."
)

UNAVAILABLE = "Приложение пока недоступно. Загляните чуть позже."


@router.message(CommandStart())
async def start(message: Message) -> None:
    keyboard = open_app_keyboard(get_settings().webapp_url)
    if keyboard is None:
        await message.answer(UNAVAILABLE)
        return
    await message.answer(WELCOME, reply_markup=keyboard)
