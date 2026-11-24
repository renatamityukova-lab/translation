"""Тесты TTL-кеша и его интеграции с бизнес-логикой."""

from __future__ import annotations

import pytest

from cache import get_translation_cache, reset_translation_cache
from cache.ttl_cache import TTLCache
from config.settings import CacheSettings, Settings
from services.translator import translate_identifier


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture(autouse=True)
def _clean_cache() -> None:
    reset_translation_cache()
    yield
    reset_translation_cache()


def test_set_and_get() -> None:
    cache: TTLCache[str, str] = TTLCache(ttl_seconds=60)
    cache.set("key", "value")
    assert cache.get("key") == "value"
    assert len(cache) == 1
    assert "key" in cache


def test_expiration_by_ttl() -> None:
    clock = FakeClock()
    cache: TTLCache[str, str] = TTLCache(ttl_seconds=10, clock=clock)
    cache.set("key", "value")

    clock.advance(9)
    assert cache.get("key") == "value"

    clock.advance(1)
    assert cache.get("key") is None
    assert len(cache) == 0


def test_purge_expired() -> None:
    clock = FakeClock()
    cache: TTLCache[str, str] = TTLCache(ttl_seconds=5, clock=clock)
    cache.set("a", "1")
    cache.set("b", "2")
    clock.advance(6)

    assert cache.purge_expired() == 2
    assert len(cache) == 0


def test_delete_and_clear() -> None:
    cache: TTLCache[str, str] = TTLCache(ttl_seconds=60)
    cache.set("a", "1")
    cache.set("b", "2")

    cache.delete("a")
    assert cache.get("a") is None
    assert cache.get("b") == "2"

    cache.clear()
    assert len(cache) == 0


def test_max_size_evicts_oldest_expiring() -> None:
    clock = FakeClock()
    cache: TTLCache[str, str] = TTLCache(ttl_seconds=10, max_size=2, clock=clock)

    cache.set("a", "1")
    clock.advance(1)
    cache.set("b", "2")
    clock.advance(1)
    cache.set("c", "3")

    assert len(cache) == 2
    assert cache.get("a") is None  # вытеснена как самая старая
    assert cache.get("b") == "2"
    assert cache.get("c") == "3"


def test_invalid_ttl_rejected() -> None:
    with pytest.raises(ValueError):
        TTLCache(ttl_seconds=0)


def test_cache_disabled_returns_none() -> None:
    settings = Settings(cache=CacheSettings(enabled=False))
    assert get_translation_cache(settings) is None


def test_translator_uses_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_complete(system_prompt, user_prompt, **kwargs):
        calls.append(user_prompt)
        return "partner_contract"

    monkeypatch.setattr("services.translator.complete", fake_complete)

    settings = Settings(cache=CacheSettings(enabled=True, ttl_seconds=60))

    assert translate_identifier("ДоговорыКонтрагентов", settings=settings) == "partner_contract"
    assert translate_identifier("ДоговорыКонтрагентов", settings=settings) == "partner_contract"
    assert len(calls) == 1  # второй запрос обслужен кешем

    translate_identifier("ЗаказыПокупателей", settings=settings)
    assert len(calls) == 2


def test_cache_key_is_trimmed(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        "services.translator.complete",
        lambda *args, **kwargs: calls.append("call") or "partner_contract",
    )
    settings = Settings(cache=CacheSettings(enabled=True, ttl_seconds=60))

    translate_identifier("ДоговорыКонтрагентов", settings=settings)
    translate_identifier("  ДоговорыКонтрагентов  ", settings=settings)

    assert len(calls) == 1


def test_cache_disabled_calls_llm_every_time(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        "services.translator.complete",
        lambda *args, **kwargs: calls.append("call") or "partner_contract",
    )
    settings = Settings(cache=CacheSettings(enabled=False))

    translate_identifier("ДоговорыКонтрагентов", settings=settings)
    translate_identifier("ДоговорыКонтрагентов", settings=settings)

    assert len(calls) == 2


def test_errors_are_not_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def failing_complete(system_prompt, user_prompt, **kwargs):
        calls.append(user_prompt)
        return "   "

    monkeypatch.setattr("services.translator.complete", failing_complete)
    settings = Settings(cache=CacheSettings(enabled=True, ttl_seconds=60))

    for _ in range(2):
        with pytest.raises(Exception, match="без пригодного перевода"):
            translate_identifier("ДоговорыКонтрагентов", settings=settings)

    assert len(calls) == 2
