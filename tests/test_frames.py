"""PTS tests prevent VFR timing from being silently replaced by average FPS."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from sample_frames import choose_frames, frame_times


class FrameTests(unittest.TestCase):
    def test_vfr_keeps_actual_decoder_indices_and_pts(self):
        rows = frame_times([{"best_effort_timestamp_time": x} for x in (7.0, 7.04, 7.15, 7.19)])
        selected = choose_frames(rows, [0.13])
        self.assertEqual([x[0] for x in selected], [0, 2, 3])
        self.assertAlmostEqual(selected[1][2], 0.15)
        self.assertEqual(selected[1][1], 7.15)

    def test_first_and_last_frames_are_always_included(self):
        rows = frame_times([{"best_effort_timestamp_time": x} for x in (0, 1, 2)])
        self.assertEqual([x[0] for x in choose_frames(rows, [])], [0, 2])

    def test_missing_nonfinite_or_decreasing_pts_fail_closed(self):
        for values in [[], [None], [float("nan")], [0, 0], [1, 0]]:
            with self.subTest(values=values), self.assertRaises(ValueError):
                frame_times([{"best_effort_timestamp_time": x} for x in values])

    def test_timestamp_outside_last_frame_is_rejected(self):
        rows = frame_times([{"best_effort_timestamp_time": x} for x in (0, 1)])
        for value in [-1, 2, float("inf")]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                choose_frames(rows, [value])


if __name__ == "__main__":
    unittest.main()
