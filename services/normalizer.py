"""Постобработка ответа LLM: приведение к ``lower_snake_case``.

Модель может вернуть markdown, кавычки, пояснения или дефисы — здесь ответ
приводится к формату, требуемому постановкой задачи.
"""

from __future__ import annotations

import re

# Служебные слова, которые не должны попадать в результат (правило «убрать предлоги»).
STOP_WORDS = frozenset(
    {"of", "for", "in", "on", "to", "with", "from", "by", "and", "or", "the", "a", "an"}
)

# Всё, что не строчная латиница и не цифра, считается разделителем.
_SEPARATORS = re.compile(r"[^a-z0-9]+")

# Контракт результата: lower_snake_case без ведущих/замыкающих и двойных подчёркиваний.
SNAKE_CASE_PATTERN = re.compile(r"[a-z0-9]+(?:_[a-z0-9]+)*")

# Текст, состоящий только из «разрешённых» символов, считается самим ответом
# (переносы строк внутри ответа не должны обрезать перевод).
_ANSWER_ONLY = re.compile(r"[a-z0-9_\s]+")

# Блоки рассуждений reasoning-моделей (MiniMax и др.) в ответе ``content``.
_REASONING_BLOCK = re.compile(
    r"<\s*(?:think|thinking|reasoning)\s*>.*?<\s*/\s*(?:think|thinking|reasoning)\s*>",
    re.IGNORECASE | re.DOTALL,
)
_REASONING_OPEN = re.compile(r"<\s*(?:think|thinking|reasoning)\s*>", re.IGNORECASE)
_REASONING_CLOSE = re.compile(r"<\s*/\s*(?:think|thinking|reasoning)\s*>", re.IGNORECASE)


def _strip_reasoning(text: str) -> str:
    """Убрать из ответа блоки рассуждений, оставив только итоговый перевод."""
    text = _REASONING_BLOCK.sub(" ", text)

    last_close = None
    for match in _REASONING_CLOSE.finditer(text):
        last_close = match
    if last_close is not None:
        # обрезанный reasoning: берём всё после последнего закрывающего тега
        text = text[last_close.end() :]

    open_match = _REASONING_OPEN.search(text)
    if open_match is not None:
        # незакрытый блок рассуждений — отбрасываем хвост
        text = text[: open_match.start()]

    return text


def normalize_snake_case(raw_answer: str) -> str:
    """Привести произвольный ответ модели к ``lower_snake_case``.

    Удаляет блоки рассуждений и markdown/кавычки, берёт первую содержательную
    строку, приводит к нижнему регистру, заменяет разделители на ``_``, убирает
    служебные слова и повторные подчёркивания.

    :returns: нормализованная строка (может быть пустой, если ответ бесполезен)
    """
    text = _strip_reasoning(raw_answer).strip().strip("`\"' \t\r\n").lower()

    if not _ANSWER_ONLY.fullmatch(text):
        # Есть посторонние символы/слова — берём первую содержательную строку,
        # отбрасывая пояснения модели.
        for line in text.splitlines():
            candidate = line.strip().strip("`\"'*- ").lower()
            if candidate:
                text = candidate
                break

    tokens = [token for token in _SEPARATORS.split(text) if token]
    tokens = [token for token in tokens if token not in STOP_WORDS]
    return "_".join(tokens)


def is_valid_snake_case(value: str) -> bool:
    """Проверить, что строка соответствует ``lower_snake_case``.

    Допустимы только строчные латинские буквы и цифры, разделённые одиночными ``_``;
    строка не может быть пустой и не может начинаться/заканчиваться на ``_``.
    """
    return bool(SNAKE_CASE_PATTERN.fullmatch(value))
