<<<<<<< HEAD
﻿import argparse
=======
import argparse
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
import os
import subprocess
import sys
import tempfile
import logging
import time
import traceback
<<<<<<< HEAD
import threading
=======
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
from pathlib import Path

import imageio_ffmpeg
import numpy as np
<<<<<<< HEAD
=======
import qdarktheme
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
import sounddevice as sd
import soundfile as sf
import torch
from pydub import AudioSegment
<<<<<<< HEAD
from PySide6.QtCore import QPoint, Property, QRect, Qt, QThread, Signal, QTimer, QObject
=======
from PySide6.QtCore import QEasingCurve, QPoint, Property, QRect, QPropertyAnimation, Qt, QThread, Signal, QTimer, QObject
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QProgressBar,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QScrollArea,
)

from omnivoice import OmniVoice, OmniVoiceGenerationConfig
from omnivoice.utils.lang_map import LANG_NAMES, lang_display_name
<<<<<<< HEAD
from omnivoice.utils.text import (
    chunk_text_punctuation,
    ends_with_sensitive_vietnamese_term,
    map_vietnamese_emotions,
    normalize_vietnamese_numbers,
)
=======
from omnivoice.utils.text import chunk_text_punctuation
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d


_ALL_LANGUAGES = ["Tự động"] + sorted(lang_display_name(n) for n in LANG_NAMES)
_CATEGORIES = {
    "Giới tính": ["Nam", "Nữ"],
    "Độ tuổi": ["Trẻ em", "Thiếu niên", "Thanh niên", "Trung niên", "Người già"],
    "Độ cao giọng": ["Rất thấp", "Thấp", "Vừa phải", "Cao", "Rất cao"],
    "Phong cách": ["Thì thầm"],
    "Khẩu âm Tiếng Anh": [
        "Giọng Mỹ",
        "Giọng Úc",
        "Giọng Anh",
        "Giọng Trung",
        "Giọng Canada",
        "Giọng Ấn Độ",
        "Giọng Hàn Quốc",
        "Giọng Bồ Đào Nha",
        "Giọng Nga",
        "Giọng Nhật Bản",
    ],
    "Phương ngôn Tiếng Trung": [
        "Tiếng Hà Nam",
        "Tiếng Thiểm Tây",
        "Tiếng Tứ Xuyên",
        "Tiếng Quý Châu",
        "Tiếng Vân Nam",
        "Tiếng Quế Lâm",
        "Tiếng Tế Nam",
        "Tiếng Thạch Gia Trang",
        "Tiếng Cam Túc",
        "Tiếng Ninh Hạ",
        "Tiếng Thanh Đảo",
        "Tiếng Đông Bắc",
    ],
}
_VI_TO_INSTRUCT = {
    "Nam": "Male",
    "Nữ": "Female",
    "Trẻ em": "Child",
    "Thiếu niên": "Teenager",
    "Thanh niên": "Young Adult",
    "Trung niên": "Middle-aged",
    "Người già": "Elderly",
    "Rất thấp": "Very Low Pitch",
    "Thấp": "Low Pitch",
    "Vừa phải": "Moderate Pitch",
    "Cao": "High Pitch",
    "Rất cao": "Very High Pitch",
    "Thì thầm": "Whisper",
    "Giọng Mỹ": "American Accent",
    "Giọng Úc": "Australian Accent",
    "Giọng Anh": "British Accent",
    "Giọng Trung": "Chinese Accent",
    "Giọng Canada": "Canadian Accent",
    "Giọng Ấn Độ": "Indian Accent",
    "Giọng Hàn Quốc": "Korean Accent",
    "Giọng Bồ Đào Nha": "Portuguese Accent",
    "Giọng Nga": "Russian Accent",
    "Giọng Nhật Bản": "Japanese Accent",
    "Tiếng Hà Nam": "河南话",
    "Tiếng Thiểm Tây": "陕西话",
    "Tiếng Tứ Xuyên": "四川话",
    "Tiếng Quý Châu": "贵州话",
    "Tiếng Vân Nam": "云南话",
    "Tiếng Quế Lâm": "桂林话",
    "Tiếng Tế Nam": "济南话",
    "Tiếng Thạch Gia Trang": "石家庄话",
    "Tiếng Cam Túc": "甘肃话",
    "Tiếng Ninh Hạ": "宁夏话",
    "Tiếng Thanh Đảo": "青岛话",
    "Tiếng Đông Bắc": "东北话",
}


def get_best_device():
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


class TrimRangeSelector(QWidget):
    changed = Signal(float, float)

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(80)
        self.total_duration = 10.0
        self.start_value = 0.0
        self.end_value = 8.0
        self.playhead_value = 0.0
        self.active_handle = None
        self.waveform_data = []

    def set_waveform(self, data: list):
        self.waveform_data = data
        self.update()

    def set_playhead(self, value: float):
        self.playhead_value = value
        self.update()

    def set_total_duration(self, duration: float):
        self.total_duration = max(duration, 0.1)
        self.start_value = max(0.0, min(self.start_value, self.total_duration))
        self.end_value = max(self.start_value + 0.1, min(self.end_value, self.total_duration))
        self.update()
        self.changed.emit(self.start_value, self.end_value)

    def set_values(self, start_value: float, end_value: float):
        self.start_value = max(0.0, min(start_value, self.total_duration))
        self.end_value = max(self.start_value + 0.1, min(end_value, self.total_duration))
        self.update()
        self.changed.emit(self.start_value, self.end_value)

    def _handle_x(self, value: float) -> int:
        track = self.rect().adjusted(18, 22, -18, -18)
        return int(track.left() + (value / self.total_duration) * track.width())

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        track = self.rect().adjusted(18, 22, -18, -18)
        
        # Background
        painter.setPen(Qt.NoPen)
<<<<<<< HEAD
        painter.setBrush(QColor(15, 23, 42))
=======
        painter.setBrush(QColor("#0f172a"))
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
        painter.drawRoundedRect(track, 8, 8)

        # Waveform
        if self.waveform_data:
            num_bars = len(self.waveform_data)
            bar_width = track.width() / num_bars
<<<<<<< HEAD
            painter.setBrush(QColor(51, 65, 85))
=======
            painter.setBrush(QColor("#334155"))
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
            for i, val in enumerate(self.waveform_data):
                bar_h = val * track.height() * 0.8
                bar_rect = QRect(int(track.left() + i * bar_width), int(track.center().y() - bar_h / 2), int(max(1, bar_width - 1)), int(bar_h))
                painter.drawRoundedRect(bar_rect, 2, 2)

        # Selected area
        start_x = self._handle_x(self.start_value)
        end_x = self._handle_x(self.end_value)
        selected = QRect(start_x, track.top(), max(8, end_x - start_x), track.height())
        
        # Draw selected background
        painter.setBrush(QColor(79, 70, 229, 100)) # Transparent indigo
        painter.drawRoundedRect(selected, 8, 8)
        
        # Highlight selected waveform
        if self.waveform_data:
<<<<<<< HEAD
            painter.setBrush(QColor(129, 140, 248))
=======
            painter.setBrush(QColor("#818cf8"))
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
            for i, val in enumerate(self.waveform_data):
                bar_x = int(track.left() + i * bar_width)
                if start_x <= bar_x <= end_x:
                    bar_h = val * track.height() * 0.8
                    bar_rect = QRect(bar_x, int(track.center().y() - bar_h / 2), int(max(1, bar_width - 1)), int(bar_h))
                    painter.drawRoundedRect(bar_rect, 2, 2)

        # Handles
        for x, label in ((start_x, self.start_value), (end_x, self.end_value)):
<<<<<<< HEAD
            painter.setBrush(QColor(248, 250, 252))
            painter.drawEllipse(QPoint(x, track.center().y()), 8, 8)
            painter.setPen(QColor(203, 213, 225))
=======
            painter.setBrush(QColor("#f8fafc"))
            painter.drawEllipse(QPoint(x, track.center().y()), 8, 8)
            painter.setPen(QColor("#cbd5e1"))
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
            painter.drawText(x - 28, track.top() - 4, 56, 18, Qt.AlignCenter, f"{label:.1f}s")
            painter.setPen(Qt.NoPen)
            
        # Playhead (Red line)
        if self.playhead_value > 0 and self.playhead_value <= self.total_duration:
            ph_x = self._handle_x(self.playhead_value)
<<<<<<< HEAD
            painter.setPen(QPen(QColor(239, 68, 68), 2))
=======
            painter.setPen(QPen(QColor("#ef4444"), 2))
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
            painter.drawLine(ph_x, track.top() - 5, ph_x, track.bottom() + 5)

    def mousePressEvent(self, event):
        start_x = self._handle_x(self.start_value)
        end_x = self._handle_x(self.end_value)
        if abs(event.position().x() - start_x) <= abs(event.position().x() - end_x):
            self.active_handle = "start"
        else:
            self.active_handle = "end"

    def mouseMoveEvent(self, event):
        if not self.active_handle:
            return
        track = self.rect().adjusted(18, 22, -18, -18)
        ratio = min(1.0, max(0.0, (event.position().x() - track.left()) / max(track.width(), 1)))
        value = ratio * self.total_duration
        if self.active_handle == "start":
            self.start_value = min(value, self.end_value - 0.1)
        else:
            self.end_value = max(value, self.start_value + 0.1)
        self.update()
        self.changed.emit(self.start_value, self.end_value)

    def mouseReleaseEvent(self, _event):
        self.active_handle = None


class GenerationWorker(QThread):
    success = Signal(object, dict)
    error = Signal(str, str)
    progress = Signal(str, int)

    def __init__(self, model: OmniVoice, mode: str, payload: dict):
        super().__init__()
        self.model = model
        self.mode = mode
        self.payload = payload
<<<<<<< HEAD
        self._is_cancelled = False
        self._cancel_event = threading.Event()

    def cancel(self):
        self._is_cancelled = True
        self._cancel_event.set()
        if hasattr(self.model, "cancel_generation"):
            self.model.cancel_generation()

    def _raise_if_cancelled(self):
        if self._is_cancelled:
            raise RuntimeError("Đã hủy tác vụ")

    def _split_text_chunks(self, text: str) -> list[str]:
        # Cháº¿ Ä‘á»™ Æ°u tiÃªn Ä‘Ãºng chá»¯: má»—i váº¿ ngÄƒn bá»Ÿi dáº¥u cÃ¢u lÃ  má»™t Ä‘Æ¡n vá»‹ Ä‘á»c
        # gáº§n nhÆ° Ä‘á»™c láº­p. CÃ¡ch nÃ y cháº­m hÆ¡n má»™t chÃºt nhÆ°ng giáº£m máº¡nh viá»‡c model
        # nuá»‘t cáº£ cá»¥m á»Ÿ giá»¯a khi gáº·p ká»‹ch báº£n comma-heavy.
        import re

        clean_text = re.sub(r'\s+,\s+', ', ', text)
        clean_text = re.sub(r',+', ',', clean_text)
        raw_parts = re.split(r'([,.;:!?\n]+)', clean_text)

        chunks = []
        current_chunk = ""
        min_clause_chars = 24

        for i in range(0, len(raw_parts) - 1, 2):
            text_part = raw_parts[i].strip()
            punct_part = raw_parts[i + 1].strip() if i + 1 < len(raw_parts) else ""

            if not text_part:
                continue

            combined = text_part + punct_part

            # Gá»™p cÃ¡c máº©u quÃ¡ ngáº¯n kiá»ƒu "Yeah," vá»›i váº¿ sÃ¡t sau Ä‘á»ƒ trÃ¡nh Ä‘á»c cá»¥t.
            if current_chunk and len(current_chunk) < min_clause_chars:
                current_chunk = f"{current_chunk} {combined}".strip()
                chunks.append(current_chunk.strip())
                current_chunk = ""
                continue

            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = combined

        if len(raw_parts) % 2 != 0:
            last_part = raw_parts[-1].strip()
            if last_part:
                if current_chunk:
                    current_chunk = f"{current_chunk} {last_part}".strip()
                else:
                    current_chunk = last_part

        if current_chunk:
            chunks.append(current_chunk.strip())

        filtered_chunks = [chunk for chunk in chunks if chunk]
        if not filtered_chunks:
            return [text]

        # Hậu xử lý tối thiểu: chỉ dồn chunk quá ngắn hoặc chunk kết thúc bằng từ
        # nháº¡y phÃ¡t Ã¢m sang chunk káº¿ tiáº¿p. KhÃ´ng gá»™p trÃ n lan Ä‘á»ƒ trÃ¡nh model bá»
        # máº¥t cáº£ cá»¥m á»Ÿ giá»¯a má»™t chunk dÃ i.
        merged_chunks = []
        i = 0
        merge_soft_min = 18
        merge_hard_cap = 110
        while i < len(filtered_chunks):
            chunk = filtered_chunks[i]
            should_merge = len(chunk) < merge_soft_min or ends_with_sensitive_vietnamese_term(chunk)
            if i + 1 < len(filtered_chunks) and should_merge:
                combined = f"{chunk} {filtered_chunks[i + 1]}".strip()
                if len(combined) <= merge_hard_cap:
                    merged_chunks.append(combined)
                    i += 2
                    continue
            merged_chunks.append(chunk)
            i += 1

        return merged_chunks

    def _prepare_chunk_text(self, text: str) -> str:
        text = text.strip()
        if not text:
            return text

        # Khi má»™t chunk káº¿t thÃºc báº±ng dáº¥u pháº©y, model thÆ°á»ng nháº£ chá»¯ cuá»‘i yáº¿u
        # hoáº·c cá»¥t hÆ¡i. Äá»•i riÃªng dáº¥u káº¿t thÃºc chunk sang dáº¥u cháº¥m Ä‘á»ƒ nÃ³ khÃ©p
        # cÃ¢u cháº¯c hÆ¡n, nhÆ°ng váº«n giá»¯ nguyÃªn toÃ n bá»™ tá»« ngá»¯.
        if text.endswith((",", ";", ":")):
            return text[:-1].rstrip() + "."
        if text[-1] not in ".!?":
            return text + "."
        return text
=======

    def _split_text_chunks(self, text: str) -> list[str]:
        chunk_chars = int(self.payload.get("chunk_chars") or 0)
        if chunk_chars <= 0 or len(text) <= chunk_chars:
            return [text]
        chunks = chunk_text_punctuation(text=text, chunk_len=chunk_chars, min_chunk_len=32)
        return chunks or [text]
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d

    def run(self):
        started_at = time.perf_counter()
        try:
<<<<<<< HEAD
            self._raise_if_cancelled()
            if hasattr(self.model, "clear_generation_cancel"):
                self.model.clear_generation_cancel()
            self.progress.emit("Đang kiểm tra dữ liệu đầu vào...", 5)
            if self.mode == "clone":
                self._raise_if_cancelled()
=======
            self.progress.emit("Đang kiểm tra dữ liệu đầu vào...", 5)
            if self.mode == "clone":
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
                self.progress.emit("Đang tạo prompt clone từ file mẫu...", 20)
                prompt = self.model.create_voice_clone_prompt(
                    ref_audio=self.payload["ref_audio"],
                    ref_text=self.payload["ref_text"],
                )
                kwargs = {
                    "text": self.payload["text"],
                    "language": self.payload["language"],
                    "generation_config": self.payload["generation_config"],
                    "voice_clone_prompt": prompt,
                }
            else:
<<<<<<< HEAD
                self._raise_if_cancelled()
=======
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
                self.progress.emit("Đang chuẩn bị cấu hình thiết kế giọng...", 20)
                kwargs = {
                    "text": self.payload["text"],
                    "language": self.payload["language"],
                    "generation_config": self.payload["generation_config"],
                }
                if self.payload["instruct"]:
                    kwargs["instruct"] = self.payload["instruct"]

            self.progress.emit("Đang áp dụng tham số suy luận...", 40)
<<<<<<< HEAD
            self._raise_if_cancelled()
=======
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
            if self.payload.get("speed") and self.payload["speed"] != 1.0:
                kwargs["speed"] = self.payload["speed"]
            if self.payload.get("duration") and self.payload["duration"] > 0:
                kwargs["duration"] = self.payload["duration"]

            chunks = self._split_text_chunks(self.payload["text"])
            generated_parts = []
            total_chunks = len(chunks)
            for index, chunk_text in enumerate(chunks, start=1):
<<<<<<< HEAD
                self._raise_if_cancelled()
                chunk_kwargs = dict(kwargs)
                prepared_chunk_text = self._prepare_chunk_text(chunk_text)
                chunk_kwargs["text"] = prepared_chunk_text
                print(f"[TEXT_CHUNK] {index}/{total_chunks}: {prepared_chunk_text}")
=======
                chunk_kwargs = dict(kwargs)
                
                # Fix AI đọc dấu chấm thành "ráp" / "chấm"
                clean_text = chunk_text.replace("...", ",")
                clean_text = clean_text.replace(". ", ", ")
                if clean_text.endswith("."):
                    clean_text = clean_text[:-1] + ","
                    
                chunk_kwargs["text"] = clean_text
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
                progress_value = 45 + int((index - 1) / max(total_chunks, 1) * 45)
                self.progress.emit(
                    f"Đang chạy chunk {index}/{total_chunks} ({len(chunk_text)} ký tự)...",
                    progress_value,
                )
<<<<<<< HEAD
                chunk_audio = self.model.generate(cancel_event=self._cancel_event, **chunk_kwargs)[0]
                self._raise_if_cancelled()
=======
                chunk_audio = self.model.generate(**chunk_kwargs)[0]
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
                generated_parts.append(chunk_audio)

            if len(generated_parts) == 1:
                final_audio = generated_parts[0]
            else:
<<<<<<< HEAD
                pause = np.zeros(int(self.model.sampling_rate * 0.05), dtype=generated_parts[0].dtype)
                with_pauses = []
                for part in generated_parts:
                    with_pauses.extend([part, pause])
                final_audio = np.concatenate(with_pauses[:-1], axis=-1)
                
            # --- Dá»n dáº¹p GPU ngay sau khi táº¡o xong ---
            try:
                import torch
                torch.cuda.empty_cache()
            except Exception:
                pass
                
=======
                final_audio = np.concatenate(generated_parts, axis=-1)
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
            elapsed_s = time.perf_counter() - started_at
            meta = {
                "ref_audio": self.payload.get("ref_audio"),
                "start": self.payload.get("start"),
                "end": self.payload.get("end"),
                "instruct": self.payload.get("instruct"),
                "language": self.payload.get("language"),
                "speed": self.payload.get("speed"),
                "duration": self.payload.get("duration"),
                "elapsed_s": elapsed_s,
                "text_length": len(self.payload.get("text", "")),
                "output_seconds": len(final_audio) / float(self.model.sampling_rate),
                "chunk_count": total_chunks,
                "chunk_chars": self.payload.get("chunk_chars"),
            }
            self.progress.emit("Đang hoàn tất kết quả...", 95)
<<<<<<< HEAD
            self._raise_if_cancelled()
=======
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
            self.success.emit(final_audio, meta)
        except Exception as exc:
            self.error.emit(str(exc), traceback.format_exc())


class QtLogStream(QObject):
    textWritten = Signal(str)

    def write(self, text):
        if str(text).strip():
            self.textWritten.emit(str(text).strip())

    def flush(self):
        pass


class OmniVoiceQtWindow(QMainWindow):
    def __init__(self, model: OmniVoice):
        super().__init__()
        self.model = model
        self.sampling_rate = model.sampling_rate
        self.audio_output = None
        
        # Log redirection
        self.log_stream = QtLogStream()
        self.log_stream.textWritten.connect(self._append_log)
        sys.stdout = self.log_stream
        sys.stderr = self.log_stream
        
        # Configure logging to go to stdout
        logging.getLogger().addHandler(logging.StreamHandler(self.log_stream))
        logging.getLogger().setLevel(logging.INFO)

        self.current_processed_ref = None
        self.current_source = ""
        self.duration_seconds = 10.0
        self.worker = None
<<<<<<< HEAD
        self.active_mode = None
        self._worker_token_seed = 0
        self._active_worker_token = None
        self._finished_workers = []
=======
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
        self.is_playing = False
        self._runtime_state = {
            "clone": {"started_at": None, "payload": None},
            "design": {"started_at": None, "payload": None},
        }

        self.setWindowTitle("OMNIVOICE STUDIO")
        self.resize(1520, 930)
        self.setMinimumSize(400, 400)
        self._apply_style()
        self._build_ui()
        self._refresh_runtime_badge()
<<<<<<< HEAD

    def _apply_style(self):
        qss_path = os.path.join(os.path.dirname(__file__), 'style.qss')
        try:
            with open(qss_path, 'r', encoding='utf-8') as f:
                self.setStyleSheet(f.read())
        except Exception as e:
            print(f"Warning: Could not load style.qss from {qss_path}: {e}")
            # Fallback minimal style so it remains usable
            self.setStyleSheet("QWidget { background: #05070b; color: #f4f7fb; }")
=======
        self._nav_buttons = []

    def _apply_style(self):
        self.setStyleSheet(
            """
            QWidget {
                background: #000000;
                color: #ffffff;
                font-family: "BMWTypeNextLatin", "Inter", sans-serif;
                font-size: 14px;
            }
            QFrame#Card {
                background: #1a1a1a;
                border: 1px solid #3c3c3c;
                border-radius: 0px;
            }
            QPushButton {
                background: #1a1a1a;
                border: 1px solid #3c3c3c;
                border-radius: 0px;
                padding: 10px 16px;
                color: #ffffff;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 1.5px;
            }
            QPushButton:hover {
                background: #262626;
                border: 1px solid #ffffff;
            }
            QPushButton:pressed {
                background: #000000;
            }
            QPushButton:disabled {
                background: #0d0d0d;
                color: #7e7e7e;
                border: 1px solid #1a1a1a;
            }
            QPushButton#PrimaryBtn {
                background: #000000;
                border: 1px solid #ffffff;
                color: #ffffff;
                font-weight: 700;
            }
            QPushButton#PrimaryBtn:hover {
                background: #1a1a1a;
            }
            QPushButton#PrimaryBtn:disabled {
                background: #1a1a1a;
                color: #7e7e7e;
                border: 1px solid #3c3c3c;
            }
            QPushButton#NavBtn {
                background: transparent;
                border: none;
                color: #bbbbbb;
                text-align: left;
                padding-left: 20px;
                font-size: 15px;
                font-weight: 700;
            }
            QPushButton#NavBtn:hover {
                color: #ffffff;
                background: #1a1a1a;
            }
            QPushButton#NavBtnActive {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0066b1, stop:0.5 #1c69d4, stop:1 #e22718);
                border: none;
                color: white;
                text-align: left;
                padding-left: 20px;
                font-size: 15px;
                font-weight: 700;
            }
            QLineEdit, QPlainTextEdit, QComboBox, QDoubleSpinBox, QSpinBox {
                background: #1a1a1a;
                border: 1px solid #3c3c3c;
                border-radius: 0px;
                padding: 10px;
                color: #ffffff;
            }
            QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus {
                border: 1px solid #ffffff;
                background: #262626;
            }
            QComboBox::drop-down { border: none; }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #bbbbbb;
                margin-right: 10px;
            }
            QComboBox QAbstractItemView {
                background: #1a1a1a;
                border: 1px solid #3c3c3c;
                selection-background-color: #0066b1;
                border-radius: 0px;
            }
            QLabel#Title { font-size: 32px; font-weight: 700; color: white; text-transform: uppercase; }
            QLabel#SubTitle { color: #bbbbbb; font-size: 14px; font-weight: 300; }
            QLabel#SectionTitle { font-size: 18px; font-weight: 700; color: #ffffff; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 1.5px; }
            QProgressBar {
                background: #1a1a1a;
                border: none;
                border-radius: 0px;
                text-align: center;
                height: 12px;
                color: transparent;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0066b1, stop:0.5 #1c69d4, stop:1 #e22718);
                border-radius: 0px;
            }
            QSlider::groove:horizontal {
                border-radius: 0px;
                height: 8px;
                background: #3c3c3c;
            }
            QSlider::handle:horizontal {
                background: #1c69d4;
                width: 16px;
                height: 16px;
                margin: -4px 0;
                border-radius: 0px;
            }
            QSlider::sub-page:horizontal {
                background: #0066b1;
                border-radius: 0px;
            }
            QScrollBar:vertical {
                border: none;
                background: #000000;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #3c3c3c;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            """
        )
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d

    def _on_device_changed(self, text: str):
        if text == "Tự động":
            target_device = get_best_device()
        else:
            target_device = text.lower()
            
        if target_device == "cuda" and not torch.cuda.is_available():
            QMessageBox.warning(self, "Lỗi cấu hình GPU", "Máy của bạn không có card NVIDIA hoặc chưa cài chuẩn CUDA. Hệ thống sẽ tự động dùng CPU.")
            self.device_combo.blockSignals(True)
            self.device_combo.setCurrentText("CPU")
            self.device_combo.blockSignals(False)
            target_device = "cpu"
            
        try:
            self.model.to(target_device)
            # Update ASR model if loaded
            if getattr(self.model, "_asr_pipe", None) is not None:
                self.model._asr_pipe.model.to(target_device)
                self.model._asr_pipe.device = torch.device(target_device)
            
            QMessageBox.information(self, "Thành công", f"Đã chuyển bộ máy xử lý sang {target_device.upper()}!")
            self._refresh_runtime_badge()
        except Exception as e:
            QMessageBox.critical(self, "Lỗi chuyển thiết bị", f"Lỗi:\n{e}")

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        main_layout = QVBoxLayout(root)
<<<<<<< HEAD
        # main_layout.setContentsMargins(0, 0, 0, 0)
        # main_layout.setSpacing(0)

        # Header banner
        header = QFrame()
        header.setObjectName("HeaderFrame")
        header_layout = QVBoxLayout(header)
        # header_layout.setContentsMargins(28, 28, 28, 22)
        # header_layout.setSpacing(8)
        title = QLabel("OmniVoice Pro")
        title.setObjectName("Title")
        title.setAlignment(Qt.AlignCenter)
        subtitle = QLabel("Phần mềm giả lập & Thiết kế giọng nói AI đỉnh cao (Chạy 100% local offline)")
        subtitle.setObjectName("SubTitle")
        subtitle.setAlignment(Qt.AlignCenter)
        self.runtime_badge = QLabel("")
        self.runtime_badge.setAlignment(Qt.AlignCenter)
        self.runtime_badge.setObjectName("RuntimeBadge")
=======
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header banner
        header = QFrame()
        header.setStyleSheet("background: #000000; border-bottom: 4px solid qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0066b1, stop:0.5 #1c69d4, stop:1 #e22718);")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(20, 30, 20, 30)
        title = QLabel("🎙️ OmniVoice Pro")
        title.setStyleSheet("font-size: 36px; font-weight: 800; color: white;")
        title.setAlignment(Qt.AlignCenter)
        subtitle = QLabel("Phần mềm giả lập & Thiết kế giọng nói AI Đỉnh cao (Chạy 100% Local Offline)")
        subtitle.setStyleSheet("font-size: 16px; color: #e0e7ff; font-weight: 500;")
        subtitle.setAlignment(Qt.AlignCenter)
        self.runtime_badge = QLabel("")
        self.runtime_badge.setAlignment(Qt.AlignCenter)
        self.runtime_badge.setStyleSheet(
            "font-size: 13px; font-weight: 700; color: white; background: rgba(15,23,42,0.28); padding: 8px 14px; border-radius: 12px;"
        )
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        
        badge_row = QHBoxLayout()
        badge_row.setAlignment(Qt.AlignCenter)
        badge_row.addWidget(self.runtime_badge)
        
        self.device_combo = QComboBox()
        self.device_combo.addItems(["Tự động", "CPU", "CUDA"])
<<<<<<< HEAD
        self.device_combo.setObjectName("DeviceCombo")
=======
        self.device_combo.setStyleSheet(
            "font-size: 13px; font-weight: 700; color: white; background: #000000; padding: 6px 10px; border-radius: 0px; border: 1px solid #3c3c3c; text-transform: uppercase;"
        )
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
        self.device_combo.setToolTip("Chọn thiết bị xử lý AI. CUDA sẽ nhanh hơn rất nhiều.")
        self.device_combo.currentTextChanged.connect(self._on_device_changed)
        badge_row.addWidget(self.device_combo)
        
        header_layout.addLayout(badge_row)
        main_layout.addWidget(header)

        # Settings states
        self.num_step = QSpinBox()
        self.num_step.setRange(4, 64)
        self.num_step.setValue(32)
        self.guidance = QDoubleSpinBox()
        self.guidance.setRange(0.0, 8.0)
        self.guidance.setSingleStep(0.1)
        self.guidance.setValue(2.0)
        self.speed = QDoubleSpinBox()
        self.speed.setRange(0.5, 2.0)
        self.speed.setSingleStep(0.05)
        self.speed.setValue(1.0)
        self.duration = QDoubleSpinBox()
        self.duration.setRange(0.0, 9999.0)
        self.duration.setValue(0.0)
        self.duration.setSingleStep(0.5)
        self.denoise = QCheckBox("Khử ồn")
        self.denoise.setChecked(True)
        self.preprocess = QCheckBox("Tiền xử lý mẫu")
        self.preprocess.setChecked(True)
        self.postprocess = QCheckBox("Hậu xử lý đầu ra")
        self.postprocess.setChecked(True)

        self.tabs = QTabWidget()
<<<<<<< HEAD
        self.tabs.setObjectName("MainTabs")
=======
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: none; background: #000000; }
            QTabBar::tab { background: #000000; color: #bbbbbb; padding: 16px 32px; font-size: 16px; font-weight: 700; border-radius: 0px; margin-right: 4px; margin-top: 16px; text-transform: uppercase; }
            QTabBar::tab:selected { background: #000000; color: #ffffff; border-bottom: 4px solid; border-image: linear-gradient(to right, #0066b1 33%, #1c69d4 33% 66%, #e22718 66%) 1; }
            QTabBar::tab:hover:!selected { background: #1a1a1a; }
        """)
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d

        clone_scroll = QScrollArea()
        clone_scroll.setWidgetResizable(True)
        clone_scroll.setFrameShape(QFrame.NoFrame)
        clone_scroll.setWidget(self._build_clone_page())
<<<<<<< HEAD
        self.tabs.addTab(clone_scroll, "Clone Giọng Nói (Sao chép)")
=======
        self.tabs.addTab(clone_scroll, "🎭 Clone Giọng Nói (Sao chép)")
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d

        design_scroll = QScrollArea()
        design_scroll.setWidgetResizable(True)
        design_scroll.setFrameShape(QFrame.NoFrame)
        design_scroll.setWidget(self._build_design_page())
<<<<<<< HEAD
        self.tabs.addTab(design_scroll, "Thiết Kế Giọng (Tạo giọng mới)")
=======
        self.tabs.addTab(design_scroll, "🧬 Thiết Kế Giọng (Tạo giọng mới)")
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d

        main_layout.addWidget(self.tabs)

    def _card(self):
        card = QFrame()
        card.setObjectName("Card")
        return card

    def _label(self, text: str, object_name: str | None = None, wrap: bool = False):
        label = QLabel(text)
        if object_name:
            label.setObjectName(object_name)
        label.setWordWrap(wrap)
        return label

<<<<<<< HEAD
    def _panel_badge(self, text: str):
        badge = QLabel(text)
        badge.setObjectName("PanelBadge")
        return badge

    def _insert_nonverbal_tag(self, editor: QPlainTextEdit, tag: str):
        cursor = editor.textCursor()
        needs_space_before = cursor.position() > 0 and not cursor.block().text()[:cursor.positionInBlock()].endswith((" ", "\n"))
        insert_text = f" {tag}" if needs_space_before else tag
        if cursor.position() < len(editor.toPlainText()):
            insert_text += " "
        cursor.insertText(insert_text)
        editor.setTextCursor(cursor)
        editor.setFocus()

    def _build_normalized_preview(self, text: str, language: str | None) -> str:
        text = text.strip()
        if not text:
            return ""

        is_vi = (language == "Vietnamese") or bool(
            __import__("re").search(
                r"[áàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđĐ]",
                text,
            )
        )
        normalized = normalize_vietnamese_numbers(text, is_vi=is_vi)
        if is_vi:
            normalized = map_vietnamese_emotions(normalized)
        return normalized.strip()

    def _show_normalized_preview(self, editor: QPlainTextEdit, language: str | None):
        raw_text = editor.toPlainText().strip()
        if not raw_text:
            QMessageBox.information(self, "Chưa có nội dung", "Bạn chưa nhập nội dung để xem preview normalize.")
            return

        preview_text = self._build_normalized_preview(raw_text, language)
        QMessageBox.information(
            self,
            "Preview normalize",
            f"Text gốc:\n{raw_text}\n\n--- Sau normalize ---\n{preview_text}",
        )

    def _nonverbal_bar(self, editor: QPlainTextEdit, get_language=None):
        wrapper = QVBoxLayout()
        wrapper.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        top_row.addWidget(self._label("Chèn nhanh:", "SubTitle"))
        for label, tag in [
            ("Cười", "[laughter]"),
            ("Thở dài", "[sigh]"),
            ("Xác nhận", "[confirmation-en]"),
            ("Bực nhẹ", "[dissatisfaction-hnn]"),
        ]:
            btn = QPushButton(label)
            btn.setMinimumHeight(32)
            btn.clicked.connect(lambda _=False, e=editor, t=tag: self._insert_nonverbal_tag(e, t))
            top_row.addWidget(btn)
        preview_btn = QPushButton("Xem preview")
        preview_btn.setMinimumHeight(32)
        preview_btn.clicked.connect(
            lambda _=False, e=editor, g=get_language: self._show_normalized_preview(
                e,
                g() if callable(g) else None,
            )
        )
        top_row.addWidget(preview_btn)
        top_row.addStretch(1)

        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(8)
        for label, tag in [
            ("Hỏi EN", "[question-en]"),
            ("Hỏi ah", "[question-ah]"),
            ("Hỏi oh", "[question-oh]"),
            ("Ngạc nhiên ah", "[surprise-ah]"),
            ("Ngạc nhiên oh", "[surprise-oh]"),
            ("Ngạc nhiên wa", "[surprise-wa]"),
        ]:
            btn = QPushButton(label)
            btn.setMinimumHeight(32)
            btn.clicked.connect(lambda _=False, e=editor, t=tag: self._insert_nonverbal_tag(e, t))
            bottom_row.addWidget(btn)
        bottom_row.addStretch(1)

        wrapper.addLayout(top_row)
        wrapper.addLayout(bottom_row)
        return wrapper

    def _build_settings_group(self, prefix: str):
        settings_card = self._card()
        settings_l = QVBoxLayout(settings_card)
        # settings_l.setContentsMargins(24, 24, 24, 24)
        # settings_l.setSpacing(14)
        settings_l.addWidget(self._label("Cài đặt nâng cao", "SectionTitle"))
=======
    def _build_settings_group(self, prefix: str):
        settings_card = self._card()
        settings_l = QVBoxLayout(settings_card)
        settings_l.setContentsMargins(24, 24, 24, 24)
        settings_l.addWidget(self._label("⚙️ Cài đặt Nâng cao", "SectionTitle"))
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
        
        speed = QDoubleSpinBox()
        speed.setRange(0.5, 2.0)
        speed.setSingleStep(0.05)
        speed.setValue(1.0)
        
        duration = QDoubleSpinBox()
        duration.setRange(0.0, 9999.0)
        duration.setValue(0.0)
        duration.setSingleStep(0.5)

        num_step = QSpinBox()
        num_step.setRange(4, 64)
        num_step.setValue(32)

        guidance = QDoubleSpinBox()
        guidance.setRange(0.0, 8.0)
        guidance.setSingleStep(0.1)
        guidance.setValue(2.0)

        denoise = QCheckBox("Khử ồn")
        denoise.setChecked(True)
        preprocess = QCheckBox("Tiền xử lý mẫu")
        preprocess.setChecked(True)
        postprocess = QCheckBox("Hậu xử lý đầu ra")
        postprocess.setChecked(True)

        setattr(self, f"{prefix}_speed", speed)
        setattr(self, f"{prefix}_duration", duration)
        setattr(self, f"{prefix}_num_step", num_step)
        setattr(self, f"{prefix}_guidance", guidance)
        setattr(self, f"{prefix}_denoise", denoise)
        setattr(self, f"{prefix}_preprocess", preprocess)
        setattr(self, f"{prefix}_postprocess", postprocess)

<<<<<<< HEAD
        form_grid = QGridLayout()
        form_grid.setHorizontalSpacing(12)
        form_grid.setVerticalSpacing(10)
        form_grid.addWidget(QLabel("Tốc độ đọc"), 0, 0)
        form_grid.addWidget(speed, 0, 1)
        form_grid.addWidget(QLabel("Ép thời lượng (s)"), 0, 2)
        form_grid.addWidget(duration, 0, 3)
        form_grid.addWidget(QLabel("Bước inference"), 1, 0)
        form_grid.addWidget(num_step, 1, 1)
        form_grid.addWidget(QLabel("Mức tuân thủ CFG"), 1, 2)
        form_grid.addWidget(guidance, 1, 3)
        settings_l.addLayout(form_grid)

        row3 = QHBoxLayout()
        row3.setSpacing(14)
        row3.addWidget(denoise)
        row3.addWidget(preprocess)
        row3.addWidget(postprocess)
        row3.addStretch(1)
=======
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Tốc độ đọc:"))
        row1.addWidget(speed)
        row1.addWidget(QLabel("Ép thời lượng (s):"))
        row1.addWidget(duration)
        settings_l.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Bước Inference:"))
        row2.addWidget(num_step)
        row2.addWidget(QLabel("Mức tuân thủ CFG:"))
        row2.addWidget(guidance)
        settings_l.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(denoise)
        row3.addWidget(preprocess)
        row3.addWidget(postprocess)
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
        settings_l.addLayout(row3)
        return settings_card

    def _build_clone_page(self):
        page = QWidget()
        layout = QHBoxLayout(page)
<<<<<<< HEAD
        # layout.setContentsMargins(28, 28, 28, 28)
        # layout.setSpacing(20)
=======
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(24)
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
        layout.setAlignment(Qt.AlignTop)

        left_col = QVBoxLayout()
        left_col.setSpacing(16)

        c1 = self._card()
        c1_l = QVBoxLayout(c1)
<<<<<<< HEAD
        # c1_l.setContentsMargins(24, 24, 24, 24)
        # c1_l.setSpacing(12)
        c1_l.addWidget(self._panel_badge("Bước 1 · Nhập nội dung"), alignment=Qt.AlignLeft)
        c1_l.addWidget(self._label("Nội dung cần đọc", "SectionTitle"))
        self.clone_text = QPlainTextEdit()
        self.clone_text.setPlaceholderText("Nhập văn bản bạn muốn chuyển thành giọng nói vào đây...\nVí dụ: Xin chào mọi người, hôm nay thời tiết rất đẹp!")
        self.clone_text.setMinimumHeight(150)
        self.clone_text.setMaximumHeight(220)
        c1_l.addWidget(self.clone_text)
        c1_l.addLayout(self._nonverbal_bar(self.clone_text, lambda: None if self.clone_lang.currentText() == "Tự động" else self.clone_lang.currentText()))
=======
        c1_l.setContentsMargins(24, 24, 24, 24)
        c1_l.addWidget(self._label("📝 Nội dung cần đọc", "SectionTitle"))
        self.clone_text = QPlainTextEdit()
        self.clone_text.setPlaceholderText("Nhập văn bản bạn muốn chuyển thành giọng nói vào đây...\nVí dụ: Xin chào mọi người, hôm nay thời tiết rất đẹp!")
        self.clone_text.setMinimumHeight(120)
        c1_l.addWidget(self.clone_text)
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
        left_col.addWidget(c1)

        c2 = self._card()
        c2_l = QVBoxLayout(c2)
<<<<<<< HEAD
        # c2_l.setContentsMargins(24, 24, 24, 24)
        # c2_l.setSpacing(12)
        c2_l.addWidget(self._panel_badge("Bước 2 · Chọn mẫu"), alignment=Qt.AlignLeft)
        c2_l.addWidget(self._label("Âm thanh gốc (Giọng mẫu)", "SectionTitle"))
=======
        c2_l.setContentsMargins(24, 24, 24, 24)
        c2_l.addWidget(self._label("🎧 Âm thanh gốc (Giọng mẫu)", "SectionTitle"))
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
        c2_l.addWidget(self._label("Tải lên 1 đoạn ghi âm giọng nói mà bạn muốn AI bắt chước (Nên dài từ 3 đến 10 giây và rõ lời).", "SubTitle", True))
        
        file_row = QHBoxLayout()
        self.clone_file = QLineEdit()
        self.clone_file.setReadOnly(True)
        self.clone_file.setPlaceholderText("Chưa chọn file audio/video nào...")
<<<<<<< HEAD
        browse_btn = QPushButton("Chọn File")
=======
        browse_btn = QPushButton("📁 Chọn File")
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
        browse_btn.setMinimumHeight(40)
        browse_btn.clicked.connect(self._browse_source)
        file_row.addWidget(self.clone_file, 1)
        file_row.addWidget(browse_btn)
        c2_l.addLayout(file_row)

        self.media_player = QMediaPlayer(self)
        self.media_audio = QAudioOutput(self)
        self.media_player.setAudioOutput(self.media_audio)
        self.media_player.positionChanged.connect(self._on_player_position_changed)
        
        # We only need the audio trimmer visualizer now to mimic Gradio's gr.Audio
<<<<<<< HEAD
        c2_l.addWidget(self._label("Kéo cắt đoạn dùng để clone", "SectionTitle"))
=======
        c2_l.addWidget(self._label("✂️ Kéo cắt đoạn dùng để clone", "SectionTitle"))
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
        self.range_selector = TrimRangeSelector()
        self.range_selector.changed.connect(self._sync_trim_spinboxes)
        c2_l.addWidget(self.range_selector)

        trim_row = QHBoxLayout()
<<<<<<< HEAD
        self.preview_play_btn = QPushButton("Phát đoạn đã cắt")
=======
        self.preview_play_btn = QPushButton("▶ Phát đoạn đã cắt")
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
        self.preview_play_btn.clicked.connect(self._toggle_media_preview)
        
        self.trim_start = QDoubleSpinBox()
        self.trim_start.setRange(0.0, 99999.0)
        self.trim_start.setValue(0.0)
        self.trim_start.valueChanged.connect(self._sync_range_from_spin)
        self.trim_end = QDoubleSpinBox()
        self.trim_end.setRange(0.0, 99999.0)
        self.trim_end.setValue(8.0)
        self.trim_end.valueChanged.connect(self._sync_range_from_spin)
        
        trim_row.addWidget(self.preview_play_btn)
        trim_row.addStretch(1)
        trim_row.addWidget(QLabel("Từ (s):"))
        trim_row.addWidget(self.trim_start)
        trim_row.addWidget(QLabel("Đến (s):"))
        trim_row.addWidget(self.trim_end)
        c2_l.addLayout(trim_row)

        c2_l.addSpacing(10)
        c2_l.addWidget(self._label("Lời của đoạn ghi âm mẫu (Tùy chọn, để trống AI sẽ tự nghe):", "SubTitle"))
        self.clone_ref_text = QPlainTextEdit()
        self.clone_ref_text.setPlaceholderText("Nhập lời thoại của đoạn âm thanh trên (nếu máy yếu tắt ASR).")
<<<<<<< HEAD
        self.clone_ref_text.setMinimumHeight(74)
        self.clone_ref_text.setMaximumHeight(90)
=======
        self.clone_ref_text.setMaximumHeight(60)
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
        c2_l.addWidget(self.clone_ref_text)
        left_col.addWidget(c2)

        c3 = self._card()
        c3_l = QVBoxLayout(c3)
<<<<<<< HEAD
        # c3_l.setContentsMargins(24, 24, 24, 24)
        # c3_l.setSpacing(10)
        c3_l.addWidget(self._panel_badge("Bước 3 · Ngôn ngữ"), alignment=Qt.AlignLeft)
        c3_l.addWidget(self._label("Ngôn ngữ đích & Tùy chỉnh", "SectionTitle"))
=======
        c3_l.setContentsMargins(24, 24, 24, 24)
        c3_l.addWidget(self._label("🌐 Ngôn ngữ đích & Tùy chỉnh", "SectionTitle"))
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
        self.clone_lang = QComboBox()
        self.clone_lang.addItems(_ALL_LANGUAGES)
        c3_l.addWidget(self.clone_lang)
        left_col.addWidget(c3)

<<<<<<< HEAD
        clone_settings = self._build_settings_group("clone")
        left_col.addWidget(clone_settings)
        left_col.addStretch(1)

        right_col = QVBoxLayout()
        right_col.setSpacing(14)
=======
        left_col.addWidget(self._build_settings_group("clone"))

        right_col = QVBoxLayout()
        right_col.setSpacing(16)
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
        right_col.setAlignment(Qt.AlignTop)

        r1 = self._card()
        r1_l = QVBoxLayout(r1)
<<<<<<< HEAD
        # r1_l.setContentsMargins(24, 24, 24, 24)
        # r1_l.setSpacing(12)
        r1_l.addWidget(self._panel_badge("Bước 4 · Tạo & xuất"), alignment=Qt.AlignLeft)
        r1_l.addWidget(self._label("Xuất File", "SectionTitle"))
        self.clone_generate_btn = QPushButton("BẮT ĐẦU TẠO GIỌNG")
        self.clone_generate_btn.setProperty("variant", "primary")
        self.clone_generate_btn.setMinimumHeight(60)
        self.clone_generate_btn.setObjectName("CloneGenerateBtn")
        self.clone_generate_btn.clicked.connect(self._start_clone_generation)
        clone_action_row = QHBoxLayout()
        clone_action_row.setSpacing(12)
        clone_action_row.addWidget(self.clone_generate_btn, 3)
        self.clone_cancel_btn = QPushButton("HỦY")
        self.clone_cancel_btn.setMinimumHeight(60)
        self.clone_cancel_btn.setEnabled(False)
        self.clone_cancel_btn.clicked.connect(lambda: self._cancel_generation("clone"))
        clone_action_row.addWidget(self.clone_cancel_btn, 1)
        r1_l.addLayout(clone_action_row)
        
        r1_l.addSpacing(8)
        r1_l.addWidget(self._label("Kết Quả", "SectionTitle"))
        self.clone_status = QLabel("Trạng thái hệ thống: Sẵn sàng")
        self.clone_status.setWordWrap(True)
=======
        r1_l.setContentsMargins(24, 24, 24, 24)
        r1_l.addWidget(self._label("🚀 Xuất File", "SectionTitle"))
        self.clone_generate_btn = QPushButton("✨ BẮT ĐẦU TẠO GIỌNG")
        self.clone_generate_btn.setObjectName("PrimaryBtn")
        self.clone_generate_btn.setMinimumHeight(60)
        self.clone_generate_btn.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.clone_generate_btn.clicked.connect(self._start_clone_generation)
        r1_l.addWidget(self.clone_generate_btn)
        
        r1_l.addSpacing(24)
        r1_l.addWidget(self._label("🔊 Kết Quả", "SectionTitle"))
        self.clone_status = QLabel("Trạng thái hệ thống: Sẵn sàng")
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
        r1_l.addWidget(self.clone_status)

        self.clone_progress = QProgressBar()
        self.clone_progress.setRange(0, 100)
        self.clone_progress.setValue(0)
        r1_l.addWidget(self.clone_progress)

        self.clone_info = QPlainTextEdit()
        self.clone_info.setReadOnly(True)
<<<<<<< HEAD
        self.clone_info.setMinimumHeight(132)
        self.clone_info.setMaximumHeight(220)
=======
        self.clone_info.setMinimumHeight(100)
        self.clone_info.setMaximumHeight(200)
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
        r1_l.addWidget(self.clone_info)
        
        self.clone_log_info = QPlainTextEdit()
        self.clone_log_info.setReadOnly(True)
        self.clone_log_info.setPlaceholderText("Log xử lý...")
<<<<<<< HEAD
        self.clone_log_info.setMinimumHeight(150)
        self.clone_log_info.setMaximumHeight(220)
        r1_l.addWidget(self.clone_log_info)

        action_row = QHBoxLayout()
        self.play_result_btn = QPushButton("Phát Audio")
        self.play_result_btn.setEnabled(False)
        self.play_result_btn.setMinimumHeight(40)
        self.play_result_btn.clicked.connect(self._toggle_generated_audio)
        self.save_result_btn = QPushButton("Tải xuống WAV")
=======
        self.clone_log_info.setMaximumHeight(150)
        r1_l.addWidget(self.clone_log_info)

        action_row = QHBoxLayout()
        self.play_result_btn = QPushButton("▶ Phát Audio")
        self.play_result_btn.setEnabled(False)
        self.play_result_btn.setMinimumHeight(40)
        self.play_result_btn.clicked.connect(self._toggle_generated_audio)
        self.save_result_btn = QPushButton("💾 Tải xuống WAV")
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
        self.save_result_btn.setEnabled(False)
        self.save_result_btn.setMinimumHeight(40)
        self.save_result_btn.clicked.connect(self._save_output)
        action_row.addWidget(self.play_result_btn, 2)
        action_row.addWidget(self.save_result_btn, 1)
        r1_l.addLayout(action_row)

        right_col.addWidget(r1)
<<<<<<< HEAD
        right_col.addStretch(1)

        layout.addLayout(left_col, 7)
        layout.addLayout(right_col, 5)
=======

        layout.addLayout(left_col, 5)
        layout.addLayout(right_col, 4)
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
        return page

    def _build_design_page(self):
        page = QWidget()
        layout = QHBoxLayout(page)
<<<<<<< HEAD
        # layout.setContentsMargins(28, 28, 28, 28)
        # layout.setSpacing(20)

        left = self._card()
        left_l = QVBoxLayout(left)
        # left_l.setContentsMargins(24, 24, 24, 24)
        # left_l.setSpacing(12)
        left_l.addWidget(self._panel_badge("Bước 1 · Nội dung & concept"), alignment=Qt.AlignLeft)
        left_l.addWidget(self._label("Nội dung cần đọc", "SectionTitle"))
        self.design_text = QPlainTextEdit()
        self.design_text.setPlainText("Xin chào, đây là giọng nhân vật ảo trên bản desktop mới.")
        self.design_text.setMinimumHeight(150)
        self.design_text.setMaximumHeight(220)
        left_l.addWidget(self.design_text)
        left_l.addLayout(self._nonverbal_bar(self.design_text, lambda: None if self.design_lang.currentText() == "Tự động" else self.design_lang.currentText()))
        self.design_lang = QComboBox()
        self.design_lang.addItems(_ALL_LANGUAGES)
        left_l.addWidget(self._label("Ngôn ngữ", "SectionTitle"))
        left_l.addWidget(self.design_lang)

        left_l.addWidget(self._panel_badge("Bước 2 · Tạo tính cách giọng"), alignment=Qt.AlignLeft)
        left_l.addWidget(self._label("Tùy chỉnh nhân vật", "SectionTitle"))
        self.design_menus = {}
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
=======
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(24)
        layout.setAlignment(Qt.AlignTop)

        left_col = QVBoxLayout()
        left_col.setSpacing(16)

        c1 = self._card()
        c1_l = QVBoxLayout(c1)
        c1_l.setContentsMargins(24, 24, 24, 24)
        c1_l.addWidget(self._label("📝 Nội dung cần đọc", "SectionTitle"))
        self.design_text = QPlainTextEdit()
        self.design_text.setPlainText("Xin chào, đây là giọng nhân vật ảo trên bản desktop mới.")
        self.design_text.setMinimumHeight(120)
        c1_l.addWidget(self.design_text)
        left_col.addWidget(c1)

        c2 = self._card()
        c2_l = QVBoxLayout(c2)
        c2_l.setContentsMargins(24, 24, 24, 24)
        c2_l.addWidget(self._label("🎛️ Tùy chỉnh nhân vật", "SectionTitle"))
        c2_l.addWidget(self._label("Ngôn ngữ", "SubTitle"))
        self.design_lang = QComboBox()
        self.design_lang.addItems(_ALL_LANGUAGES)
        c2_l.addWidget(self.design_lang)
        
        c2_l.addSpacing(10)
        self.design_menus = {}
        grid = QGridLayout()
        idx = 0
        for label, values in _CATEGORIES.items():
            combo = QComboBox()
            combo.addItems(["Tự động"] + values)
            self.design_menus[label] = combo
            row = idx // 2
            col = (idx % 2) * 2
            lbl = QLabel(label)
            lbl.setObjectName("SubTitle")
            grid.addWidget(lbl, row * 2, col)
            grid.addWidget(combo, row * 2 + 1, col)
            idx += 1
        c2_l.addLayout(grid)
        left_col.addWidget(c2)

        left_col.addWidget(self._build_settings_group("design"))

        right_col = QVBoxLayout()
        right_col.setSpacing(16)
        right_col.setAlignment(Qt.AlignTop)

        r1 = self._card()
        r1_l = QVBoxLayout(r1)
        r1_l.setContentsMargins(24, 24, 24, 24)
        r1_l.addWidget(self._label("🚀 Xuất File", "SectionTitle"))
        self.design_generate_btn = QPushButton("✨ BẮT ĐẦU TẠO GIỌNG")
        self.design_generate_btn.setObjectName("PrimaryBtn")
        self.design_generate_btn.setMinimumHeight(56)
        self.design_generate_btn.setStyleSheet("font-size: 18px;")
        self.design_generate_btn.clicked.connect(self._start_design_generation)
        r1_l.addWidget(self.design_generate_btn)

        r1_l.addSpacing(24)
        r1_l.addWidget(self._label("🔊 Kết Quả", "SectionTitle"))
        self.design_status = QLabel("Trạng thái hệ thống: Sẵn sàng")
        r1_l.addWidget(self.design_status)

        self.design_info = QPlainTextEdit()
        self.design_info.setReadOnly(True)
        self.design_info.setMinimumHeight(80)
        self.design_info.setMaximumHeight(150)
        right_l.addWidget(self.design_info)

        self.design_log_info = QPlainTextEdit()
        self.design_log_info.setReadOnly(True)
        self.design_log_info.setPlaceholderText("Log xử lý...")
        self.design_log_info.setMaximumHeight(150)
        right_l.addWidget(self.design_log_info)

        action_row = QHBoxLayout()
        self.design_play_btn = QPushButton("▶ Phát Audio")
        self.design_play_btn.setEnabled(False)
        self.design_play_btn.setMinimumHeight(40)
        self.design_play_btn.clicked.connect(self._toggle_generated_audio)
        self.design_save_btn = QPushButton("💾 Tải xuống WAV")
        self.design_save_btn.setEnabled(False)
        self.design_save_btn.setMinimumHeight(40)
        self.design_save_btn.clicked.connect(self._save_output)
        action_row.addWidget(self.design_play_btn, 2)
        action_row.addWidget(self.design_save_btn, 1)
        r1_l.addLayout(action_row)

        right_col.addWidget(r1)

        layout.addLayout(left_col, 5)
        layout.addLayout(right_col, 4)
        return page

    def _build_design_page(self):
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setSpacing(16)

        left = self._card()
        left_l = QVBoxLayout(left)
        left_l.setContentsMargins(24, 24, 24, 24)
        left_l.addWidget(self._label("📝 Nội dung cần đọc", "SectionTitle"))
        self.design_text = QPlainTextEdit()
        self.design_text.setPlainText("Xin chào, đây là giọng nhân vật ảo trên bản desktop mới.")
        left_l.addWidget(self.design_text)
        self.design_lang = QComboBox()
        self.design_lang.addItems(_ALL_LANGUAGES)
        left_l.addWidget(self._label("🌐 Ngôn ngữ", "SectionTitle"))
        left_l.addWidget(self.design_lang)

        left_l.addWidget(self._label("🎛️ Tùy chỉnh nhân vật", "SectionTitle"))
        self.design_menus = {}
        grid = QGridLayout()
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
        idx = 0
        for label, values in _CATEGORIES.items():
            combo = QComboBox()
            combo.addItems(["Tự động"] + values)
            self.design_menus[label] = combo
            row = idx // 2
            col = (idx % 2) * 2
            grid.addWidget(QLabel(label), row, col)
            grid.addWidget(combo, row, col + 1)
            idx += 1
        left_l.addLayout(grid)
<<<<<<< HEAD
        left_l.addWidget(self._build_settings_group("design"))

        self.design_generate_btn = QPushButton("BẮT ĐẦU TẠO GIỌNG")
        self.design_generate_btn.setObjectName("PrimaryBtn")
        self.design_generate_btn.setMinimumHeight(60)
        self.design_generate_btn.clicked.connect(self._start_design_generation)
        self.design_cancel_btn = QPushButton("HỦY")
        self.design_cancel_btn.setMinimumHeight(60)
        self.design_cancel_btn.setEnabled(False)
        self.design_cancel_btn.clicked.connect(lambda: self._cancel_generation("design"))
        design_action_row = QHBoxLayout()
        design_action_row.setSpacing(12)
        design_action_row.addWidget(self.design_generate_btn, 3)
        design_action_row.addWidget(self.design_cancel_btn, 1)
        left_l.addLayout(design_action_row)
        left_l.addStretch(1)

        right = self._card()
        right_l = QVBoxLayout(right)
        # right_l.setContentsMargins(24, 24, 24, 24)
        # right_l.setSpacing(12)
        right_l.addWidget(self._panel_badge("Bước 3 · Xem kết quả"), alignment=Qt.AlignLeft)
        self.design_status = QLabel("Chưa tạo")
        self.design_status.setWordWrap(True)
        self.design_info = QPlainTextEdit()
        self.design_info.setReadOnly(True)
        self.design_info.setMinimumHeight(132)
        self.design_info.setMaximumHeight(220)
=======
        self.design_generate_btn = QPushButton("✨ BẮT ĐẦU TẠO GIỌNG")
        self.design_generate_btn.setObjectName("PrimaryBtn")
        self.design_generate_btn.clicked.connect(self._start_design_generation)
        left_l.addWidget(self.design_generate_btn)

        right = self._card()
        right_l = QVBoxLayout(right)
        right_l.setContentsMargins(24, 24, 24, 24)
        self.design_status = QLabel("Chưa tạo")
        self.design_info = QPlainTextEdit()
        self.design_info.setReadOnly(True)
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
        self.design_play_btn = QPushButton("Phát kết quả")
        self.design_play_btn.setEnabled(False)
        self.design_play_btn.clicked.connect(self._toggle_generated_audio)
        self.design_save_btn = QPushButton("Lưu WAV")
        self.design_save_btn.setEnabled(False)
        self.design_save_btn.clicked.connect(self._save_output)
<<<<<<< HEAD
        right_l.addWidget(self._label("Kết quả thiết kế giọng", "SectionTitle"))
=======
        right_l.addWidget(self._label("🔊 Kết quả thiết kế giọng", "SectionTitle"))
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
        right_l.addWidget(self.design_status)

        self.design_progress = QProgressBar()
        self.design_progress.setRange(0, 100)
        self.design_progress.setValue(0)
        right_l.addWidget(self.design_progress)

        right_l.addWidget(self.design_info, 1)

        self.design_log_info = QPlainTextEdit()
        self.design_log_info.setReadOnly(True)
        self.design_log_info.setPlaceholderText("Log xử lý...")
<<<<<<< HEAD
        self.design_log_info.setMinimumHeight(150)
        self.design_log_info.setMaximumHeight(220)
        right_l.addWidget(self.design_log_info)

        result_action_row = QHBoxLayout()
        result_action_row.setSpacing(12)
        result_action_row.addWidget(self.design_play_btn, 2)
        result_action_row.addWidget(self.design_save_btn, 1)
        right_l.addLayout(result_action_row)
        right_l.addStretch(1)

        layout.addWidget(left, 7)
        layout.addWidget(right, 5)
        return page

    def _build_settings_page(self):
        page = self._card()
        layout = QVBoxLayout(page)
        # layout.setContentsMargins(24, 24, 24, 24)
        layout.addWidget(self._label("Cài Đặt Nâng Cao", "SectionTitle"))
=======
        self.design_log_info.setMaximumHeight(170)
        right_l.addWidget(self.design_log_info)

        right_l.addWidget(self.design_play_btn)
        right_l.addWidget(self.design_save_btn)

        layout.addWidget(left, 5)
        layout.addWidget(right, 4)
        return page

    def _switch_page(self, index: int):
        current = self.stack.currentWidget()
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self._nav_buttons):
            if i == index:
                btn.setObjectName("NavBtnActive")
            else:
                btn.setObjectName("NavBtn")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        page = self.stack.currentWidget()
        page.setWindowOpacity(0.0)
        animation = QPropertyAnimation(page, b"windowOpacity", self)
        animation.setDuration(220)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        animation.start()
        self._page_animation = animation

    def _build_settings_page(self):
        page = self._card()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.addWidget(self._label("⚙️ Cài Đặt Nâng Cao", "SectionTitle"))
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d

        self.num_step = QSpinBox()
        self.num_step.setRange(4, 64)
        self.num_step.setValue(32)
        self.guidance = QDoubleSpinBox()
        self.guidance.setRange(0.0, 8.0)
        self.guidance.setSingleStep(0.1)
        self.guidance.setValue(2.0)
        self.speed = QDoubleSpinBox()
        self.speed.setRange(0.5, 2.0)
        self.speed.setSingleStep(0.05)
        self.speed.setValue(1.0)
        self.duration = QDoubleSpinBox()
        self.duration.setRange(0.0, 9999.0)
        self.duration.setValue(0.0)
        self.duration.setSingleStep(0.5)
        self.denoise = QCheckBox("Khử ồn")
        self.denoise.setChecked(True)
        self.preprocess = QCheckBox("Tiền xử lý mẫu")
        self.preprocess.setChecked(True)
        self.postprocess = QCheckBox("Hậu xử lý đầu ra")
        self.postprocess.setChecked(True)

        for label, widget in [
            ("Inference steps", self.num_step),
            ("Guidance scale", self.guidance),
            ("Tốc độ", self.speed),
            ("Thời lượng ép", self.duration),
        ]:
            layout.addWidget(QLabel(label))
            layout.addWidget(widget)

        layout.addWidget(self.denoise)
        layout.addWidget(self.preprocess)
        layout.addWidget(self.postprocess)
        layout.addStretch(1)
        return page

    def _build_generation_config(self, prefix: str):
        num_step = getattr(self, f"{prefix}_num_step").value()
        guidance = getattr(self, f"{prefix}_guidance").value()
        denoise = getattr(self, f"{prefix}_denoise").isChecked()
        preprocess = getattr(self, f"{prefix}_preprocess").isChecked()
        postprocess = getattr(self, f"{prefix}_postprocess").isChecked()
        return OmniVoiceGenerationConfig(
            num_step=int(num_step),
            guidance_scale=float(guidance),
            denoise=denoise,
            preprocess_prompt=preprocess,
            postprocess_output=postprocess,
        )

    def _browse_source(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn media mẫu", "", "Media (*.wav *.mp3 *.flac *.m4a *.aac *.mp4 *.mov *.mkv *.avi);;All Files (*.*)")
        if not path:
            return
        self.current_source = path
        self.clone_file.setText(path)
        self.clone_status.setText(f"Đã chọn: {Path(path).name}")
        self.media_player.setSource(Path(path).as_uri())
        # self.preview_pos.setValue(0) # Removed because preview_pos is not an attribute anymore
        try:
            if Path(path).suffix.lower() in {".mp4", ".mov", ".mkv", ".avi"}:
                extracted = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
                extracted.close()
                self._extract_audio_from_video(path, extracted.name)
                duration_audio = AudioSegment.from_file(extracted.name)
            else:
                duration_audio = AudioSegment.from_file(path)
            
            samples = np.array(duration_audio.get_array_of_samples())
            if duration_audio.channels == 2:
                samples = samples[::2]
            num_points = 100
            chunk_size = max(1, len(samples) // num_points)
            waveform = []
            if chunk_size > 0:
                for i in range(num_points):
                    chunk = samples[i * chunk_size : (i+1) * chunk_size]
                    if len(chunk) > 0:
                        waveform.append(float(np.max(np.abs(chunk))) / 32768.0)
            self.range_selector.set_waveform(waveform)

            self.duration_seconds = max(1.0, len(duration_audio) / 1000.0)
            self.range_selector.set_total_duration(self.duration_seconds)
            self.range_selector.set_values(0.0, min(8.0, self.duration_seconds))
            self.trim_start.setValue(0.0)
            self.trim_end.setValue(min(8.0, self.duration_seconds))
            # self.preview_pos.setRange(0, int(self.duration_seconds * 1000))
        except Exception:
            self.duration_seconds = 10.0

    def _toggle_media_preview(self):
        if self.media_player.playbackState() == QMediaPlayer.PlayingState:
            self.media_player.pause()
<<<<<<< HEAD
            self.preview_play_btn.setText("Phát đoạn đã cắt")
        else:
            self.media_player.setPosition(int(self.trim_start.value() * 1000))
            self.media_player.play()
            self.preview_play_btn.setText("Dừng")
=======
            self.preview_play_btn.setText("▶ Phát đoạn đã cắt")
        else:
            self.media_player.setPosition(int(self.trim_start.value() * 1000))
            self.media_player.play()
            self.preview_play_btn.setText("⏸ Dừng")
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d

    def _on_player_position_changed(self, pos_ms: int):
        pos_sec = pos_ms / 1000.0
        self.range_selector.set_playhead(pos_sec)
        if pos_sec >= self.trim_end.value() and self.media_player.playbackState() == QMediaPlayer.PlayingState:
            self.media_player.pause()
<<<<<<< HEAD
            self.preview_play_btn.setText("Phát đoạn đã cắt")
=======
            self.preview_play_btn.setText("▶ Phát đoạn đã cắt")
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
            self.range_selector.set_playhead(0)

    def _sync_trim_spinboxes(self, start_value: float, end_value: float):
        self.trim_start.blockSignals(True)
        self.trim_end.blockSignals(True)
        self.trim_start.setValue(start_value)
        self.trim_end.setValue(end_value)
        self.trim_start.blockSignals(False)
        self.trim_end.blockSignals(False)

    def _sync_range_from_spin(self):
        self.range_selector.set_values(self.trim_start.value(), self.trim_end.value())

    def _extract_audio_from_video(self, video_path: str, output_wav: str):
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        command = [ffmpeg_exe, "-y", "-i", video_path, "-vn", "-ac", "1", "-ar", "24000", output_wav]
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _prepare_reference_audio(self):
        source = self.clone_file.text().strip()
        if not source:
            raise ValueError("Chưa chọn file mẫu.")
        suffix = Path(source).suffix.lower()
        working_source = source
        if suffix in {".mp4", ".mov", ".mkv", ".avi"}:
            extracted = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
            extracted.close()
            self._extract_audio_from_video(source, extracted.name)
            working_source = extracted.name

        audio = AudioSegment.from_file(working_source)
        start_sec = self.trim_start.value()
        end_sec = self.trim_end.value()
        if end_sec <= start_sec:
            raise ValueError("Khoảng cắt không hợp lệ.")
        trimmed = audio[int(start_sec * 1000): int(end_sec * 1000)]
        temp_ref = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        temp_ref.close()
        trimmed.export(temp_ref.name, format="wav")
        self.current_processed_ref = temp_ref.name
        return temp_ref.name, start_sec, end_sec

    def _prepare_reference_preview(self):
        pass

    def _start_clone_generation(self):
        transcript = self.clone_ref_text.toPlainText().strip() or None
        asr_loaded = getattr(self.model, "_asr_pipe", None) is not None
        if not transcript and not asr_loaded:
            QMessageBox.warning(self, "Thiếu transcript", "Bản local hiện đang tắt ASR (tự động nghe) để tránh nặng máy. Bạn phải nhập sẵn lời của file mẫu (Transcript) để Clone giọng.\n\nNếu muốn dùng tính năng tự động nghe, hãy tích chọn 'Bật ASR' lúc khởi động.")
            return
        if not self.clone_text.toPlainText().strip():
            QMessageBox.warning(self, "Thiếu nội dung", "Nhập nội dung cần đọc đã.")
            return
        try:
            ref_path, start_sec, end_sec = self._prepare_reference_audio()
        except Exception as exc:
            QMessageBox.critical(self, "Lỗi xử lý mẫu", str(exc))
            return
        self.clone_generate_btn.setEnabled(False)
        self.clone_status.setText("Đang clone giọng...")
        payload = {
            "text": self.clone_text.toPlainText().strip(),
            "language": None if self.clone_lang.currentText() == "Tự động" else self.clone_lang.currentText(),
            "generation_config": self._build_generation_config("clone"),
            "ref_audio": ref_path,
            "ref_text": transcript,
            "speed": float(self.clone_speed.value()),
            "duration": float(self.clone_duration.value()),
            "start": start_sec,
            "end": end_sec,
            "chunk_chars": self._suggest_chunk_chars(self.clone_text.toPlainText().strip()),
        }
        self._run_worker("clone", payload)

    def _build_design_instruct(self):
        parts = []
        for label, combo in self.design_menus.items():
            value = combo.currentText()
            if value != "Tự động":
                parts.append(_VI_TO_INSTRUCT.get(value, value))
        return ", ".join(parts) if parts else None

    def _start_design_generation(self):
        if not self.design_text.toPlainText().strip():
            QMessageBox.warning(self, "Thiếu nội dung", "Nhập nội dung cần đọc đã.")
            return
        self.design_generate_btn.setEnabled(False)
        self.design_status.setText("Đang thiết kế giọng...")
        payload = {
            "text": self.design_text.toPlainText().strip(),
            "language": None if self.design_lang.currentText() == "Tự động" else self.design_lang.currentText(),
            "generation_config": self._build_generation_config("design"),
            "instruct": self._build_design_instruct(),
            "speed": float(self.design_speed.value()),
            "duration": float(self.design_duration.value()),
            "chunk_chars": self._suggest_chunk_chars(self.design_text.toPlainText().strip()),
        }
        self._run_worker("design", payload)

    def _run_worker(self, mode: str, payload: dict):
<<<<<<< HEAD
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "Đang bận", "Hiện đang có một tác vụ tạo giọng chạy rồi. Hãy đợi xong hoặc bấm Hủy.")
            return
        self._worker_token_seed += 1
        worker_token = self._worker_token_seed
        self._active_worker_token = worker_token
=======
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
        self._runtime_state[mode] = {
            "started_at": time.perf_counter(),
            "payload": payload.copy(),
        }
<<<<<<< HEAD
        self.active_mode = mode
        if mode == "clone":
            self.clone_generate_btn.setText("ĐANG XỬ LÝ...")
=======
        if mode == "clone":
            self.clone_generate_btn.setText("⏳ ĐANG XỬ LÝ...")
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
            self.clone_status.setText("Trạng thái hệ thống: Đang chạy...")
            self.clone_progress.setValue(1)
            self.clone_log_info.clear()
            self.clone_info.setPlainText(self._build_runtime_summary(mode, payload))
<<<<<<< HEAD
            self.clone_cancel_btn.setEnabled(True)
            self.design_generate_btn.setEnabled(False)
            self._log_event(mode, "INFO", "Đã bắt đầu job clone giọng.")
        else:
            self.design_generate_btn.setText("ĐANG XỬ LÝ...")
=======
            self._log_event(mode, "INFO", "Đã bắt đầu job clone giọng.")
        else:
            self.design_generate_btn.setText("⏳ ĐANG XỬ LÝ...")
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
            self.design_status.setText("Trạng thái hệ thống: Đang chạy...")
            self.design_progress.setValue(1)
            self.design_log_info.clear()
            self.design_info.setPlainText(self._build_runtime_summary(mode, payload))
<<<<<<< HEAD
            self.design_cancel_btn.setEnabled(True)
            self.clone_generate_btn.setEnabled(False)
            self._log_event(mode, "INFO", "Đã bắt đầu job thiết kế giọng.")
            
        self.worker = GenerationWorker(self.model, mode, payload)
        self.worker.progress.connect(lambda text, val, m=mode, t=worker_token: self._update_progress(m, text, val, t))
        self.worker.success.connect(lambda audio, meta, m=mode, t=worker_token: self._on_worker_success(m, audio, meta, t))
        self.worker.error.connect(lambda message, detail, m=mode, t=worker_token: self._on_worker_error(m, message, detail, t))
        self.worker.finished.connect(lambda w=self.worker: self._on_worker_finished(w))
        self.worker.start()

    def _cancel_generation(self, mode: str):
        if mode != self.active_mode:
            return
        if not self.worker or not self.worker.isRunning():
            return
        self.worker.cancel()
        if mode == "clone":
            self.clone_cancel_btn.setEnabled(False)
            self.clone_status.setText("Trạng thái hệ thống: Đang hủy để bạn tiếp tục chỉnh sửa...")
            self.clone_info.setPlainText(
                "\n".join([
                    "Đang hủy clone giọng.",
                    "",
                    f"Thiết bị: {self._device_label()}",
                    "App sẽ giữ nguyên để bạn chỉnh sửa nội dung và chạy lại.",
                ])
            )
            self._log_event(mode, "CANCEL", "Người dùng yêu cầu hủy clone giọng để chỉnh sửa tiếp.")
        else:
            self.design_cancel_btn.setEnabled(False)
            self.design_status.setText("Trạng thái hệ thống: Đang hủy để bạn tiếp tục chỉnh sửa...")
            self.design_info.setPlainText(
                "\n".join([
                    "Đang hủy thiết kế giọng.",
                    "",
                    f"Thiết bị: {self._device_label()}",
                    "App sẽ giữ nguyên để bạn chỉnh sửa nội dung và chạy lại.",
                ])
            )
            self._log_event(mode, "CANCEL", "Người dùng yêu cầu hủy thiết kế giọng để chỉnh sửa tiếp.")

    def _reset_generation_ui(self, mode: str):
        self.active_mode = None
        self.clone_generate_btn.setEnabled(True)
        self.clone_generate_btn.setText("BẮT ĐẦU TẠO GIỌNG")
        self.clone_cancel_btn.setEnabled(False)
        self.design_generate_btn.setEnabled(True)
        self.design_generate_btn.setText("BẮT ĐẦU TẠO GIỌNG")
        self.design_cancel_btn.setEnabled(False)

    def _update_progress(self, mode: str, text: str, value: int, worker_token: int | None = None):
        if worker_token is not None and worker_token != self._active_worker_token:
            return
=======
            self._log_event(mode, "INFO", "Đã bắt đầu job thiết kế giọng.")
            
        self.worker = GenerationWorker(self.model, mode, payload)
        self.worker.progress.connect(lambda text, val, m=mode: self._update_progress(m, text, val))
        self.worker.success.connect(lambda audio, meta, m=mode: self._on_worker_success(m, audio, meta))
        self.worker.error.connect(lambda message, detail, m=mode: self._on_worker_error(m, message, detail))
        self.worker.start()

    def _update_progress(self, mode: str, text: str, value: int):
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
        if mode == "clone":
            self.clone_status.setText("Trạng thái hệ thống: " + text)
            self.clone_progress.setValue(value)
        else:
            self.design_status.setText("Trạng thái hệ thống: " + text)
            self.design_progress.setValue(value)
        self._log_event(mode, "STEP", f"[{value}%] {text}")

<<<<<<< HEAD
    def _on_worker_success(self, mode: str, audio, meta: dict, worker_token: int | None = None):
        if worker_token is not None and worker_token != self._active_worker_token:
            return
        self._active_worker_token = None
        self._reset_generation_ui(mode)
=======
    def _on_worker_success(self, mode: str, audio, meta: dict):
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
        self.audio_output = audio
        elapsed_s = meta.get("elapsed_s") or self._elapsed_for_mode(mode)
        if mode == "clone":
            self.clone_status.setText("Trạng thái hệ thống: Hoàn thành xuất sắc!")
            self.clone_progress.setValue(100)
            self.play_result_btn.setEnabled(True)
            self.save_result_btn.setEnabled(True)
<<<<<<< HEAD
            self.clone_info.setPlainText(
                "\n".join([
                    "Đã clone giọng xong.",
=======
            self.clone_generate_btn.setEnabled(True)
            self.clone_generate_btn.setText("✨ BẮT ĐẦU TẠO GIỌNG")
            self.clone_info.setPlainText(
                "\n".join([
                    "✅ Đã clone giọng xong.",
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
                    "",
                    f"Thiết bị: {self._device_label()}",
                    f"Thời gian xử lý: {elapsed_s:.2f}s",
                    f"Độ dài audio xuất ra: {meta.get('output_seconds', 0.0):.2f}s",
                    f"Độ dài văn bản: {meta.get('text_length', 0)} ký tự",
                    f"Số chunk đã chạy: {meta.get('chunk_count', 1)}",
                    f"Ngôn ngữ: {meta.get('language') or 'Tự động'}",
                    f"Đoạn mẫu dùng: {meta.get('start', 0):.2f}s -> {meta.get('end', 0):.2f}s",
                    f"File mẫu: {meta.get('ref_audio', '')}",
                    f"Tốc độ: {meta.get('speed', 1.0)}",
                    f"Duration ép: {meta.get('duration', 0.0)}",
                ])
            )
        else:
            self.design_status.setText("Trạng thái hệ thống: Hoàn thành xuất sắc!")
            self.design_progress.setValue(100)
            self.design_play_btn.setEnabled(True)
            self.design_save_btn.setEnabled(True)
<<<<<<< HEAD
            self.design_info.setPlainText(
                "\n".join([
                    "Thiết kế giọng thành công.",
=======
            self.design_generate_btn.setEnabled(True)
            self.design_generate_btn.setText("✨ BẮT ĐẦU TẠO GIỌNG")
            self.design_info.setPlainText(
                "\n".join([
                    "✅ Thiết kế giọng thành công.",
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
                    "",
                    f"Thiết bị: {self._device_label()}",
                    f"Thời gian xử lý: {elapsed_s:.2f}s",
                    f"Độ dài audio xuất ra: {meta.get('output_seconds', 0.0):.2f}s",
                    f"Độ dài văn bản: {meta.get('text_length', 0)} ký tự",
                    f"Số chunk đã chạy: {meta.get('chunk_count', 1)}",
                    f"Ngôn ngữ: {meta.get('language') or 'Tự động'}",
                    f"Thuộc tính dùng: {meta.get('instruct', 'Auto Voice') or 'Auto Voice'}",
                    f"Tốc độ: {meta.get('speed', 1.0)}",
                    f"Duration ép: {meta.get('duration', 0.0)}",
                ])
            )
        self._log_event(mode, "DONE", f"Hoàn tất sau {elapsed_s:.2f}s. Audio đầu ra {meta.get('output_seconds', 0.0):.2f}s.")

<<<<<<< HEAD
    def _on_worker_error(self, mode: str, message: str, detail: str, worker_token: int | None = None):
        if worker_token is not None and worker_token != self._active_worker_token:
            return
        elapsed_s = self._elapsed_for_mode(mode)
        self._active_worker_token = None
        self._reset_generation_ui(mode)
        cancelled = message == "Đã hủy tác vụ"
        if mode == "clone":
            self.clone_status.setText("Trạng thái hệ thống: Đã hủy." if cancelled else f"Lỗi: {message}")
            self.clone_progress.setValue(100)
            self.clone_info.setPlainText(
                "\n".join([
                    "Đã hủy clone giọng." if cancelled else "Clone giọng thất bại.",
                    "",
                    f"Thiết bị: {self._device_label()}",
                    f"Thời gian trước khi dừng: {elapsed_s:.2f}s" if cancelled else f"Thời gian trước khi lỗi: {elapsed_s:.2f}s",
                    "Tác vụ sẽ dừng sau chunk hiện tại để tránh crash app." if cancelled else f"Lỗi chính: {message}",
                    *( [] if cancelled else ["", "Traceback chi tiết:", detail.strip()] ),
                ])
            )
        else:
            self.design_status.setText("Trạng thái hệ thống: Đã hủy." if cancelled else f"Lỗi: {message}")
            self.design_progress.setValue(100)
            self.design_info.setPlainText(
                "\n".join([
                    "Đã hủy thiết kế giọng." if cancelled else "Thiết kế giọng thất bại.",
                    "",
                    f"Thiết bị: {self._device_label()}",
                    f"Thời gian trước khi dừng: {elapsed_s:.2f}s" if cancelled else f"Thời gian trước khi lỗi: {elapsed_s:.2f}s",
                    "Tác vụ sẽ dừng sau chunk hiện tại để tránh crash app." if cancelled else f"Lỗi chính: {message}",
                    *( [] if cancelled else ["", "Traceback chi tiết:", detail.strip()] ),
                ])
            )
        if cancelled:
            self._log_event(mode, "CANCEL", "Người dùng đã hủy tác vụ tạo giọng.")
        else:
            self._log_event(mode, "ERROR", message)
            for line in detail.strip().splitlines():
                self._log_event(mode, "TRACE", line)
            QMessageBox.critical(self, "Lỗi hệ thống", message)

    def _on_worker_finished(self, worker: GenerationWorker):
        if self.worker is worker:
            self.worker = None
        self._finished_workers.append(worker)
        worker.deleteLater()
        QTimer.singleShot(0, self._finished_workers.clear)
=======
    def _on_worker_error(self, mode: str, message: str, detail: str):
        elapsed_s = self._elapsed_for_mode(mode)
        if mode == "clone":
            self.clone_status.setText(f"❌ Lỗi: {message}")
            self.clone_progress.setValue(100)
            self.clone_generate_btn.setEnabled(True)
            self.clone_generate_btn.setText("✨ BẮT ĐẦU TẠO GIỌNG")
            self.clone_info.setPlainText(
                "\n".join([
                    "❌ Clone giọng thất bại.",
                    "",
                    f"Thiết bị: {self._device_label()}",
                    f"Thời gian trước khi lỗi: {elapsed_s:.2f}s",
                    f"Lỗi chính: {message}",
                    "",
                    "Traceback chi tiết:",
                    detail.strip(),
                ])
            )
        else:
            self.design_status.setText(f"❌ Lỗi: {message}")
            self.design_progress.setValue(100)
            self.design_generate_btn.setEnabled(True)
            self.design_generate_btn.setText("✨ BẮT ĐẦU TẠO GIỌNG")
            self.design_info.setPlainText(
                "\n".join([
                    "❌ Thiết kế giọng thất bại.",
                    "",
                    f"Thiết bị: {self._device_label()}",
                    f"Thời gian trước khi lỗi: {elapsed_s:.2f}s",
                    f"Lỗi chính: {message}",
                    "",
                    "Traceback chi tiết:",
                    detail.strip(),
                ])
            )
        self._log_event(mode, "ERROR", message)
        for line in detail.strip().splitlines():
            self._log_event(mode, "TRACE", line)
        QMessageBox.critical(self, "Lỗi hệ thống", message)
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d

    def _build_runtime_summary(self, mode: str, payload: dict) -> str:
        config = payload["generation_config"]
        lines = [
            f"Mode: {'Clone giọng' if mode == 'clone' else 'Thiết kế giọng'}",
            f"Thiết bị: {self._device_label()}",
<<<<<<< HEAD
            f"ASR: {'Báº­t' if getattr(self.model, '_asr_pipe', None) is not None else 'Táº¯t'}",
=======
            f"ASR: {'Bật' if getattr(self.model, '_asr_pipe', None) is not None else 'Tắt'}",
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
            f"Ngôn ngữ: {payload.get('language') or 'Tự động'}",
            f"Số ký tự đầu vào: {len(payload.get('text', ''))}",
            f"Inference steps: {config.num_step}",
            f"Guidance scale: {config.guidance_scale}",
            f"Khử ồn: {'Có' if config.denoise else 'Không'}",
            f"Tiền xử lý mẫu: {'Có' if config.preprocess_prompt else 'Không'}",
            f"Hậu xử lý đầu ra: {'Có' if config.postprocess_output else 'Không'}",
            f"Tốc độ: {payload.get('speed', 1.0)}",
            f"Duration ép: {payload.get('duration', 0.0)}",
            f"Chunk chars mục tiêu: {payload.get('chunk_chars', 0)}",
        ]
        if mode == "clone":
            lines.extend([
                f"Transcript mẫu: {'Có' if payload.get('ref_text') else 'Không'}",
                f"Đoạn cắt mẫu: {payload.get('start', 0.0):.2f}s -> {payload.get('end', 0.0):.2f}s",
                f"File mẫu: {payload.get('ref_audio', '')}",
            ])
        else:
            lines.append(f"Thuộc tính giọng: {payload.get('instruct') or 'Auto Voice'}")
        return "\n".join(lines)

    def _elapsed_for_mode(self, mode: str) -> float:
        started_at = self._runtime_state.get(mode, {}).get("started_at")
        if not started_at:
            return 0.0
        return time.perf_counter() - started_at

    def _suggest_chunk_chars(self, text: str) -> int:
        text_len = len(text.strip())
        if text_len <= 500:
            return 0
        if text_len <= 4000:
            return 260
        return 220

    def _device_label(self) -> str:
        device = getattr(self.model, "device", None)
        return str(device or get_best_device()).upper()

    def _refresh_runtime_badge(self):
        cuda_ok = torch.cuda.is_available()
        asr_on = getattr(self.model, "_asr_pipe", None) is not None
        badge = [
            f"Runtime: {self._device_label()}",
            f"CUDA: {'ON' if cuda_ok else 'OFF'}",
            f"ASR: {'ON' if asr_on else 'OFF'}",
        ]
        if cuda_ok:
            try:
                gpu_name = torch.cuda.get_device_name(0)
                badge.append(f"GPU: {gpu_name}")
            except Exception:
                pass
        else:
            badge.append("GPU chưa khả dụng")
        self.runtime_badge.setText(" | ".join(badge))

    def _log_event(self, mode: str, level: str, message: str):
        line = f"[{level}] {message}"
        if mode == "clone":
            self.clone_log_info.appendPlainText(line)
        else:
            self.design_log_info.appendPlainText(line)

    def _toggle_generated_audio(self):
        if self.audio_output is None:
            return
        if self.is_playing:
            sd.stop()
            self.is_playing = False
            self.play_result_btn.setText("Phát kết quả")
            self.design_play_btn.setText("Phát kết quả")
            return
        self.is_playing = True
        self.play_result_btn.setText("Dừng")
        self.design_play_btn.setText("Dừng")
        sd.play(self.audio_output, self.sampling_rate)

    def _save_output(self):
        if self.audio_output is None:
            return
        output, _ = QFileDialog.getSaveFileName(self, "Lưu WAV", "", "WAV (*.wav)")
        if output:
            sf.write(output, self.audio_output, self.sampling_rate)
            QMessageBox.information(self, "Đã lưu", output)

    def _save_processed_ref(self):
        if not self.current_processed_ref or not os.path.exists(self.current_processed_ref):
            QMessageBox.warning(self, "Chưa có mẫu", "Bạn chưa xử lý mẫu.")
            return
        output, _ = QFileDialog.getSaveFileName(self, "Lưu mẫu đã cắt", "", "WAV (*.wav)")
        if output:
            audio, sr = sf.read(self.current_processed_ref)
            sf.write(output, audio, sr)
            QMessageBox.information(self, "Đã lưu", output)

    def _append_log(self, text: str):
        line = text.strip()
        if not line:
            return
            
        if line.startswith("[STEP_PROGRESS]"):
            try:
<<<<<<< HEAD
                if self._active_worker_token is None or not self.active_mode:
                    return
                parts = line.split(" ")[1].split("/")
                step = int(parts[0])
                total = int(parts[1])
                mode = self.active_mode
=======
                parts = line.split(" ")[1].split("/")
                step = int(parts[0])
                total = int(parts[1])
                mode = "clone" if (self.worker and self.worker.mode == "clone") else "design"
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
                pct = 45 + int((step / total) * 50)  # Progress between 45 and 95
                self._update_progress(mode, f"Đang suy luận (bước {step}/{total})...", pct)
            except Exception:
                pass
            return
            
        if hasattr(self, "clone_log_info"):
            self.clone_log_info.appendPlainText(f"[SYS] {line}")
        if hasattr(self, "design_log_info"):
            self.design_log_info.appendPlainText(f"[SYS] {line}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="k2-fsa/OmniVoice")
    parser.add_argument("--asr-model", default="openai/whisper-large-v3-turbo")
    parser.add_argument("--smoke-test", action="store_true", default=False)
    parser.add_argument("--smoke-seconds", type=float, default=4.0)
    parser.add_argument("--no-asr", action="store_true", default=False, help="Tắt ASR để tiết kiệm RAM")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    app.setApplicationName("OMNIVOICE STUDIO")

    device = get_best_device()
    dtype = torch.float16 if device != "cpu" else torch.float32
<<<<<<< HEAD
    
    # Háº¡n cháº¿ GPU cháº¡y 100% báº±ng cÃ¡ch giáº£m luá»“ng OMP vÃ  Torch Thread
    import os
    os.environ["OMP_NUM_THREADS"] = "1"
    torch.set_num_threads(1)
    
=======
>>>>>>> 5766eb7d6be95cb98d3fc2076e1f63567e773b2d
    print(f"Dang nap model tren {device}...")
    model = OmniVoice.from_pretrained(args.model, asr_model_name=args.asr_model, device_map=device, dtype=dtype, load_asr=not args.no_asr)
    print("Nap model xong.")

    window = OmniVoiceQtWindow(model)
    window.show()
    if args.smoke_test:
        print("Qt smoke test mode dang chay.")
        QTimer.singleShot(int(args.smoke_seconds * 1000), app.quit)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
