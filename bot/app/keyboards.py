from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo


def open_app_keyboard(webapp_url: str | None) -> InlineKeyboardMarkup | None:
    if webapp_url is None:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Открыть «Контакт»", web_app=WebAppInfo(url=webapp_url))]]
    )
