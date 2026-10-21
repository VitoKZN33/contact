import logging

from aiogram import Router
from aiogram.types import ErrorEvent

logger = logging.getLogger(__name__)

router = Router(name="errors")


@router.errors()
async def on_error(event: ErrorEvent) -> bool:
    # Пользователю — нейтральное сообщение, детали — только в лог
    logger.error("bot handler failed: %s", type(event.exception).__name__, exc_info=event.exception)
    message = event.update.message
    if message is not None:
        try:
            await message.answer("Что-то пошло не так. Попробуйте ещё раз чуть позже.")
        except Exception:
            logger.warning("failed to notify user about error")
    return True
