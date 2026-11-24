"""Работа с LLM: клиент API, промпты, разбор и валидация ответа модели.

Перевод выполняется через API LLM (провайдер и модель задаются в конфигурации).
"""

from llm.client import complete
from llm.errors import LLMError
from llm.prompts import SYSTEM_PROMPT, build_user_prompt

__all__ = ["SYSTEM_PROMPT", "build_user_prompt", "complete", "LLMError"]
