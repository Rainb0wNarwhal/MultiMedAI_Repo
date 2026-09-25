from __future__ import annotations

import os
from typing import Any

# Single switch for which backend answers questions.
#   MULTIMEDAI_LLM_BACKEND=cloud  -> src/cloud_client.py (Groq API, default for now)
#   MULTIMEDAI_LLM_BACKEND=local  -> src/ollama_client.py (local Ollama, for later)
#
# Callers (resolve_coach.py, resolve_coach_ui.py) should import generate_answer
# from here instead of importing a specific backend directly, so switching back
# to local later is a one-line env var change, not a code change.
BACKEND = os.environ.get("MULTIMEDAI_LLM_BACKEND", "cloud").strip().lower()


def generate_answer(question: str, facts: list[str], entries: list[dict[str, Any]], **kwargs: Any) -> str:
    if BACKEND == "local":
        from ollama_client import generate_answer as _generate

        kwargs.setdefault("model", "llama3.2:3b")
        return _generate(question, facts, entries, **kwargs)

    if BACKEND != "cloud":
        return (
            f"Unknown MULTIMEDAI_LLM_BACKEND value '{BACKEND}'. "
            "Use 'cloud' or 'local'."
        )

    from cloud_client import generate_answer as _generate

    return _generate(question, facts, entries, **kwargs)


def backend_label() -> str:
    return "cloud (Groq)" if BACKEND != "local" else "local (Ollama)"
