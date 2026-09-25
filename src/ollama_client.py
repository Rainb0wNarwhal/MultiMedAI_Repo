from __future__ import annotations

import json
import os
import urllib.request
from typing import Any


def generate_answer(
    question: str,
    facts: list[str],
    entries: list[dict[str, Any]],
    model: str = "llama3.2:3b",
    host: str = "http://localhost:11434",
) -> str:
    """Call the local Ollama server and return the model's text response."""
    if not entries:
        return (
            "I couldn't find a strong match in the local knowledge base. "
            "Please check the current shot and ask a more specific question."
        )

    knowledge = []
    for entry in entries:
        knowledge.append(
            {
                "id": entry.get("id"),
                "category": entry.get("category"),
                "symptom_phrases": entry.get("symptom_phrases", []),
                "diagnosis": entry.get("diagnosis"),
                "tool_or_technique": entry.get("tool_or_technique"),
                "explanation": entry.get("explanation"),
                "step_pointer": entry.get("step_pointer"),
                "manual_reference": entry.get("manual_reference"),
            }
        )

    fact_lines = "\n- ".join(facts) if facts else "No project facts available."
    prompt = (
        "You are a DaVinci Resolve coach for the Color and Edit pages. "
        "Answer from the provided entries and factual project context only. "
        "You have read-only project access: never claim to have changed the "
        "project or offer to execute an action. You may explain the manual UI "
        "steps the user can choose to take. "
        "Keep the answer practical and concise.\n\n"
        f"Question: {question}\n\n"
        f"Project facts:\n- {fact_lines}\n\n"
        f"Relevant knowledge entries:\n{json.dumps(knowledge, ensure_ascii=False, indent=2)}\n\n"
        "Provide a short diagnosis, the first thing to check, and a manual "
        "Resolve UI path, using only those entries."
    )

    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
    }).encode("utf-8")

    url = f"{host}/api/generate"
    request = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = response.read().decode("utf-8")
            data = json.loads(body)
            return str(data.get("response", "")).strip() or "No answer generated."
    except Exception as exc:  # pragma: no cover - depends on local model install
        return (
            f"Local model call failed: {exc}. "
            f"Make sure Ollama is installed and running with: ollama pull {model}"
        )


if __name__ == "__main__":
    answer = generate_answer(
        question="The skin looks too warm and flat.",
        facts=["user is on the Color page", "current clip: Shot_023", "node graph has 4 node(s)"],
        entries=[
            {
                "id": "skin_tone_overly_red",
                "category": "skin-tone",
                "symptom_phrases": ["skin looks red", "faces look too warm"],
                "diagnosis": "Skin hue is pushed too warm.",
                "tool_or_technique": "Vectorscope skin line + Hue vs Hue",
                "explanation": "Check skin tone line and rotate the hue back toward neutral.",
                "step_pointer": "Color page -> Vectorscope -> Curves",
                "manual_reference": "Using Scopes",
            }
        ],
    )
    print(answer)
