from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from edit_state import get_edit_state_snapshot


class FakeItem:
    def GetName(self):
        return "Opening still"

    def GetDuration(self):
        return 120


class FakeTimeline:
    def GetCurrentTimecode(self):
        return "01:00:01:00"

    def GetCurrentVideoItem(self):
        return FakeItem()

    def GetTrackCount(self, kind):
        return {"video": 1, "audio": 1}[kind]

    def GetTrackName(self, kind, index):
        return f"{kind.title()} {index}"

    def GetItemListInTrack(self, kind, index):
        return [object()] if kind == "video" else []

    def GetIsTrackEnabled(self, kind, index):
        return kind == "audio"

    def GetIsTrackLocked(self, kind, index):
        return False


class EditStateTests(unittest.TestCase):
    def test_snapshot_reports_track_state_and_current_clip(self):
        facts = get_edit_state_snapshot(FakeTimeline()).as_facts()
        self.assertIn("Edit: current timeline clip is Opening still, duration 120 frame(s)", facts)
        self.assertIn("Edit: video track 1 ('Video 1') is disabled, unlocked, and contains 1 clip(s)", facts)


if __name__ == "__main__":
    unittest.main()
