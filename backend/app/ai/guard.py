"""Проверка реплики персонажа до показа пользователю."""

import re

# Явные признаки выхода из роли. Обычные слова («инструкция» в рабочем
# разговоре) не трогаем — только формулировки ассистента о себе.
_LEAK_PATTERNS = [
    r"\bкак (?:языковая модель|ии|искусственный интеллект|ассистент)\b",
    r"\bя\s*[—-]?\s*(?:языковая модель|ии-ассистент|искусственный интеллект|чат-?бот)\b",
    r"\bсистемн(?:ый|ого|ом) промпт",
    r"\bsystem prompt\b",
    r"\bмои инструкции\b",
    r"\bв рамках (?:сценария|тренировки)\b",
    r"\bуровень сложности\b",
]
_LEAK_RE = re.compile("|".join(_LEAK_PATTERNS), re.IGNORECASE)

MAX_REPLY_CHARS = 1200


class GuardViolation(Exception):
    pass


def clean_reply(text: str, persona_name: str) -> str:
    reply = text.strip().strip('"«»').strip()
    # Модель иногда подписывает реплику: «Анна: Привет»
    for prefix in (f"{persona_name}:", f"{persona_name} :", "Ответ:", "Собеседник:"):
        if reply.lower().startswith(prefix.lower()):
            reply = reply[len(prefix) :].strip()
    # Ремарки в звёздочках не нужны: только прямая речь
    reply = re.sub(r"\*[^*\n]{1,80}\*", "", reply).strip()
    reply = re.sub(r"\n{3,}", "\n\n", reply)
    if not reply:
        raise GuardViolation("пустая реплика")
    if _LEAK_RE.search(reply):
        raise GuardViolation("выход из роли")
    if len(reply) > MAX_REPLY_CHARS:
        cut = reply[:MAX_REPLY_CHARS]
        last_end = max(cut.rfind("."), cut.rfind("!"), cut.rfind("?"))
        reply = cut[: last_end + 1] if last_end > 200 else cut
    return reply
