from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.config import get_settings
from app.keyboards import open_app_keyboard

router = Router(name="help")

HELP = (
    "Как пользоваться:\n"
    "1. Откройте приложение кнопкой ниже.\n"
    "2. Выберите ситуацию, характер собеседника и сложность.\n"
    "3. Разговаривайте как в жизни — собеседник не будет подсказывать.\n"
    "4. Нажмите «Завершить», чтобы получить разбор.\n\n"
    "Команды: /start — начать, /help — эта справка."
)


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(HELP, reply_markup=open_app_keyboard(get_settings().webapp_url))
