"""Тесты пост-обработки ответа LLM и валидации результата."""

from __future__ import annotations

import pytest

from llm.errors import LLMError
from services.normalizer import is_valid_snake_case, normalize_snake_case
from services.translator import translate_identifier


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("partner_contract", "partner_contract"),
        ("  partner_contract  ", "partner_contract"),
        ("partner   contract", "partner_contract"),
        ("partner\tcontract", "partner_contract"),
        ("partner\ncontract", "partner_contract"),
        ("partner\u00a0contract", "partner_contract"),
        ("Partner Contract", "partner_contract"),
        ("`Partner_Contracts`", "partner_contracts"),
        ("**partner_contract**", "partner_contract"),
        ("partner-contract.", "partner_contract"),
        ("partner__contract", "partner_contract"),
        ("partner_contract\n\nПояснение модели", "partner_contract"),
        ("the partner for contract", "partner_contract"),
        ("  ", ""),
        ("", ""),
        ("!!!", ""),
        ("ДоговорыКонтрагентов", ""),
    ],
)
def test_normalize_snake_case(raw: str, expected: str) -> None:
    assert normalize_snake_case(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        " thinkingразмышления</think>warehouse_stock",
        "<thinking>step by step</thinking>warehouse_stock",
        "<reasoning>x</reasoning>warehouse_stock",
        "<think>обрыв reasoning warehouse_stock",
    ],
)
def test_reasoning_is_stripped(raw: str) -> None:
    result = normalize_snake_case(raw)
    assert "think" not in result
    assert "reasoning" not in result


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("partner_contract", True),
        ("invoice2", True),
        ("", False),
        ("_partner", False),
        ("partner_", False),
        ("partner__contract", False),
        ("Partner_Contract", False),
        ("partner contract", False),
        ("партнёр", False),
    ],
)
def test_is_valid_snake_case(value: str, expected: bool) -> None:
    assert is_valid_snake_case(value) is expected


def test_empty_model_answer_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("services.translator.complete", lambda *args, **kwargs: "   ")
    with pytest.raises(LLMError, match="без пригодного перевода"):
        translate_identifier("ДоговорыКонтрагентов")


def test_model_answer_is_cleaned(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "services.translator.complete",
        lambda *args, **kwargs: "  **Partner   Contract**  ",
    )
    assert translate_identifier("ДоговорыКонтрагентов") == "partner_contract"
