"""
Validates every YAML file in content/entries/ against the required schema.

Run this after authoring new entries, before feeding them into the embedding
pipeline. Catches missing fields, duplicate ids, and broken related_entries
references early - cheaper than debugging bad retrieval later.

Usage:
    python src/validate_entries.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

REQUIRED_FIELDS = {
    "id",
    "category",
    "symptom_phrases",
    "diagnosis",
    "tool_or_technique",
    "explanation",
    "step_pointer",
    "manual_reference",
}

OPTIONAL_FIELDS = {
    "page",
    "project_state_signals",
    "common_mistake",
    "related_entries",
}

VALID_CATEGORIES = {
    "skin-tone",
    "matching",
    "contrast",
    "saturation",
    "noise-artifacts",
    "node-structure",
    "tracking",
    "scopes-reading",
    "qualifiers-masks",
    "delivery",
    "editing-timeline",
    "editing-audio",
    "multicam",
    "media-management",
    "titles-subtitles",
}

ENTRIES_DIR = Path(__file__).resolve().parent.parent / "content" / "entries"


def load_all_entries() -> list[dict]:
    entries: list[dict] = []
    for path in sorted(ENTRIES_DIR.glob("*.yaml")):
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, list):
            raise ValueError(f"{path.name}: top-level YAML must be a list of entries")
        for entry in data:
            entry["_source_file"] = path.name
            entries.append(entry)
    return entries


def validate(entries: list[dict]) -> list[str]:
    errors: list[str] = []
    seen_ids: dict[str, str] = {}

    for entry in entries:
        eid = entry.get("id", "<missing id>")
        src = entry.get("_source_file", "<unknown file>")

        missing = REQUIRED_FIELDS - entry.keys()
        if missing:
            errors.append(f"[{src}] entry '{eid}': missing required fields {sorted(missing)}")

        unknown = set(entry.keys()) - REQUIRED_FIELDS - OPTIONAL_FIELDS - {"_source_file"}
        if unknown:
            errors.append(f"[{src}] entry '{eid}': unknown fields {sorted(unknown)}")

        category = entry.get("category")
        if category and category not in VALID_CATEGORIES:
            errors.append(
                f"[{src}] entry '{eid}': invalid category '{category}', "
                f"must be one of {sorted(VALID_CATEGORIES)}"
            )

        phrases = entry.get("symptom_phrases")
        if phrases is not None and (not isinstance(phrases, list) or len(phrases) == 0):
            errors.append(f"[{src}] entry '{eid}': symptom_phrases must be a non-empty list")

        if eid in seen_ids:
            errors.append(
                f"[{src}] entry '{eid}': duplicate id, first seen in {seen_ids[eid]}"
            )
        else:
            seen_ids[eid] = src

    # Second pass: check related_entries point to real ids
    for entry in entries:
        eid = entry.get("id", "<missing id>")
        src = entry.get("_source_file", "<unknown file>")
        for related in entry.get("related_entries", []) or []:
            if related not in seen_ids:
                errors.append(
                    f"[{src}] entry '{eid}': related_entries references unknown id '{related}'"
                )

    return errors


def main() -> int:
    if not ENTRIES_DIR.exists():
        print(f"No entries directory found at {ENTRIES_DIR}")
        return 1

    entries = load_all_entries()
    print(f"Loaded {len(entries)} entries from {ENTRIES_DIR}")

    errors = validate(entries)
    if errors:
        print(f"\n{len(errors)} problem(s) found:\n")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("All entries valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
