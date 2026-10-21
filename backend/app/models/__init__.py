# Все модели импортируются здесь, чтобы Alembic видел их в Base.metadata.
from app.models.scenario import Scenario
from app.models.training import Message, TrainingResult, TrainingSession
from app.models.usage import AIUsage
from app.models.user import AuthSession, User

__all__ = ["AIUsage", "AuthSession", "Message", "Scenario", "TrainingResult", "TrainingSession", "User"]
