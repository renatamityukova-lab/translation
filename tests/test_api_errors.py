"""Тесты обработки ошибок API: 400 / 500 / 502 / 503 и успешный сценарий."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cache import reset_translation_cache
from llm.errors import (
    LLMConfigError,
    LLMError,
    LLMRequestRejectedError,
    LLMResponseError,
    LLMUnavailableError,
)
from main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clean_cache() -> None:
    """Кеш не должен влиять на проверку ошибок (иначе ответ придёт из кеша)."""
    reset_translation_cache()
    yield
    reset_translation_cache()


@pytest.fixture
def stub_translate(monkeypatch: pytest.MonkeyPatch):
    """Подменить вызов LLM в бизнес-логике."""

    def _install(behavior):
        monkeypatch.setattr("services.translator.complete", behavior)

    return _install


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({}, "message"),
        ({"message": ""}, "message"),
        ({"message": "    "}, "message"),
        ({"message": "я" * 1001}, "message"),
        ({"message": "ok", "extra": 1}, "extra"),
        ({"message": 123}, "message"),
    ],
)
def test_invalid_input_returns_400(payload: dict, field: str) -> None:
    response = client.post("/chat", json=payload)
    assert response.status_code == 400
    body = response.json()
    assert "Некорректный запрос" in body["detail"]
    assert any(item["field"] == field for item in body["errors"])


def test_malformed_json_returns_400() -> None:
    response = client.post(
        "/chat",
        content="{not json}",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400
    assert "Некорректный запрос" in response.json()["detail"]


def test_success_returns_200(stub_translate) -> None:
    stub_translate(lambda *args, **kwargs: "partner_contract")
    response = client.post("/chat", json={"message": "ДоговорыКонтрагентов"})
    assert response.status_code == 200
    assert response.json() == {
        "message": "ДоговорыКонтрагентов",
        "translated": "partner_contract",
    }


@pytest.mark.parametrize(
    ("error", "status", "fragment"),
    [
        (LLMConfigError("нет ключа"), 503, "LLM не настроена"),
        (LLMUnavailableError("таймаут"), 503, "временно недоступен"),
        (LLMResponseError("пустой ответ"), 502, "Некорректный ответ модели"),
        (LLMRequestRejectedError("HTTP 404"), 502, "отклонил запрос"),
        (LLMError("прочее"), 502, "Ошибка LLM"),
    ],
)
def test_llm_errors_are_mapped(stub_translate, error, status, fragment) -> None:
    def raiser(*args, **kwargs):
        raise error

    stub_translate(raiser)
    response = client.post("/chat", json={"message": "ДоговорыКонтрагентов"})
    assert response.status_code == status
    assert fragment in response.json()["detail"]


def test_unexpected_error_returns_500(stub_translate) -> None:
    def raiser(*args, **kwargs):
        raise RuntimeError("boom")

    stub_translate(raiser)
    safe_client = TestClient(app, raise_server_exceptions=False)
    response = safe_client.post("/chat", json={"message": "ДоговорыКонтрагентов"})
    assert response.status_code == 500
    assert response.json() == {"detail": "Внутренняя ошибка сервиса"}


def test_health_returns_200() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
