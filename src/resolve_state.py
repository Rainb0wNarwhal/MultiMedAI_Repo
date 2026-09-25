"""
Read-only layer over DaVinci Resolve's scripting API.

CORE RULE: this module NEVER calls a write method on the Resolve API objects
(no SetLUT, SetNodeEnabled, ApplyGradeFromDRX, SetClipProperty, etc.). It only
reads project/timeline/node state and converts it into short factual
statements the coach engine can use to narrow down which knowledge-base entry
applies. If you find yourself wanting to add a Set*/Add*/Delete*/Apply* call
here, stop - that belongs nowhere in this product.

All method names below (GetProjectManager, GetCurrentProject,
GetCurrentTimeline, GetCurrentVideoItem, GetNodeGraph, GetNumNodes,
GetNodeLabel, GetToolsInNode, GetLUT) are from Blackmagic's official
scripting documentation, bundled with Resolve at:
  Windows: C:\\ProgramData\\Blackmagic Design\\DaVinci Resolve\\Support\\Developer\\Scripting\\README.txt
  macOS:   /Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/README.txt
Verify against your installed version's copy of that file before shipping -
Blackmagic has changed/removed undocumented behavior between versions before,
so treat anything not in that README as unstable.

NOT YET VERIFIED IN THIS STUB (check against the README.txt above once you're
running this against a live Resolve instance):
  - Exact structure of what GetToolsInNode returns for Color page primary
    wheels vs qualifiers vs power windows - the doc says "list of tools used
    in the node" but doesn't fully enumerate tool name strings.
  - Whether GetCurrentVideoItem() on the Color page reliably returns the same
    item as what's active in the node graph, or whether you need a separate
    call for Color-page-specific state.
"""

from __future__ import annotations

import os
import sys
import platform
from dataclasses import dataclass, field

from edit_state import EditStateSnapshot, get_edit_state_snapshot


def _safe_read(method: object, *args: object, default: object = None) -> object:
    """Read an optional Resolve API value without breaking the entire snapshot."""
    if not callable(method):
        return default
    try:
        return method(*args)
    except Exception:
        return default


def _configure_environment() -> None:
    """
    Sets the environment variables Resolve's scripting API needs to be
    importable. Must run before `import DaVinciResolveScript`.

    Paths are from Blackmagic's official README.txt, reproduced across
    multiple archived copies of the scripting docs (see docs/authoring-guide.md
    for source links). Verify these match your actual install location -
    they can differ for non-default install paths.
    """
    system = platform.system()

    if system == "Windows":
        api_path = r"%PROGRAMDATA%\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting"
        lib_path = r"C:\Program Files\Blackmagic Design\DaVinci Resolve\fusionscript.dll"
    elif system == "Darwin":
        api_path = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
        lib_path = "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"
    else:  # Linux
        api_path = "/opt/resolve/Developer/Scripting"
        lib_path = "/opt/resolve/libs/Fusion/fusionscript.so"

    api_path = os.path.expandvars(api_path)
    modules_path = os.path.join(api_path, "Modules")

    os.environ["RESOLVE_SCRIPT_API"] = api_path
    os.environ["RESOLVE_SCRIPT_LIB"] = lib_path
    if modules_path not in sys.path:
        sys.path.append(modules_path)


def connect() -> "object | None":
    """
    Connects to a running Resolve instance. Returns the top-level `resolve`
    object, or None if Resolve isn't running or scripting access is disabled.

    Two ways this gets run, and they behave differently:

    1. From INSIDE Resolve (Workspace > Scripts menu) - this is the required
       path on DaVinci Resolve FREE. Resolve's own Python environment already
       has DaVinciResolveScript importable and a `resolve` object available
       via the `bmd` module - no env var setup needed. This function tries
       a plain import first for this case.

    2. As an EXTERNAL process (`python src/resolve_state.py` from a normal
       terminal) - this is Studio-only. Resolve 19.1+ blocks this entirely on
       Free; earlier Free versions were unreliable for it even before that
       became an official restriction. If you're on Free (confirmed via
       DaVinci Resolve > About DaVinci Resolve), skip straight to the Scripts
       menu approach in README.md rather than debugging this path.
    """
    try:
        # Case 1: running from inside Resolve's own console/Scripts menu.
        # The module is already importable, no env vars needed.
        import DaVinciResolveScript as dvr_script  # type: ignore
    except ImportError:
        # Case 2: running as an external process. Needs env vars pointed at
        # Resolve's bundled scripting bridge. Studio required for this to
        # actually connect.
        _configure_environment()
        try:
            import DaVinciResolveScript as dvr_script  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "Could not import DaVinciResolveScript either directly or "
                "via env-configured path. If you're on DaVinci Resolve FREE, "
                "this script needs to be run from inside Resolve's own "
                "Workspace > Scripts menu, not from an external terminal - "
                "see README.md 'Running on Resolve Free' section. If you're "
                "on Studio, confirm RESOLVE_SCRIPT_API/RESOLVE_SCRIPT_LIB "
                "paths in _configure_environment() match your install."
            ) from e

    resolve = dvr_script.scriptapp("Resolve")
    return resolve  # None if Resolve isn't running or scripting is disabled


@dataclass
class NodeSummary:
    index: int
    label: str
    tools: list[str] = field(default_factory=list)
    lut: str | None = None


@dataclass
class ProjectStateSnapshot:
    """
    The structured output this module produces. This is what gets handed to
    the coach engine alongside the user's typed question - short factual
    statements, not raw API objects.
    """
    current_page: str | None
    project_name: str | None
    timeline_name: str | None
    current_clip_name: str | None
    node_count: int
    nodes: list[NodeSummary]
    edit: EditStateSnapshot | None = None

    def as_facts(self) -> list[str]:
        """
        Converts the snapshot into short natural-language facts, formatted
        the way they'd be fed into the coach engine's context alongside
        retrieved knowledge-base entries. This is the piece that should get
        matched against each entry's `project_state_signals` field.
        """
        facts = []
        if self.current_page:
            facts.append(f"user is on the {self.current_page} page")
        if self.timeline_name:
            facts.append(f"current timeline: {self.timeline_name}")
        if self.current_clip_name:
            facts.append(f"current clip: {self.current_clip_name}")
        facts.append(f"node graph has {self.node_count} node(s)")
        for node in self.nodes:
            tool_desc = ", ".join(node.tools) if node.tools else "no tools applied"
            facts.append(f"node {node.index} ('{node.label}'): {tool_desc}")
            if node.lut:
                facts.append(f"node {node.index} has LUT applied: {node.lut}")
        if self.edit:
            facts.extend(self.edit.as_facts())
        return facts


def get_project_state_snapshot(resolve: object) -> ProjectStateSnapshot | None:
    """
    Reads current page, project, timeline, current clip, and node graph
    state. Returns None if there's no open project/timeline - the coach
    engine should fall back to answering from the question text alone in
    that case, not error out.

    Every call in this function is a Get* method. Do not add Set*/Add*/
    Delete*/Apply* calls here - see module docstring.
    """
    current_page = resolve.GetCurrentPage()

    project_manager = resolve.GetProjectManager()
    project = project_manager.GetCurrentProject() if project_manager else None
    if project is None:
        return None

    timeline = project.GetCurrentTimeline()
    if timeline is None:
        return ProjectStateSnapshot(
            current_page=current_page,
            project_name=project.GetName(),
            timeline_name=None,
            current_clip_name=None,
            node_count=0,
            nodes=[],
        )

    current_item = timeline.GetCurrentVideoItem()
    current_clip_name = current_item.GetName() if current_item else None

    edit_snapshot = get_edit_state_snapshot(timeline) if current_page == "edit" else None
    nodes: list[NodeSummary] = []
    node_count = 0

    # Resolve 18.6 documents these Color calls directly on TimelineItem.
    # GetNodeGraph/GetToolsInNode are not part of the installed public API and
    # can be absent in Resolve Free, so never use them here.
    if current_page == "color" and current_item is not None:
        raw_count = _safe_read(getattr(current_item, "GetNumNodes", None), default=0)
        node_count = raw_count if isinstance(raw_count, int) else 0
        for i in range(1, node_count + 1):  # node indices are 1-based
            label = _safe_read(getattr(current_item, "GetNodeLabel", None), i, default=f"Node {i}")
            lut = _safe_read(getattr(current_item, "GetLUT", None), i)
            nodes.append(
                NodeSummary(
                    index=i,
                    label=str(label or f"Node {i}"),
                    tools=[],
                    lut=str(lut) if lut else None,
                )
            )

    return ProjectStateSnapshot(
        current_page=current_page,
        project_name=project.GetName(),
        timeline_name=timeline.GetName(),
        current_clip_name=current_clip_name,
        node_count=node_count,
        nodes=nodes,
        edit=edit_snapshot,
    )


if __name__ == "__main__":
    # On DaVinci Resolve FREE (River's setup: Windows + Free): this file
    # will NOT work run as `python src/resolve_state.py` from a terminal.
    # Copy it into Resolve's Scripts folder instead and run it from
    # Resolve's Workspace > Scripts menu - see README.md.
    #
    # On Studio: this terminal invocation should work as-is, provided
    # Resolve is running with a project/timeline open and External
    # scripting is enabled in Preferences.
    resolve = connect()
    if resolve is None:
        print("Could not connect to Resolve. Is it running? "
              "On Resolve Free, this must be run from Resolve's own "
              "Workspace > Scripts menu, not this terminal - see README.md.")
    else:
        snapshot = get_project_state_snapshot(resolve)
        if snapshot is None:
            print("Connected, but no project/timeline is currently open.")
        else:
            for fact in snapshot.as_facts():
                print(fact)
