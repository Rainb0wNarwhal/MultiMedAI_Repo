from __future__ import annotations

import os
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - installed in requirements.txt
    raise RuntimeError(
        "PyYAML is required. Install dependencies with: pip install -r requirements.txt"
    ) from exc


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.lower().replace("\n", " ").split())


def load_entries(yaml_path: str | None = None) -> list[dict[str, Any]]:
    """Load all YAML entries under content/entries and return them as dicts."""
    if yaml_path is None:
        yaml_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "content", "entries"))

    entries: list[dict[str, Any]] = []
    if not os.path.isdir(yaml_path):
        return entries

    for filename in sorted(os.listdir(yaml_path)):
        if not filename.endswith(".yaml") and not filename.endswith(".yml"):
            continue
        full_path = os.path.join(yaml_path, filename)
        with open(full_path, "r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle)
        if isinstance(loaded, list):
            entries.extend(item for item in loaded if isinstance(item, dict))
    return entries


def _entry_score(question_text: str, facts_text: str, entry: dict[str, Any]) -> tuple[int, str]:
    score = 0
    reasons: list[str] = []

    question = _normalize_text(question_text)
    facts = _normalize_text(facts_text)

    symptom_phrases = entry.get("symptom_phrases") or []
    for phrase in symptom_phrases:
        norm = _normalize_text(phrase)
        if not norm:
            continue
        if norm in question or question.find(norm) >= 0:
            score += 4
            reasons.append(f"symptom:{norm}")
        elif any(word in question for word in norm.split() if len(word) > 3):
            score += 2
            reasons.append(f"symptom-partial:{norm}")

    project_signals = entry.get("project_state_signals") or []
    for signal in project_signals:
        norm = _normalize_text(signal)
        if not norm:
            continue
        if norm in facts:
            score += 3
            reasons.append(f"signal:{norm}")

    category = _normalize_text(entry.get("category"))
    if category and category in question:
        score += 2
        reasons.append(f"category:{category}")

    title = _normalize_text(entry.get("id"))
    if title and title in question:
        score += 1
        reasons.append(f"id:{title}")

    page = _normalize_text(entry.get("page"))
    if page and f"user is on the {page} page" in facts:
        score += 3
        reasons.append(f"page:{page}")

    return score, ", ".join(reasons)


def find_best_entries(question: str, facts: list[str], yaml_path: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
    """Return the best-matching entries ordered highest-first."""
    entries = load_entries(yaml_path)
    if not entries:
        return []

    facts_text = " ".join(facts)
    scored: list[tuple[int, dict[str, Any], str]] = []
    for entry in entries:
        score, reasons = _entry_score(question, facts_text, entry)
        if score > 0:
            scored.append((score, entry, reasons))

    scored.sort(key=lambda item: item[0], reverse=True)
    ranked = [entry for _, entry, _ in scored[:limit]]
    return ranked
