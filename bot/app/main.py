import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, MenuButtonWebApp, WebAppInfo

from app.config import get_settings
from app.handlers import build_router

logger = logging.getLogger("bot")


async def configure_bot(bot: Bot, webapp_url: str | None) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Открыть «Контакт»"),
            BotCommand(command="help", description="Как пользоваться"),
        ]
    )
    if webapp_url is not None:
        await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="Контакт", web_app=WebAppInfo(url=webapp_url)))
    else:
        logger.warning("TELEGRAM_WEBAPP_URL не задан или не https — кнопка меню не настроена")


async def main() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        stream=sys.stdout,
        format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
    )

    bot = Bot(token=settings.telegram_bot_token.get_secret_value())
    dp = Dispatcher()
    dp.include_router(build_router())

    await configure_bot(bot, settings.webapp_url)
    # Один процесс polling на токен; старые апдейты, накопленные за простой, пропускаем
    await dp.start_polling(bot, drop_pending_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
