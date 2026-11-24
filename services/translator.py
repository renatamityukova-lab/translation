"""Бизнес-логика перевода идентификаторов 1С.

Единая точка входа для API-слоя — :func:`translate_identifier`.
Оркестрация: кеш → построение промпта → вызов LLM → постобработка → запись в кеш.

Каждый этап пишется в лог: идентификатор, попадание/промах кеша, промпт,
ответ модели, результат нормализации и ошибки.
"""

from __future__ import annotations

import logging
import time

from cache import get_translation_cache
from config.settings import Settings, get_settings
from llm.client import complete
from llm.errors import LLMError
from llm.prompts import SYSTEM_PROMPT, build_user_prompt
from services.normalizer import is_valid_snake_case, normalize_snake_case

logger = logging.getLogger(__name__)


def translate_identifier(identifier: str, *, settings: Settings | None = None) -> str:
    """Перевести идентификатор 1С в английский ``lower_snake_case``.

    :param identifier: идентификатор в CamelCase, например ``ДоговорыКонтрагентов``
    :param settings: настройки (по умолчанию — из ``config/config.yaml`` и ``.env``)
    :returns: перевод, например ``partner_contract``
    :raises LLMError: модель недоступна или вернула бесполезный ответ
    """
    settings = settings or get_settings()
    cache = get_translation_cache(settings)

    started = time.perf_counter()
    cache_key = identifier.strip()
    logger.info(
        "Перевод: старт — identifier=%r (cache_key=%r, длина %d)",
        identifier,
        cache_key,
        len(cache_key),
    )

    if cache is not None:
        cached = cache.get(cache_key)
        if cached is not None:
            logger.info(
                "Кеш: попадание — %r → %r (%.3f с)",
                cache_key,
                cached,
                time.perf_counter() - started,
            )
            return cached
        logger.info("Кеш: промах — %r, требуется вызов LLM", cache_key)

    logger.debug("Системный промпт: %s", SYSTEM_PROMPT)
    user_prompt = build_user_prompt(identifier)
    logger.info(
        "Промпт для LLM (%d символов):\n%s", len(user_prompt), user_prompt
    )

    try:
        raw_answer = complete(
            SYSTEM_PROMPT,
            user_prompt,
            settings=settings.llm,
        )
    except LLMError as exc:
        logger.error(
            "Ошибка LLM при переводе %r: %s: %s",
            cache_key,
            type(exc).__name__,
            exc,
        )
        raise

    logger.info("Ответ LLM (%d символов): %r", len(raw_answer), raw_answer)

    result = normalize_snake_case(raw_answer)
    logger.info("Нормализация: %r → %r", raw_answer, result)

    if not result:
        logger.error(
            "Пустой результат нормализации для %r (ответ LLM: %r)", cache_key, raw_answer
        )
        raise LLMError(f"Модель вернула ответ без пригодного перевода: {raw_answer!r}")
    if not is_valid_snake_case(result):
        logger.error(
            "Невалидный формат после нормализации для %r: %r", cache_key, result
        )
        raise LLMError(f"Модель вернула некорректный формат (ожидался snake_case): {result!r}")

    if cache is not None:
        cache.set(cache_key, result)
        logger.info("Кеш: сохранено — %r → %r", cache_key, result)

    logger.info(
        "Перевод: готово — %r → %r за %.3f с",
        cache_key,
        result,
        time.perf_counter() - started,
    )
    return result
