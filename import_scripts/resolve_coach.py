from __future__ import annotations

import os
import sys


def _find_project_root() -> str:
    """Resolve the repo root across local runs and Resolve's own Scripts menu.

    DaVinci Resolve may execute this file with no __file__ defined and with a
    working directory that is unrelated to the repo checkout. We therefore walk
    from the current script/argv location upward and also check the usual repo
    locations before falling back to the default workspace path.
    """
    env_root = os.environ.get("MULTIMEDAI_ROOT")
    if env_root and os.path.isdir(env_root):
        return os.path.abspath(env_root)

    raw_script_path = globals().get("__file__") or (sys.argv[0] if len(sys.argv) > 0 and sys.argv[0] else None)
    if raw_script_path:
        script_dir = os.path.dirname(os.path.abspath(raw_script_path))
    else:
        script_dir = os.getcwd()

    candidates: list[str] = []
    for candidate in [
        env_root,
        os.getcwd(),
        script_dir,
        os.path.dirname(script_dir),
        os.path.abspath(os.path.join(script_dir, "..")),
        r"C:\MultiMedAI",
        os.path.expanduser(r"~\MultiMedAI"),
    ]:
        if candidate and os.path.isdir(candidate) and candidate not in candidates:
            candidates.append(os.path.abspath(candidate))

    current = os.path.abspath(script_dir)
    seen: set[str] = set()
    while True:
        if current in seen:
            break
        seen.add(current)
        if current not in candidates:
            candidates.append(current)
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent

    for candidate in candidates:
        if not os.path.isdir(candidate):
            continue
        src_candidate = os.path.join(candidate, "src")
        content_candidate = os.path.join(candidate, "content", "entries")
        if os.path.exists(os.path.join(src_candidate, "resolve_state.py")) and os.path.isdir(content_candidate):
            return os.path.abspath(candidate)

    for candidate in (r"C:\MultiMedAI", os.path.expanduser(r"~\MultiMedAI")):
        if os.path.isdir(candidate):
            return os.path.abspath(candidate)

    fallback = os.path.abspath(os.path.join(script_dir, ".."))
    return fallback if os.path.isdir(fallback) else os.path.abspath(os.getcwd())


PROJECT_ROOT = _find_project_root()
for repo_path in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "src")):
    if os.path.isdir(repo_path) and repo_path not in sys.path:
        sys.path.insert(0, repo_path)

from llm_client import generate_answer  # noqa: E402
from retriever import find_best_entries  # noqa: E402
from resolve_state import connect, get_project_state_snapshot  # noqa: E402


def _get_resolve_handle() -> object | None:
    """Use Resolve's pre-created handle when this file runs from its menu."""
    handle = globals().get("resolve")
    if handle is not None:
        return handle

    app_handle = globals().get("app")
    get_resolve = getattr(app_handle, "GetResolve", None)
    return get_resolve() if callable(get_resolve) else None


def main() -> None:
    question = "".join(sys.argv[1:]) or "The skin looks too warm and flat."

    resolve_handle = _get_resolve_handle() or connect()
    if resolve_handle is None:
        print("Could not connect to Resolve. If using Resolve Free, run this from Workspace > Scripts inside Resolve.")
        return

    snapshot = get_project_state_snapshot(resolve_handle)
    if snapshot is None:
        print("Connected, but no project or timeline is open. Ask a question after opening a project.")
        return

    facts = snapshot.as_facts()
    yaml_dir = os.path.join(PROJECT_ROOT, "content", "entries")
    entries = find_best_entries(question, facts, yaml_dir, limit=5)

    print("Resolved project facts:")
    for fact in facts:
        print(f"- {fact}")

    if not entries:
        print("\nNo strong YAML match found.")
        print("Try asking about a more specific symptom like 'skin looks red' or 'looks flat'.")
        return

    print("\nTop matching entries:")
    for entry in entries:
        print(f"- {entry.get('id')} :: {entry.get('category')}")

    answer = generate_answer(question, facts, entries)
    print("\nCoach answer:")
    print(answer)


if __name__ == "__main__":
    main()
