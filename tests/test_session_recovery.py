import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import soundfile as sf
import numpy as np

from omnivoice.session_recovery import SessionManager
from omnivoice_qt_app import GenerationWorker


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
        sleep_mock.assert_called_once_with(0.08)

    def test_soft_throttle_adds_extra_cooldown_for_long_chunks(self):
        worker = self._worker()
        with patch.object(worker, "_is_cuda_run", return_value=True), \
             patch("omnivoice_qt_app.time.sleep") as sleep_mock, \
             patch("omnivoice_qt_app.torch.cuda.synchronize"), \
             patch("omnivoice_qt_app.torch.cuda.empty_cache"):
            worker._soft_throttle_cuda(8.5)
        sleep_mock.assert_called_once_with(0.2)


if __name__ == "__main__":
    unittest.main()
