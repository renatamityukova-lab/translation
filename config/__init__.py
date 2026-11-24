"""Конфигурация сервиса Transtalion.

Значения читаются из ``config/config.yaml`` и переопределяются переменными
окружения из ``.env`` (см. :func:`config.settings.get_settings`).
"""

from config.settings import Settings, get_settings

__all__ = ["Settings", "get_settings"]
