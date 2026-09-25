from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

# Groq's free tier (as of testing): no credit card required, OpenAI-compatible
# chat completions endpoint. Get a key at https://console.groq.com/keys and set
# it as the GROQ_API_KEY environment variable before running the coach.
DEFAULT_MODEL = "llama-3.3-70b-versatile"
DEFAULT_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"


def _build_prompt(question: str, facts: list[str], entries: list[dict[str, Any]]) -> str:
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
    return (
        "You are a DaVinci Resolve coach. Answer from the provided entries and "
        "factual project context only. You have read-only project access: never "
        "claim to have changed the project or offer to execute an action. You may "
        "explain the manual UI steps the user can choose to take. Keep the answer "
        "practical and concise.\n\n"
        f"Question: {question}\n\n"
        f"Project facts:\n- {fact_lines}\n\n"
        f"Relevant knowledge entries:\n{json.dumps(knowledge, ensure_ascii=False, indent=2)}\n\n"
        "Provide a short diagnosis, the first thing to check, and a manual "
        "Resolve UI path, using only those entries."
    )


def generate_answer(
    question: str,
    facts: list[str],
    entries: list[dict[str, Any]],
    model: str = DEFAULT_MODEL,
    api_key: str | None = None,
    endpoint: str = DEFAULT_ENDPOINT,
) -> str:
    """Call Groq's cloud API (OpenAI-compatible) and return the model's text response."""
    if not entries:
        return (
            "I couldn't find a strong match in the knowledge base. "
            "Please check the current shot and ask a more specific question."
        )

    key = api_key or os.environ.get("GROQ_API_KEY")
    if not key:
        return (
            "No cloud API key found. Set the GROQ_API_KEY environment variable "
            "(get a free key at https://console.groq.com/keys) and try again."
        )

    prompt = _build_prompt(question, facts, entries)
    payload = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        endpoint,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8")
            data = json.loads(body)
            choices = data.get("choices") or []
            if not choices:
                return "No answer generated."
            return str(choices[0]["message"]["content"]).strip() or "No answer generated."
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        if exc.code == 401:
            return "Cloud API call failed: invalid or missing GROQ_API_KEY. Check your key at https://console.groq.com/keys."
        if exc.code == 429:
            return "Cloud API call failed: rate limit hit on the free tier. Wait a moment and try again."
        return f"Cloud API call failed ({exc.code}): {detail}"
    except Exception as exc:  # pragma: no cover - network dependent
        return f"Cloud API call failed: {exc}"


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
