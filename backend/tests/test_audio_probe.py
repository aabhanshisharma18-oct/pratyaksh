import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import audio_probe


class AudioProbeTests(unittest.TestCase):
    def test_short_audio_is_repeated_to_model_length(self):
        source = np.arange(16000, dtype=np.float32)
        prepared = audio_probe.prepare_aasist_input(source)
        self.assertEqual(len(prepared), audio_probe.MODEL_SAMPLES)
        np.testing.assert_array_equal(prepared[:16000], source)
        np.testing.assert_array_equal(prepared[16000:32000], source)

    def test_long_audio_uses_first_model_window(self):
        source = np.arange(70000, dtype=np.float32)
        prepared = audio_probe.prepare_aasist_input(source)
        np.testing.assert_array_equal(prepared, source[:audio_probe.MODEL_SAMPLES])

    def test_decode_failure_is_not_a_model_result(self):
        completed = type("Result", (), {"returncode": 1, "stdout": b""})()
        with patch.object(audio_probe.subprocess, "run", return_value=completed):
            with self.assertRaises(audio_probe.AudioProbeError):
                audio_probe.decode_audio(b"not-audio")


if __name__ == "__main__":
    unittest.main()
