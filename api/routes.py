"""Эндпоинты сервиса Transtalion.

Роутеры только принимают и валидируют запрос, затем делегируют работу
в слой ``services``. Обращений к LLM и кешу на этом уровне нет.
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter

from api.schemas import ChatRequest, ChatResponse
from services.translator import translate_identifier

logger = logging.getLogger(__name__)

router = APIRouter(tags=["translation"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Перевести идентификатор 1С в snake_case",
    description=(
        "Принимает идентификатор в стиле 1С (CamelCase, русский язык, без пробелов) "
        "и возвращает его перевод на английский в формате lower_snake_case "
        "(единственное число, без предлогов, терминология учётных систем)."
    ),
)
def chat(payload: ChatRequest) -> ChatResponse:
    """Перевести идентификатор.

    Ошибки валидации (пустое сообщение, длина > 1000 символов) возвращаются как 422.
    """
    started = time.perf_counter()
    logger.info(
        "POST /chat — запрос на перевод: message=%r (длина %d)",
        payload.message,
        len(payload.message),
    )

    try:
        translated = translate_identifier(payload.message)
    except Exception as exc:  # noqa: BLE001 — логируем и пробрасываем в обработчики
        logger.error(
            "POST /chat — ошибка перевода %r: %s: %s",
            payload.message,
            type(exc).__name__,
            exc,
        )
        raise

    logger.info(
        "POST /chat — ответ: translated=%r за %.3f с",
        translated,
        time.perf_counter() - started,
    )
    return ChatResponse(message=payload.message, translated=translated)
