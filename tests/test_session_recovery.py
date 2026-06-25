import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import soundfile as sf
import numpy as np

from omnivoice.session_recovery import SessionManager
from omnivoice_qt_app import GenerationWorker, OmniVoiceQtWindow, _auto_select_reference_segment


class SessionRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.manager = SessionManager(self.root)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_session_persists_manifest(self):
        payload = {
            "text": "Chunk one, chunk two",
            "language": None,
            "generation_config": {
                "num_step": 16,
                "guidance_scale": 1.5,
                "denoise": True,
                "preprocess_prompt": True,
                "postprocess_output": True,
            },
        }
        session_id, manifest = self.manager.create_session("clone", payload, ["Chunk one", "Chunk two"])
        self.assertEqual(manifest["session_id"], session_id)
        manifest_path = self.root / session_id / "manifest.json"
        self.assertTrue(manifest_path.exists())
        loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(loaded["schema_version"], 1)
        self.assertEqual(len(loaded["chunks"]), 2)

    def test_recoverable_session_listing_filters_completed(self):
        payload = {
            "text": "abc",
            "language": None,
            "generation_config": {},
        }
        session_id, _ = self.manager.create_session("design", payload, ["a"])
        self.manager.mark_finished(session_id, "completed", 3.0)
        sessions = self.manager.list_recoverable_sessions()
        self.assertEqual(sessions, [])

    def test_delete_session_removes_folder(self):
        payload = {
            "text": "abc",
            "language": None,
            "generation_config": {},
        }
        session_id, _ = self.manager.create_session("design", payload, ["a"])
        self.assertTrue((self.root / session_id).exists())
        self.manager.delete_session(session_id)
        self.assertFalse((self.root / session_id).exists())

    def test_recoverable_listing_includes_elapsed_and_completed_chunks(self):
        payload = {
            "text": "Chunk one, chunk two",
            "language": None,
            "generation_config": {},
        }
        session_id, _ = self.manager.create_session("clone", payload, ["Chunk one", "Chunk two"])
        chunk_path = self.manager.chunk_output_path(session_id, 0)
        sf.write(str(chunk_path), np.zeros(2400, dtype=np.float32), 24000)
        self.manager.mark_chunk_complete(session_id, 0, str(chunk_path), 12.5)
        sessions = self.manager.list_recoverable_sessions()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["completed_chunks"], 1)
        self.assertEqual(sessions[0]["total_chunks"], 2)
        self.assertAlmostEqual(sessions[0]["elapsed_active_s"], 12.5)
        self.assertEqual(sessions[0]["first_incomplete_index"], 1)

    def test_mark_running_and_finished_preserve_elapsed(self):
        payload = {
            "text": "Chunk one",
            "language": None,
            "generation_config": {},
        }
        session_id, _ = self.manager.create_session("design", payload, ["Chunk one"])
        running = self.manager.mark_running(session_id, 8.0)
        self.assertEqual(running["status"], "running")
        self.assertAlmostEqual(running["timing"]["elapsed_active_s"], 8.0)
        self.assertIsNotNone(running["timing"]["run_started_at"])
        finished = self.manager.mark_finished(session_id, "failed", 15.25, error="boom")
        self.assertEqual(finished["status"], "failed")
        self.assertAlmostEqual(finished["timing"]["elapsed_active_s"], 15.25)
        self.assertIsNone(finished["timing"]["run_started_at"])
        self.assertEqual(finished["error"], "boom")


class GenerationWorkerThrottleTests(unittest.TestCase):
    def _worker(self):
        model = SimpleNamespace(device="cuda:0", sampling_rate=24000)
        return GenerationWorker(model, "clone", {"text": "hello"}, None)

    def test_soft_throttle_skips_non_cuda_runs(self):
        worker = self._worker()
        with patch.object(worker, "_is_cuda_run", return_value=False), patch("omnivoice_qt_app.time.sleep") as sleep_mock:
            worker._soft_throttle_cuda(3.0)
        sleep_mock.assert_not_called()

    def test_soft_throttle_applies_base_cooldown_for_cuda(self):
        worker = self._worker()
        with patch.object(worker, "_is_cuda_run", return_value=True), \
             patch("omnivoice_qt_app.time.sleep") as sleep_mock, \
             patch("omnivoice_qt_app.torch.cuda.synchronize"), \
             patch("omnivoice_qt_app.torch.cuda.empty_cache"):
            worker._soft_throttle_cuda(3.0)
        sleep_mock.assert_called_once_with(0.02)

    def test_soft_throttle_adds_extra_cooldown_for_very_long_chunks(self):
        worker = self._worker()
        with patch.object(worker, "_is_cuda_run", return_value=True), \
             patch("omnivoice_qt_app.time.sleep") as sleep_mock, \
             patch("omnivoice_qt_app.torch.cuda.synchronize"), \
             patch("omnivoice_qt_app.torch.cuda.empty_cache"):
            worker._soft_throttle_cuda(10.5)
        sleep_mock.assert_called_once_with(0.06)


class AutoReferenceSelectionTests(unittest.TestCase):
    def test_auto_selector_prefers_long_stable_voice_region(self):
        sr = 24000
        silence = np.zeros(int(sr * 3.0), dtype=np.float32)
        t_long = np.linspace(0, 12.0, int(sr * 12.0), endpoint=False)
        stable_voice = (
            0.22 * np.sin(2 * np.pi * 220 * t_long)
            + 0.11 * np.sin(2 * np.pi * 440 * t_long)
        ).astype(np.float32)
        t_short = np.linspace(0, 4.0, int(sr * 4.0), endpoint=False)
        short_voice = (
            0.12 * np.sin(2 * np.pi * 180 * t_short)
            + 0.03 * np.random.default_rng(0).standard_normal(t_short.shape[0])
        ).astype(np.float32)
        audio = np.concatenate([silence, stable_voice, silence[: sr], short_voice])

        selection = _auto_select_reference_segment(audio, sr)

        self.assertGreaterEqual(selection["start_sec"], 2.0)
        self.assertLessEqual(selection["start_sec"], 6.5)
        self.assertGreaterEqual(selection["end_sec"], 11.0)
        self.assertLessEqual(selection["end_sec"], 16.5)
        self.assertIn("giọng", selection["reason"])

    def test_auto_pick_updates_trim_controls_and_status(self):
        class DummyField:
            def __init__(self, value=None):
                self._value = value
            def text(self):
                return self._value
            def setValue(self, value):
                self._value = value
            def value(self):
                return self._value

        class DummyLabel:
            def __init__(self):
                self.value = ""
            def setText(self, value):
                self.value = value

        class DummyWindow:
            pass

        with tempfile.TemporaryDirectory() as temp_dir:
            sr = 24000
            t = np.linspace(0, 12.0, int(sr * 12.0), endpoint=False)
            audio = (
                np.concatenate(
                    [
                        np.zeros(int(sr * 2.0), dtype=np.float32),
                        0.2 * np.sin(2 * np.pi * 220 * t[: int(sr * 8.0)]),
                        np.zeros(int(sr * 2.0), dtype=np.float32),
                    ]
                )
            ).astype(np.float32)
            source = Path(temp_dir) / "reference.wav"
            sf.write(str(source), audio, sr)

            win = DummyWindow()
            win.clone_file = DummyField(str(source))
            win.trim_start = DummyField(0.0)
            win.trim_end = DummyField(8.0)
            win.auto_trim_info = DummyLabel()
            win.clone_status = DummyLabel()
            win._resolve_reference_working_source = lambda source_path: source_path
            win._sync_range_from_spin = lambda: None
            win._apply_reference_segment_selection = lambda start, end, reason=None: OmniVoiceQtWindow._apply_reference_segment_selection(win, start, end, reason)

            OmniVoiceQtWindow._auto_pick_reference_segment(win)

            self.assertGreater(win.trim_end.value(), win.trim_start.value())
            self.assertIn("Tự chọn:", win.auto_trim_info.value)
            self.assertIn("Đã tự chọn đoạn mẫu", win.clone_status.value)


if __name__ == "__main__":
    unittest.main()
