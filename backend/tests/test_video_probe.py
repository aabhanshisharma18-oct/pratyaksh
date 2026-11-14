import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from video_probe import VideoProbeError, VideoSampler


class VideoSamplerTests(unittest.TestCase):
    def test_timestamp_selection_uses_real_available_presentation_times(self):
        variable_rate_timestamps = [0, 41, 83, 140, 260, 510, 900, 1510, 2300, 3500, 4990]
        selected = VideoSampler._choose_timestamps(variable_rate_timestamps, 5000)
        self.assertEqual(len(selected), 3)
        self.assertTrue(all(value in variable_rate_timestamps for value in selected))
        self.assertEqual(selected, sorted(set(selected)))

    def test_timestamp_selection_rejects_missing_timing_information(self):
        with self.assertRaises(VideoProbeError):
            VideoSampler._choose_timestamps([], 5000)


if __name__ == "__main__":
    unittest.main()
