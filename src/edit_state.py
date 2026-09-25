"""Read-only Edit-page facts derived from Resolve's documented Timeline API."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _read(method: Any, *args: Any, default: Any = None) -> Any:
    """Return a documented API value without making the snapshot brittle."""
    try:
        return method(*args)
    except Exception:
        return default


@dataclass
class TrackSummary:
    kind: str
    index: int
    name: str
    item_count: int
    enabled: bool | None
    locked: bool | None


@dataclass
class EditStateSnapshot:
    playhead_timecode: str | None
    current_clip_name: str | None
    current_clip_duration_frames: int | None
    video_tracks: list[TrackSummary] = field(default_factory=list)
    audio_tracks: list[TrackSummary] = field(default_factory=list)

    def as_facts(self) -> list[str]:
        facts: list[str] = []
        if self.playhead_timecode:
            facts.append(f"Edit: playhead timecode is {self.playhead_timecode}")
        if self.current_clip_name:
            duration = (
                f", duration {self.current_clip_duration_frames} frame(s)"
                if self.current_clip_duration_frames is not None
                else ""
            )
            facts.append(f"Edit: current timeline clip is {self.current_clip_name}{duration}")

        facts.append(
            f"Edit: timeline has {len(self.video_tracks)} video track(s) and "
            f"{len(self.audio_tracks)} audio track(s)"
        )
        for track in [*self.video_tracks, *self.audio_tracks]:
            state = "enabled" if track.enabled else "disabled" if track.enabled is not None else "unknown enabled state"
            lock_state = "locked" if track.locked else "unlocked" if track.locked is not None else "unknown lock state"
            facts.append(
                f"Edit: {track.kind} track {track.index} ('{track.name}') is {state}, "
                f"{lock_state}, and contains {track.item_count} clip(s)"
            )
        return facts


def _summarize_tracks(timeline: object, kind: str) -> list[TrackSummary]:
    count = _read(timeline.GetTrackCount, kind, default=0) or 0
    tracks: list[TrackSummary] = []
    for index in range(1, int(count) + 1):
        name = _read(timeline.GetTrackName, kind, index, default=f"{kind.title()} {index}")
        items = _read(timeline.GetItemListInTrack, kind, index, default=[]) or []
        enabled = _read(timeline.GetIsTrackEnabled, kind, index)
        locked = _read(timeline.GetIsTrackLocked, kind, index)
        tracks.append(
            TrackSummary(
                kind=kind,
                index=index,
                name=str(name or f"{kind.title()} {index}"),
                item_count=len(items),
                enabled=enabled if isinstance(enabled, bool) else None,
                locked=locked if isinstance(locked, bool) else None,
            )
        )
    return tracks


def get_edit_state_snapshot(timeline: object) -> EditStateSnapshot:
    """Read Edit facts only; this function never calls a mutating API method."""
    current_item = _read(timeline.GetCurrentVideoItem)
    current_name = _read(current_item.GetName) if current_item is not None else None
    current_duration = _read(current_item.GetDuration) if current_item is not None else None
    return EditStateSnapshot(
        playhead_timecode=_read(timeline.GetCurrentTimecode),
        current_clip_name=str(current_name) if current_name else None,
        current_clip_duration_frames=int(current_duration) if isinstance(current_duration, int) else None,
        video_tracks=_summarize_tracks(timeline, "video"),
        audio_tracks=_summarize_tracks(timeline, "audio"),
    )
