"""Floating, read-only Resolve AI Coach window for Workspace > Scripts > Utility."""

from __future__ import annotations

import os
import sys


def _find_project_root() -> str:
    env_root = os.environ.get("MULTIMEDAI_ROOT")
    if env_root and os.path.isdir(env_root):
        return os.path.abspath(env_root)

    script_path = globals().get("__file__") or (sys.argv[0] if sys.argv else "")
    script_dir = os.path.dirname(os.path.abspath(script_path)) if script_path else os.getcwd()
    candidates = [
        os.getcwd(),
        script_dir,
        os.path.dirname(script_dir),
        r"C:\MultiMedAI",
        os.path.expanduser(r"~\MultiMedAI"),
    ]
    for candidate in candidates:
        if (
            candidate
            and os.path.exists(os.path.join(candidate, "src", "resolve_state.py"))
            and os.path.isdir(os.path.join(candidate, "content", "entries"))
        ):
            return os.path.abspath(candidate)
    return os.path.abspath(r"C:\MultiMedAI")


PROJECT_ROOT = _find_project_root()
for path in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "src")):
    if path not in sys.path:
        sys.path.insert(0, path)

from ollama_client import generate_answer  # noqa: E402
from retriever import find_best_entries  # noqa: E402
from resolve_state import connect, get_project_state_snapshot  # noqa: E402


WINDOW_ID = "com.multimedai.resolve.Coach"


def _get_resolve_handle() -> object | None:
    handle = globals().get("resolve")
    if handle is not None:
        return handle
    app_handle = globals().get("app")
    get_resolve = getattr(app_handle, "GetResolve", None)
    return get_resolve() if callable(get_resolve) else None


def _context_summary(facts: list[str]) -> str:
    if not facts:
        return "No active project or timeline context."
    priority = [fact for fact in facts if fact.startswith("user is on") or fact.startswith("current timeline")]
    return " | ".join(priority) if priority else facts[0]


def main() -> None:
    fusion_handle = globals().get("fusion") or globals().get("fu")
    bmd_handle = globals().get("bmd")
    if fusion_handle is None or bmd_handle is None:
        print("Resolve UI bridge is unavailable. Launch this from Workspace > Scripts > Utility.")
        return

    ui = fusion_handle.UIManager
    dispatcher = bmd_handle.UIDispatcher(ui)
    existing = ui.FindWindow(WINDOW_ID)
    if existing:
        existing.Show()
        existing.Raise()
        return

    window = dispatcher.AddWindow(
        {
            "ID": WINDOW_ID,
            "WindowTitle": "Resolve AI Coach",
            "Geometry": [180, 180, 760, 640],
        },
        ui.VGroup(
            [
                ui.Label({"Text": "Resolve AI Coach", "StyleSheet": "font-size: 18px; font-weight: 600;"}),
                ui.Label({"ID": "Context", "Text": "Reading Resolve context…", "WordWrap": True}),
                ui.Label({"Text": "Ask about what you see in the current Color or Edit page:"}),
                ui.TextEdit(
                    {
                        "ID": "Question",
                        "PlaceholderText": "Example: My clip is in the timeline but the viewer is black.",
                        "AcceptRichText": False,
                        "MinimumSize": [0, 72],
                    }
                ),
                ui.HGroup(
                    {"Weight": 0},
                    [
                        ui.Button({"ID": "Ask", "Text": "Ask Coach", "Default": True}),
                        ui.Button({"ID": "Refresh", "Text": "Refresh Context"}),
                        ui.Button({"ID": "Clear", "Text": "Clear"}),
                        ui.HGap(0, 1),
                    ],
                ),
                ui.Label({"ID": "Status", "Text": "Ready.", "WordWrap": True}),
                ui.Label({"Text": "Coach guidance:"}),
                ui.TextEdit(
                    {
                        "ID": "Answer",
                        "ReadOnly": True,
                        "AcceptRichText": False,
                        "MinimumSize": [0, 260],
                    }
                ),
                ui.Label({"Text": "Retrieved knowledge entries:"}),
                ui.TextEdit(
                    {
                        "ID": "Sources",
                        "ReadOnly": True,
                        "AcceptRichText": False,
                        "MinimumSize": [0, 70],
                    }
                ),
            ]
        ),
    )
    items = window.GetItems()

    def read_context() -> tuple[object | None, list[str], str | None]:
        resolve_handle = _get_resolve_handle() or connect()
        if resolve_handle is None:
            return None, [], "Could not connect to Resolve. Run this from Workspace > Scripts > Utility."
        snapshot = get_project_state_snapshot(resolve_handle)
        if snapshot is None:
            return resolve_handle, [], "Open a project and timeline, then refresh context."
        return resolve_handle, snapshot.as_facts(), None

    def refresh_context(_event=None) -> None:
        _handle, facts, error = read_context()
        items["Context"].Text = _context_summary(facts) if not error else error
        items["Status"].Text = "Ready." if not error else error

    def ask_coach(_event=None) -> None:
        question = items["Question"].PlainText.strip()
        if not question:
            items["Status"].Text = "Type a question first."
            return

        _handle, facts, error = read_context()
        if error:
            items["Status"].Text = error
            items["Answer"].PlainText = ""
            items["Sources"].PlainText = ""
            return

        items["Context"].Text = _context_summary(facts)
        entries = find_best_entries(question, facts, os.path.join(PROJECT_ROOT, "content", "entries"), limit=5)
        if not entries:
            items["Status"].Text = "No strong local match found. Try a more specific Color or Edit question."
            items["Answer"].PlainText = (
                "I could not find a strong match in the local Color/Edit knowledge base. "
                "Try describing the visible symptom, the Resolve page, and what you expected to happen."
            )
            items["Sources"].PlainText = "No entries retrieved."
            return

        items["Status"].Text = "Thinking locally with Ollama…"
        items["Sources"].PlainText = "\n".join(
            f"• {entry.get('id')} — {entry.get('tool_or_technique')}" for entry in entries
        )
        items["Answer"].PlainText = generate_answer(question, facts, entries, model="llama3.2:3b")
        items["Status"].Text = "Ready. Guidance is informational; the coach has not changed your project."

    def clear(_event=None) -> None:
        items["Question"].PlainText = ""
        items["Answer"].PlainText = ""
        items["Sources"].PlainText = ""
        items["Status"].Text = "Ready."

    def close(_event=None) -> None:
        dispatcher.ExitLoop()

    window.On[WINDOW_ID].Close = close
    window.On["Ask"].Clicked = ask_coach
    window.On["Refresh"].Clicked = refresh_context
    window.On["Clear"].Clicked = clear
    refresh_context()
    window.Show()
    dispatcher.RunLoop()


if __name__ == "__main__":
    main()
