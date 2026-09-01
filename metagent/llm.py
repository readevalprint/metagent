"""Pluggable LLM backends.

Set METAGENT_API_KEY + METAGENT_BASE_URL + METAGENT_MODEL, or pass them
via Flags. OpenAI-compatible servers (OpenAI, xAI Grok, Groq, vLLM,
Ollama, llama.cpp) all work through OpenAICompatLLM.
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Any

import httpx


class LLM(ABC):
    """Minimal completion interface used by Evolve.prompt."""

    model: str = "dummy"

    @abstractmethod
    def complete(self, system: str, user: str, **kwargs: Any) -> str:
        raise NotImplementedError


class DummyLLM(LLM):
    """Offline backend so the harness is usable without an API key.

    Emits a tiny deterministic skill that records the call. Real work
    requires OpenAICompatLLM (or any LLM subclass you inject).
    """

    model = "dummy"

    def complete(self, system: str, user: str, **kwargs: Any) -> str:
        if "You are debugging a live metagent agent" in system:
            return '{"tool": "raise"}'
        if "You guide an instrumented method" in system:
            return '{"op": "continue"}'
        if "You refine method specifications" in system:
            marker = "CURRENT SPEC:"
            if marker in user:
                return user.split(marker, 1)[1].strip() or "Do the described work."
            return "Do the described work."
        if "Decide the next action" in system:
            return '{"op": "done", "result": "dummy-complete"}'
        name = "skill"
        for line in user.splitlines():
            line = line.strip()
            if line.startswith("def "):
                name = line[4:].split("(")[0].strip()
                break
            if line.startswith("METHOD:"):
                name = line.split(":", 1)[1].strip()
                break
        return (
            f"def {name}(self, *args, **kwargs):\n"
            f"    return {{'skill': {name!r}, 'args': args, 'kwargs': kwargs}}\n"
        )


class OpenAICompatLLM(LLM):
    """Chat Completions client for any OpenAI-compatible gateway."""

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 90.0,
    ) -> None:
        self.model = model
        self.api_key = api_key or os.environ.get("METAGENT_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
        self.base_url = (base_url or os.environ.get("METAGENT_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.timeout = timeout

    def complete(self, system: str, user: str, **kwargs: Any) -> str:
        if not self.api_key:
            raise RuntimeError(
                "No API key. Set METAGENT_API_KEY / OPENAI_API_KEY, "
                "pass api_key=..., or construct Evolve with dummy=True."
            )
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "temperature": kwargs.get("temperature", 0.2),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"Unexpected LLM payload: {json.dumps(data)[:400]}") from exc


def build_llm(flags) -> LLM:
    if flags.dummy or flags.model in {"dummy", "none", "offline"}:
        return DummyLLM()
    if not flags.api_key and not os.environ.get("METAGENT_API_KEY"):
        return DummyLLM()
    return OpenAICompatLLM(
        model=flags.model,
        api_key=flags.api_key,
        base_url=flags.base_url,
    )
