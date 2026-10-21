"""Проверка реплики персонажа до показа пользователю."""

import re

# Явные признаки выхода из роли — только высказывания о СЕБЕ как об ассистенте.
# Повтор слов собеседника в роли («Системный промпт — это что вообще?») допустим:
# так реагирует живой человек на странный вопрос.
_LEAK_PATTERNS = [
    r"\bкак (?:языковая модель|ии|искусственный интеллект|ии-ассистент)\b",
    r"\bя\s*[—-]?\s*(?:языковая модель|ии-ассистент|искусственный интеллект|нейросеть)\b",
    r"\bя\s+(?:всего лишь\s+|просто\s+)?(?:ии|бот|чат-?бот)\b(?!\?)",
    r"\b(?:мой|мои|моего|моих|моём)\s+(?:системн\w*\s+)?(?:промпт\w*|инструкци\w*)",
    r"\bmy (?:system )?(?:prompt|instructions)\b",
    r"\bв рамках (?:сценария|тренировки|ролевой игры)\b",
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
