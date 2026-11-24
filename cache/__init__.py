"""Кеш переводов.

Назначение — не отправлять в LLM повторные запросы для уже переведённых
идентификаторов. Реализован in-memory бэкенд (словарь с TTL); ``file`` и ``redis``
заявлены в конфигурации, но пока не реализованы (используется memory с предупреждением).
"""

from __future__ import annotations

import logging

from cache.ttl_cache import TTLCache
from config.settings import Settings, get_settings

logger = logging.getLogger(__name__)

_translation_cache: TTLCache[str, str] | None = None


def get_translation_cache(settings: Settings | None = None) -> TTLCache[str, str] | None:
    """Вернуть общий кеш переводов согласно настройкам.

    :returns: экземпляр кеша либо ``None``, если кеширование отключено
    """
    global _translation_cache

    settings = settings or get_settings()
    if not settings.cache.enabled:
        return None

    if _translation_cache is None:
        if settings.cache.backend != "memory":
            logger.warning(
                "Бэкенд кеша %r не реализован — используется memory",
                settings.cache.backend,
            )
        _translation_cache = TTLCache(
            ttl_seconds=settings.cache.ttl_seconds,
            max_size=settings.cache.max_size,
        )

    return _translation_cache


def reset_translation_cache() -> None:
    """Очистить и сбросить общий кеш (тесты, перезагрузка настроек)."""
    global _translation_cache
    if _translation_cache is not None:
        _translation_cache.clear()
    _translation_cache = None


__all__ = ["TTLCache", "get_translation_cache", "reset_translation_cache"]
