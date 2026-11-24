"""Загрузка конфигурации: ``config/config.yaml`` + переопределения из ``.env``.

Приоритет: переменные окружения (``.env``) > ``config/config.yaml`` > значения по умолчанию.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
CONFIG_PATH = BASE_DIR / "config.yaml"
ENV_PATH = PROJECT_DIR / ".env"


class AppSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = "transtalion"
    host: str = "0.0.0.0"
    port: int = 8000


class LLMSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    provider: str = "openai"
    model: str = "gpt-4o-mini"
    api_key_env: str = "OPENAI_API_KEY"
    base_url: str | None = None
    trust_env: bool = True
    fallback_model: str | None = None
    fallback_base_url: str | None = None
    temperature: float = 0.0
    timeout_seconds: float = 30.0
    max_retries: int = 2

    @property
    def api_key(self) -> str | None:
        """Ключ доступа к LLM из переменной окружения (None, если не задан)."""
        return os.getenv(self.api_key_env, "").strip() or None

    @property
    def api_url(self) -> str:
        """URL метода chat/completions."""
        base = (self.base_url or "https://api.openai.com/v1").rstrip("/")
        return f"{base}/chat/completions"


class LoggingSettings(BaseModel):
    """Параметры логирования: консоль и файл с ротацией."""

    model_config = ConfigDict(extra="ignore")

    enabled: bool = True
    level: str = "INFO"
    console: bool = True
    file: bool = True
    file_path: str = "logs/transtalion.log"
    max_bytes: int = 5_000_000
    backup_count: int = 5
    format: str = (
        "%(asctime)s | %(levelname)-8s | %(request_id)s | %(name)s | %(message)s"
    )
    date_format: str = "%Y-%m-%d %H:%M:%S"


class CacheSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool = True
    backend: str = "memory"
    ttl_seconds: int = 86400
    max_size: int = 10000
    path: str = ".cache/translations.json"
    redis_url: str = "redis://localhost:6379/0"


class TranslationSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    source_lang: str = "ru"
    target_lang: str = "en"
    output_case: str = "snake_case"
    singular: bool = True
    drop_prepositions: bool = True


class Settings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    app: AppSettings = AppSettings()
    llm: LLMSettings = LLMSettings()
    cache: CacheSettings = CacheSettings()
    logging: LoggingSettings = LoggingSettings()
    translation: TranslationSettings = TranslationSettings()


def _read_yaml(path: Path) -> dict[str, Any]:
    """Прочитать YAML-конфигурацию (пустой словарь, если файла нет)."""
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _apply_env_overrides(data: dict[str, Any]) -> dict[str, Any]:
    """Переопределить значения из YAML переменными окружения (пустые игнорируются)."""
    llm = data.setdefault("llm", {})
    cache = data.setdefault("cache", {})
    app = data.setdefault("app", {})
    log = data.setdefault("logging", {})

    mapping: dict[str, tuple[dict[str, Any], str]] = {
        "LLM_PROVIDER": (llm, "provider"),
        "LLM_MODEL": (llm, "model"),
        "LLM_BASE_URL": (llm, "base_url"),
        "LLM_TRUST_ENV": (llm, "trust_env"),
        "LLM_FALLBACK_MODEL": (llm, "fallback_model"),
        "LLM_FALLBACK_BASE_URL": (llm, "fallback_base_url"),
        "CACHE_ENABLED": (cache, "enabled"),
        "CACHE_BACKEND": (cache, "backend"),
        "CACHE_TTL_SECONDS": (cache, "ttl_seconds"),
        "CACHE_MAX_SIZE": (cache, "max_size"),
        "APP_HOST": (app, "host"),
        "APP_PORT": (app, "port"),
        "LOG_ENABLED": (log, "enabled"),
        "LOG_LEVEL": (log, "level"),
        "LOG_CONSOLE": (log, "console"),
        "LOG_FILE": (log, "file"),
        "LOG_FILE_PATH": (log, "file_path"),
        "LOG_MAX_BYTES": (log, "max_bytes"),
        "LOG_BACKUP_COUNT": (log, "backup_count"),
        "LOG_FORMAT": (log, "format"),
    }

    for env_name, (target, key) in mapping.items():
        raw = os.getenv(env_name)
        if raw is None or not raw.strip():
            continue
        target[key] = raw.strip()

    return data


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Собрать настройки приложения (кешируется на время жизни процесса)."""
    load_dotenv(ENV_PATH, override=False)
    data = _read_yaml(CONFIG_PATH)
    data = _apply_env_overrides(data)
    return Settings.model_validate(data)
