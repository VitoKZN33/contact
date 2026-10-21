"""Справочники домена. Единый источник для БД-ограничений, схем и сценариев."""

# Категории сценариев: ключ -> название для интерфейса
CATEGORIES: dict[str, str] = {
    "acquaintance": "Знакомство с незнакомыми людьми",
    "small_talk": "Поддержание разговора",
    "events": "Знакомства в компании и на мероприятиях",
    "first_date": "Первые свидания",
    "messaging": "Переписка и первый шаг",
    "opinion": "Своё мнение",
    "saying_no": "Умение сказать «нет»",
    "boundaries": "Личные границы",
    "criticism": "Ответ на критику",
    "conflict": "Сложные разговоры и конфликты",
    "favor": "Просьбы об услуге",
    "custom": "Своя ситуация",
}

# Характеры персонажей: ключ -> название
PERSONAS: dict[str, str] = {
    "friendly": "Дружелюбный",
    "neutral": "Нейтральный",
    "reserved": "Сдержанный",
    "shy": "Застенчивый",
    "sociable": "Общительный",
    "skeptical": "Скептичный",
    "demanding": "Требовательный",
    "unpredictable": "Непредсказуемый",
}

DIFFICULTIES: dict[str, str] = {
    "easy": "Лёгкий",
    "medium": "Средний",
    "hard": "Сложный",
}

GENDERS: dict[str, str] = {
    "male": "Мужской",
    "female": "Женский",
}

INTERACTION_MODES = ("text",)

TRAINING_STATUSES = ("active", "completed", "abandoned", "expired")
ANALYSIS_STATUSES = ("none", "pending", "done", "failed")
MESSAGE_ROLES = ("user", "persona")
MESSAGE_STATUSES = ("accepted", "completed", "failed")
USER_STATUSES = ("active", "blocked")
PLANS = ("free",)
AI_OPERATIONS = ("reply", "summary", "analysis")


def sql_in(values) -> str:
    """Список значений для CHECK-ограничения: ('a', 'b')."""
    return "(" + ", ".join(f"'{v}'" for v in values) + ")"
