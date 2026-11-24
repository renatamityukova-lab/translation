"""Тесты логирования: файл + консоль, request_id, этапы перевода и ошибки."""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient

from cache import reset_translation_cache
from config import logging_config
from config.logging_config import (
    RequestIdFilter,
    reset_request_id,
    reset_logging,
    set_request_id,
    setup_logging,
)
from config.settings import CacheSettings, LoggingSettings, Settings
from llm.errors import LLMUnavailableError
from main import app
from services.translator import translate_identifier


@pytest.fixture(autouse=True)
def _clean_cache():
    """Общий кеш не должен протекать между тестами (в т. ч. в HTTP-сценарии)."""
    reset_translation_cache()
    yield
    reset_translation_cache()


@pytest.fixture
def isolated_logging():
    """Сохранить/восстановить обработчики корневого логгера вокруг теста."""
    root = logging.getLogger()
    saved_handlers = [
        handler
        for handler in root.handlers
        if not getattr(handler, "_transtalion_handler", False)
    ]
    saved_level = root.level
    saved_configured = logging_config._configured
    yield
    reset_logging()
    for handler in saved_handlers:
        root.addHandler(handler)
    root.setLevel(saved_level)
    logging_config._configured = saved_configured


def test_setup_logging_writes_to_file_and_console(tmp_path, isolated_logging) -> None:
    log_file = tmp_path / "nested" / "app.log"
    settings = LoggingSettings(
        level="DEBUG",
        console=True,
        file=True,
        file_path=str(log_file),
    )

    root = setup_logging(settings, force=True)
    logging.getLogger("test.logging").debug("сообщение для файла")
    for handler in root.handlers:
        handler.flush()

    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "сообщение для файла" in content
    assert "DEBUG" in content
    assert "test.logging" in content

    file_handlers = [h for h in root.handlers if isinstance(h, logging.FileHandler)]
    console_handlers = [
        h
        for h in root.handlers
        if isinstance(h, logging.StreamHandler)
        and not isinstance(h, logging.FileHandler)
    ]
    assert len(file_handlers) == 1
    assert len(console_handlers) == 1


def test_logging_disabled_adds_null_handler(isolated_logging) -> None:
    root = setup_logging(LoggingSettings(enabled=False), force=True)

    assert any(isinstance(h, logging.NullHandler) for h in root.handlers)
    assert not any(isinstance(h, logging.FileHandler) for h in root.handlers)


def test_request_id_filter_adds_field() -> None:
    token = set_request_id("req12345")
    try:
        record = logging.LogRecord(
            "test", logging.INFO, __file__, 1, "сообщение", None, None
        )
        assert RequestIdFilter().filter(record) is True
        assert record.request_id == "req12345"
    finally:
        reset_request_id(token)

    record = logging.LogRecord("test", logging.INFO, __file__, 1, "вне запроса", None, None)
    RequestIdFilter().filter(record)
    assert record.request_id == "-"


def test_translate_logs_prompt_answer_and_result(monkeypatch, caplog) -> None:
    settings = Settings(cache=CacheSettings(enabled=False))
    monkeypatch.setattr(
        "services.translator.complete", lambda *args, **kwargs: "partner_contract"
    )

    with caplog.at_level(logging.INFO, logger="services.translator"):
        result = translate_identifier("ДоговорыКонтрагентов", settings=settings)

    assert result == "partner_contract"
    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "Перевод: старт" in messages
    assert "Промпт для LLM" in messages
    assert "Ответ LLM" in messages
    assert "Нормализация" in messages
    assert "partner_contract" in messages


def test_translate_logs_llm_errors(monkeypatch, caplog) -> None:
    settings = Settings(cache=CacheSettings(enabled=False))

    def boom(*args, **kwargs):
        raise LLMUnavailableError("нет связи с моделью")

    monkeypatch.setattr("services.translator.complete", boom)

    with caplog.at_level(logging.INFO, logger="services.translator"):
        with pytest.raises(LLMUnavailableError):
            translate_identifier("ЗаказыПокупателей", settings=settings)

    assert any(
        record.levelno == logging.ERROR and "Ошибка LLM" in record.getMessage()
        for record in caplog.records
    )


def test_http_request_logged_with_request_id(monkeypatch, caplog) -> None:
    reset_translation_cache()
    monkeypatch.setattr(
        "services.translator.complete", lambda *args, **kwargs: "partner_contract"
    )

    with caplog.at_level(logging.INFO):
        response = TestClient(app).post(
            "/chat", json={"message": "ДоговорыКонтрагентов"}
        )

    assert response.status_code == 200
    request_id = response.headers["X-Request-ID"]
    assert len(request_id) == 8

    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "запрос начат" in messages
    assert "POST /chat — запрос на перевод" in messages
    assert "POST /chat — ответ" in messages
    assert "завершён" not in messages  # формат завершения: «← ... за ... с»
    assert "← POST /chat — 200" in messages

    # request_id из контекста попал в записи логов
    assert any(
        getattr(record, "request_id", "-") == request_id for record in caplog.records
    )
