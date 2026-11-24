"""Pydantic-схемы API-слоя (запрос/ответ эндпоинта перевода)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

MAX_MESSAGE_LENGTH = 1000


class ChatRequest(BaseModel):
    """Запрос на перевод идентификатора 1С.

    ``message`` — фраза в стиле 1С (CamelCase, русский язык, без пробелов).
    Пробелы по краям обрезаются, пустое значение и длина > 1000 символов отклоняются.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    message: str = Field(
        ...,
        min_length=1,
        max_length=MAX_MESSAGE_LENGTH,
        description="Идентификатор 1С в CamelCase, например ДоговорыКонтрагентов",
        examples=["ДоговорыКонтрагентов"],
    )


class ChatResponse(BaseModel):
    """Результат перевода."""

    message: str = Field(..., description="Исходный идентификатор (после trim)")
    translated: str = Field(..., description="Перевод в lower_snake_case, например partner_contract")
