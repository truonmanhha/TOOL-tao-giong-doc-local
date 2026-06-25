import json
import os
import shutil
import uuid
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path


SESSION_SCHEMA_VERSION = 1
RECOVERABLE_STATUSES = {"running", "interrupted", "failed", "cancelled"}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get_runtime_root() -> Path:
    project_root = Path(__file__).resolve().parent.parent
    runtime_root = project_root / ".omnivoice-runtime"
    runtime_root.mkdir(parents=True, exist_ok=True)
    return runtime_root


def get_temp_root() -> Path:
    temp_root = get_runtime_root() / "temp"
    temp_root.mkdir(parents=True, exist_ok=True)
    return temp_root


def get_sessions_root() -> Path:
    sessions_root = get_runtime_root() / "sessions"
    sessions_root.mkdir(parents=True, exist_ok=True)
    return sessions_root


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(content, encoding="utf-8")
    os.replace(temp_path, path)


def _copy_file_atomic(source: str, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_suffix(destination.suffix + ".tmp")
    shutil.copy2(source, temp_path)
    os.replace(temp_path, destination)
    return str(destination)


class SessionManager:
    def __init__(self, root: Path | None = None):
        self.root = Path(root or get_sessions_root())
        self.root.mkdir(parents=True, exist_ok=True)

    def _session_dir(self, session_id: str) -> Path:
        return self.root / session_id

    def _manifest_path(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "manifest.json"

    def _serialize_payload(self, payload: dict) -> dict:
        serialized = dict(payload)
        config = serialized.get("generation_config")
        if config is not None:
            if is_dataclass(config):
                serialized["generation_config"] = asdict(config)
            else:
                serialized["generation_config"] = {
                    "num_step": getattr(config, "num_step", None),
                    "guidance_scale": getattr(config, "guidance_scale", None),
                    "denoise": getattr(config, "denoise", None),
                    "preprocess_prompt": getattr(config, "preprocess_prompt", None),
                    "postprocess_output": getattr(config, "postprocess_output", None),
                }
        return serialized

    def _persist_manifest(self, manifest: dict) -> None:
        manifest["updated_at"] = utc_now_iso()
        path = self._manifest_path(manifest["session_id"])
        _atomic_write_text(path, json.dumps(manifest, ensure_ascii=False, indent=2))

    def create_session(self, mode: str, payload: dict, chunks: list[str]) -> tuple[str, dict]:
        session_id = uuid.uuid4().hex
        session_dir = self._session_dir(session_id)
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / "chunks").mkdir(exist_ok=True)
        (session_dir / "artifacts").mkdir(exist_ok=True)

        serialized_payload = self._serialize_payload(payload)
        copied_ref_audio = None
        if serialized_payload.get("ref_audio") and os.path.exists(serialized_payload["ref_audio"]):
            ref_name = Path(serialized_payload["ref_audio"]).suffix or ".wav"
            copied_ref_audio = _copy_file_atomic(
                serialized_payload["ref_audio"],
                session_dir / "artifacts" / f"reference{ref_name}",
            )
            serialized_payload["ref_audio"] = copied_ref_audio

        manifest = {
            "schema_version": SESSION_SCHEMA_VERSION,
            "session_id": session_id,
            "mode": mode,
            "status": "running",
            "created_at": utc_now_iso(),
            "updated_at": utc_now_iso(),
            "text_preview": (serialized_payload.get("text") or "")[:160],
            "payload": serialized_payload,
            "chunks": [
                {
                    "index": index,
                    "text": text,
                    "status": "pending",
                    "audio_file": None,
                }
                for index, text in enumerate(chunks)
            ],
            "timing": {
                "elapsed_active_s": float(serialized_payload.get("elapsed_offset_s") or 0.0),
                "run_started_at": None,
            },
            "artifacts": {
                "reference_audio": copied_ref_audio,
                "final_audio": None,
            },
            "error": None,
        }
        self._persist_manifest(manifest)
        return session_id, manifest

    def load_session(self, session_id: str) -> dict:
        path = self._manifest_path(session_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def save_session(self, manifest: dict) -> dict:
        self._persist_manifest(manifest)
        return manifest

    def mark_running(self, session_id: str, elapsed_active_s: float) -> dict:
        manifest = self.load_session(session_id)
        manifest["status"] = "running"
        manifest["timing"]["elapsed_active_s"] = float(elapsed_active_s)
        manifest["timing"]["run_started_at"] = utc_now_iso()
        manifest["error"] = None
        return self.save_session(manifest)

    def update_elapsed(self, session_id: str, elapsed_active_s: float) -> dict:
        manifest = self.load_session(session_id)
        manifest["timing"]["elapsed_active_s"] = float(elapsed_active_s)
        return self.save_session(manifest)

    def mark_chunk_complete(self, session_id: str, chunk_index: int, audio_file: str, elapsed_active_s: float) -> dict:
        manifest = self.load_session(session_id)
        manifest["chunks"][chunk_index]["status"] = "completed"
        manifest["chunks"][chunk_index]["audio_file"] = audio_file
        manifest["timing"]["elapsed_active_s"] = float(elapsed_active_s)
        return self.save_session(manifest)

    def reset_chunks_from(self, session_id: str, chunk_index: int) -> dict:
        manifest = self.load_session(session_id)
        for chunk in manifest["chunks"][chunk_index:]:
            chunk["status"] = "pending"
            chunk["audio_file"] = None
        return self.save_session(manifest)

    def mark_finished(self, session_id: str, status: str, elapsed_active_s: float, error: str | None = None, final_audio: str | None = None) -> dict:
        manifest = self.load_session(session_id)
        manifest["status"] = status
        manifest["timing"]["elapsed_active_s"] = float(elapsed_active_s)
        manifest["timing"]["run_started_at"] = None
        manifest["error"] = error
        if final_audio:
            manifest["artifacts"]["final_audio"] = final_audio
        return self.save_session(manifest)

    def chunk_output_path(self, session_id: str, chunk_index: int) -> Path:
        return self._session_dir(session_id) / "chunks" / f"{chunk_index:04d}.wav"

    def final_output_path(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "artifacts" / "final.wav"

    def list_recoverable_sessions(self) -> list[dict]:
        sessions: list[dict] = []
        if not self.root.exists():
            return sessions
        for session_dir in self.root.iterdir():
            if not session_dir.is_dir():
                continue
            manifest_path = session_dir / "manifest.json"
            if not manifest_path.exists():
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if manifest.get("schema_version") != SESSION_SCHEMA_VERSION:
                continue
            status = manifest.get("status")
            if status not in RECOVERABLE_STATUSES:
                continue
            completed = 0
            total = len(manifest.get("chunks") or [])
            first_missing = None
            for chunk in manifest.get("chunks") or []:
                if chunk.get("status") == "completed" and chunk.get("audio_file") and os.path.exists(chunk["audio_file"]):
                    completed += 1
                    continue
                if first_missing is None:
                    first_missing = chunk.get("index", completed)
            sessions.append(
                {
                    "session_id": manifest["session_id"],
                    "mode": manifest.get("mode"),
                    "status": "interrupted" if status == "running" else status,
                    "text_preview": manifest.get("text_preview") or "",
                    "updated_at": manifest.get("updated_at") or manifest.get("created_at"),
                    "created_at": manifest.get("created_at"),
                    "elapsed_active_s": float(manifest.get("timing", {}).get("elapsed_active_s") or 0.0),
                    "completed_chunks": completed,
                    "total_chunks": total,
                    "first_incomplete_index": first_missing if first_missing is not None else completed,
                    "manifest": manifest,
                }
            )
        sessions.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
        return sessions

    def delete_session(self, session_id: str) -> None:
        session_dir = self._session_dir(session_id)
        if session_dir.exists():
            shutil.rmtree(session_dir, ignore_errors=True)
