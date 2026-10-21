from aiogram import Router

from app.handlers.errors import router as errors_router
from app.handlers.help import router as help_router
from app.handlers.start import router as start_router


def build_router() -> Router:
    root = Router(name="root")
    root.include_routers(start_router, help_router, errors_router)
    return root
