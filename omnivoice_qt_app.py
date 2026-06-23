import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import logging
import time
import traceback
import threading
import re
import difflib
import hashlib
from pathlib import Path
from collections import Counter, OrderedDict

try:
    import winsound
except Exception:
    winsound = None

import imageio_ffmpeg
import numpy as np
import sounddevice as sd
import soundfile as sf
import torch
from pydub import AudioSegment
from PySide6.QtCore import QPoint, Property, QRect, Qt, QThread, Signal, QTimer, QObject
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QSyntaxHighlighter, QTextCharFormat
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
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
    QScrollArea,
)

from omnivoice import OmniVoice, OmniVoiceGenerationConfig
from omnivoice.session_recovery import SessionManager, get_temp_root
from omnivoice.utils.lang_map import LANG_NAMES, lang_display_name
from omnivoice.utils.text import (
    chunk_text_punctuation,
    ends_with_sensitive_vietnamese_term,
    map_vietnamese_emotions,
    normalize_vietnamese_numbers,
)
from omnivoice.utils.vi_sensitive_terms import VI_PRONUNCIATION_SENSITIVE_TERMS

try:
    from wordfreq import zipf_frequency, top_n_list
except Exception:
    zipf_frequency = None
    top_n_list = None


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


_GENERATION_PRESETS = {
    "fast": {
        "label": "Nhanh",
        "summary": "Toc do uu tien. Hop voi script dai, test nhanh, batch lon.",
        "steps": 12,
        "guidance": 1.2,
        "speed": 1.2,
    },
    "balanced": {
        "label": "Can bang",
        "summary": "De xuat cho workflow hang ngay. Nhanh hon ban cu nhung van on.",
        "steps": 16,
        "guidance": 1.5,
        "speed": 1.15,
    },
    "quality": {
        "label": "Chat luong",
        "summary": "Chi tiet hon nhung cham hon. Dung khi can output ky.",
        "steps": 32,
        "guidance": 2.0,
        "speed": 1.0,
    },
}


_LOCAL_TEMP_ROOT = get_temp_root()
_VOICE_PROMPT_CACHE_MAX = 4
_REFERENCE_AUDIO_CACHE_MAX = 4


def _named_temp_wav() -> tempfile.NamedTemporaryFile:
    _LOCAL_TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    return tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".wav",
        dir=str(_LOCAL_TEMP_ROOT),
    )


def parse_srt_blocks(srt_content: str) -> str:
    lines = srt_content.splitlines()
    blocks: list[str] = []
    current_block: list[str] = []
    is_text = False

    for raw_line in lines:
        line = raw_line.strip()
        if not line or re.fullmatch(r"\d+", line):
            if current_block:
                blocks.append(" ".join(current_block))
                current_block = []
            is_text = False
            continue
        if re.match(r"^\d{2}:\d{2}:\d{2}", line):
            is_text = True
            continue
        if is_text:
            current_block.append(line)

    if current_block:
        blocks.append(" ".join(current_block))
    return "\n".join(blocks)


def format_text_content(text: str) -> str:
    return re.sub(r"\s{2,}", " ", text.replace("\r", " ").replace("\n", " ")).strip()


def smart_sort_text_content(input_text: str) -> str:
    vi_lower = "aàảãáạăằẳẵắặâầẩẫấậeèẻẽéẹêềểễếệiìỉĩíịoòỏõóọôồổỗốộơờởỡớợuùủũúụưừửữứựyỳỷỹýỵđ"
    vi_upper = "AÀẢÃÁẠĂẰẲẴẮẶÂẦẨẪẤẬEÈẺẼÉẸÊỀỂỄẾỆIÌỈĨÍỊOÒỎÕÓỌÔỒỔỖỐỘƠỜỞỠỚỢUÙỦŨÚỤƯỪỬỮỨỰYỲỶỸÝỴĐ"
    tag_noise = r"\[(âm nhạc|music|tiếng cười|tạp âm|noise|background music|applause|laughs?|laughter)\]"

    text = re.sub(tag_noise, "", input_text, flags=re.IGNORECASE)
    text = re.sub(fr"([{vi_upper}][{vi_lower}]+)\.\s+([{vi_upper}][{vi_lower}]+)", r"\1 \2", text)
    text = re.sub(fr"([{vi_lower}a-z])\.\s+([{vi_lower}a-z])", r"\1 \2", text, flags=re.IGNORECASE)
    unified_text = re.sub(r"\s+", " ", text.replace("\r", " ").replace("\n", " ")).strip()
    if not unified_text:
        return ""

    sentence_break = re.compile(fr"(?<=[.!?])\s+(?=[{vi_upper}A-Z\"'])")
    dialogue_break = re.compile(r'(".*?")')
    simple_break = re.compile(r"(?<=[.!?])\s+")

    sentences = sentence_break.split(unified_text)
    final_lines: list[str] = []

    for sentence in sentences:
        parts = [part for part in dialogue_break.split(sentence) if part.strip()]
        for part in parts:
            trimmed = part.strip()
            if trimmed.startswith('"') and trimmed.endswith('"'):
                inner = trimmed[1:-1].strip()
                inner_parts = [piece.strip() for piece in simple_break.split(inner) if piece.strip()]
                if len(inner_parts) > 1:
                    final_lines.extend([f'"{piece}"' for piece in inner_parts])
                elif inner:
                    final_lines.append(f'"{inner}"')
            else:
                final_lines.extend([piece.strip() for piece in simple_break.split(trimmed) if piece.strip()])

    return "\n".join(line for line in final_lines if line)


_SPELL_TOKEN_RE = re.compile(r"[A-Za-zÀ-ỹà-ỹĐđ]+", re.UNICODE)
_SPELL_LEXICON_CACHE = None
_SPELL_INDEX_CACHE = None


def _build_spell_lexicon():
    global _SPELL_LEXICON_CACHE, _SPELL_INDEX_CACHE
    if _SPELL_LEXICON_CACHE is not None and _SPELL_INDEX_CACHE is not None:
        return _SPELL_LEXICON_CACHE, _SPELL_INDEX_CACHE

    lexicon: set[str] = set()
    if top_n_list is not None:
        try:
            lexicon.update(word.lower() for word in top_n_list("vi", 50000))
            lexicon.update(word.lower() for word in top_n_list("en", 12000))
        except Exception:
            pass

    lexicon.update(word.lower() for word in VI_PRONUNCIATION_SENSITIVE_TERMS)
    lexicon.update(
        {
            "tts", "srt", "txt", "wav", "mp3", "cuda", "asr", "cfg", "clone",
            "design", "workflow", "preview", "format", "youtube", "omnivoice",
            "local", "offline", "batch", "prompt", "prompts", "thumbnail",
            "tiktok", "facebook", "zalo", "ok", "oke", "audio", "video",
        }
    )
    lexicon = {word for word in lexicon if word and any(ch.isalpha() for ch in word)}

    index: dict[str, list[str]] = {}
    for word in lexicon:
        index.setdefault(word[:1], []).append(word)

    _SPELL_LEXICON_CACHE = lexicon
    _SPELL_INDEX_CACHE = index
    return _SPELL_LEXICON_CACHE, _SPELL_INDEX_CACHE


def _match_case_style(source: str, suggestion: str) -> str:
    if source.isupper():
        return suggestion.upper()
    if len(source) > 1 and source[0].isupper() and source[1:].islower():
        return suggestion[:1].upper() + suggestion[1:]
    return suggestion


class SpellcheckHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self._enabled = zipf_frequency is not None
        self._lexicon, self._index = _build_spell_lexicon()
        self._format = QTextCharFormat()
        self._format.setUnderlineStyle(QTextCharFormat.WaveUnderline)
        self._format.setUnderlineColor(QColor("#ff6b6b"))
        self._format.setBackground(QColor(255, 107, 107, 38))
        self._format.setForeground(QColor("#ffd7d7"))
        self._suggestion_cache: dict[str, list[str]] = {}

    def highlightBlock(self, text: str):
        if not self._enabled or not text.strip():
            return
        for match in _SPELL_TOKEN_RE.finditer(text):
            token = match.group(0)
            if self._is_suspicious(token):
                self.setFormat(match.start(), len(token), self._format)

    def _is_suspicious(self, token: str) -> bool:
        normalized = token.strip().lower()
        if not normalized or len(normalized) <= 1:
            return False
        if normalized in self._lexicon:
            return False
        if token.isupper() and len(token) <= 5:
            return False
        if normalized.startswith(("http", "www")):
            return False
        if "-" in normalized or "_" in normalized:
            return False
        if not any(ch.isalpha() for ch in normalized):
            return False

        vi_score = zipf_frequency(normalized, "vi") if zipf_frequency else 0.0
        en_score = zipf_frequency(normalized, "en") if zipf_frequency else 0.0
        if vi_score >= 2.2 or en_score >= 2.7:
            return False
        if len(normalized) <= 2 and max(vi_score, en_score) >= 1.6:
            return False
        return True

    def suggestions_for(self, token: str, limit: int = 5) -> list[str]:
        normalized = token.strip().lower()
        if not normalized or not self._is_suspicious(token):
            return []
        cached = self._suggestion_cache.get(normalized)
        if cached is not None:
            return cached[:limit]

        first_bucket = list(self._index.get(normalized[:1], []))
        candidates = [word for word in first_bucket if abs(len(word) - len(normalized)) <= 3]
        if len(candidates) < 12:
            fallback = [word for word in self._lexicon if abs(len(word) - len(normalized)) <= 2]
            candidates.extend(fallback)

        deduped = list(dict.fromkeys(candidates))
        matches = difflib.get_close_matches(normalized, deduped, n=max(limit * 3, 12), cutoff=0.72)
        ranked = sorted(
            matches,
            key=lambda word: max(zipf_frequency(word, "vi"), zipf_frequency(word, "en")),
            reverse=True,
        )
        self._suggestion_cache[normalized] = ranked[:limit]
        return self._suggestion_cache[normalized]

    def suspicious_words_in_text(self, text: str) -> list[str]:
        if not self._enabled or not text.strip():
            return []
        words: list[str] = []
        for match in _SPELL_TOKEN_RE.finditer(text):
            token = match.group(0)
            if self._is_suspicious(token):
                words.append(token)
        return words


class SpellcheckTextEdit(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._spellcheck_highlighter: SpellcheckHighlighter | None = None

    def set_spellcheck_highlighter(self, highlighter: SpellcheckHighlighter):
        self._spellcheck_highlighter = highlighter

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        cursor = self.cursorForPosition(event.pos())
        cursor.select(cursor.WordUnderCursor)
        selected = cursor.selectedText().strip()

        if self._spellcheck_highlighter and selected:
            suggestions = self._spellcheck_highlighter.suggestions_for(selected)
            if suggestions:
                menu.addSeparator()
                title_action = menu.addAction("Goi y sua")
                title_action.setEnabled(False)
                for suggestion in suggestions:
                    action = menu.addAction(f'Thay tat ca "{selected}" -> "{suggestion}"')
                    action.triggered.connect(
                        lambda _=False, old_word=selected, new_word=suggestion: self.replace_all_occurrences(
                            old_word,
                            new_word,
                        )
                    )

        menu.exec(event.globalPos())

    def replace_all_occurrences(self, source_word: str, target_word: str):
        if not source_word or not target_word or source_word == target_word:
            return
        text = self.toPlainText()
        pattern = re.compile(
            fr"(?<![A-Za-zÀ-ỹà-ỹĐđ]){re.escape(source_word)}(?![A-Za-zÀ-ỹà-ỹĐđ])",
            flags=re.IGNORECASE,
        )
        replaced = pattern.sub(
            lambda match: _match_case_style(match.group(0), target_word),
            text,
        )
        if replaced != text:
            self.setPlainText(replaced)


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
        painter.setBrush(QColor(15, 23, 42))
        painter.drawRoundedRect(track, 8, 8)

        # Waveform
        if self.waveform_data:
            num_bars = len(self.waveform_data)
            bar_width = track.width() / num_bars
            painter.setBrush(QColor(51, 65, 85))
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
            painter.setBrush(QColor(129, 140, 248))
            for i, val in enumerate(self.waveform_data):
                bar_x = int(track.left() + i * bar_width)
                if start_x <= bar_x <= end_x:
                    bar_h = val * track.height() * 0.8
                    bar_rect = QRect(bar_x, int(track.center().y() - bar_h / 2), int(max(1, bar_width - 1)), int(bar_h))
                    painter.drawRoundedRect(bar_rect, 2, 2)

        # Handles
        for x, label in ((start_x, self.start_value), (end_x, self.end_value)):
            painter.setBrush(QColor(248, 250, 252))
            painter.drawEllipse(QPoint(x, track.center().y()), 8, 8)
            painter.setPen(QColor(203, 213, 225))
            painter.drawText(x - 28, track.top() - 4, 56, 18, Qt.AlignCenter, f"{label:.1f}s")
            painter.setPen(Qt.NoPen)
            
        # Playhead (Red line)
        if self.playhead_value > 0 and self.playhead_value <= self.total_duration:
            ph_x = self._handle_x(self.playhead_value)
            painter.setPen(QPen(QColor(239, 68, 68), 2))
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

    def __init__(
        self,
        model: OmniVoice,
        mode: str,
        payload: dict,
        session_manager: SessionManager | None = None,
        voice_prompt_cache: OrderedDict | None = None,
    ):
        super().__init__()
        self.model = model
        self.mode = mode
        self.payload = payload
        self.session_manager = session_manager
        self.voice_prompt_cache = voice_prompt_cache
        self._is_cancelled = False
        self._cancel_event = threading.Event()

    def _active_elapsed_s(self, started_at: float) -> float:
        return float(self.payload.get("elapsed_offset_s") or 0.0) + (time.perf_counter() - started_at)

    def _persist_chunk_audio(self, chunk_index: int, chunk_audio) -> str | None:
        session_id = self.payload.get("session_id")
        if not session_id or not self.session_manager:
            return None
        chunk_path = self.session_manager.chunk_output_path(session_id, chunk_index)
        temp_path = chunk_path.with_suffix(chunk_path.suffix + ".tmp")
        sf.write(str(temp_path), chunk_audio, self.model.sampling_rate, format="WAV")
        os.replace(temp_path, chunk_path)
        return str(chunk_path)

    def _get_cached_voice_prompt(self):
        cache_key = self.payload.get("clone_prompt_cache_key")
        if not cache_key or self.voice_prompt_cache is None:
            return None
        prompt = self.voice_prompt_cache.get(cache_key)
        if prompt is not None:
            self.voice_prompt_cache.move_to_end(cache_key)
        return prompt

    def _set_cached_voice_prompt(self, prompt) -> None:
        cache_key = self.payload.get("clone_prompt_cache_key")
        if not cache_key or self.voice_prompt_cache is None:
            return
        self.voice_prompt_cache[cache_key] = prompt
        self.voice_prompt_cache.move_to_end(cache_key)
        while len(self.voice_prompt_cache) > _VOICE_PROMPT_CACHE_MAX:
            self.voice_prompt_cache.popitem(last=False)

    def _get_or_create_voice_prompt(self):
        prompt = self._get_cached_voice_prompt()
        if prompt is not None:
            return prompt
        prompt = self.model.create_voice_clone_prompt(
            ref_audio=self.payload["ref_audio"],
            ref_text=self.payload["ref_text"],
        )
        self._set_cached_voice_prompt(prompt)
        return prompt

    def _is_cuda_run(self) -> bool:
        device = str(getattr(self.model, "device", "") or "").lower()
        return "cuda" in device and torch.cuda.is_available()

    def _soft_throttle_cuda(self, chunk_elapsed_s: float) -> None:
        if not self._is_cuda_run():
            return
        base_cooldown_s = 0.02
        extra_cooldown_s = 0.04 if chunk_elapsed_s >= 10.0 else 0.0
        if chunk_elapsed_s >= 10.0:
            try:
                torch.cuda.synchronize()
            except Exception:
                pass
        time.sleep(base_cooldown_s + extra_cooldown_s)

    def cancel(self):
        self._is_cancelled = True
        self._cancel_event.set()
        if hasattr(self.model, "cancel_generation"):
            self.model.cancel_generation()

    def _raise_if_cancelled(self):
        if self._is_cancelled:
            raise RuntimeError("Đã hủy tác vụ")

    def _split_text_chunks(self, text: str) -> list[str]:
        # ChÃ¡ÂºÂ¿ Ã„â€˜Ã¡Â»â„¢ Ã†Â°u tiÃƒÂªn Ã„â€˜ÃƒÂºng chÃ¡Â»Â¯: mÃ¡Â»â€”i vÃ¡ÂºÂ¿ ngÃ„Æ’n bÃ¡Â»Å¸i dÃ¡ÂºÂ¥u cÃƒÂ¢u lÃƒÂ  mÃ¡Â»â„¢t Ã„â€˜Ã†Â¡n vÃ¡Â»â€¹ Ã„â€˜Ã¡Â»Âc
        # gÃ¡ÂºÂ§n nhÃ†Â° Ã„â€˜Ã¡Â»â„¢c lÃ¡ÂºÂ­p. CÃƒÂ¡ch nÃƒÂ y chÃ¡ÂºÂ­m hÃ†Â¡n mÃ¡Â»â„¢t chÃƒÂºt nhÃ†Â°ng giÃ¡ÂºÂ£m mÃ¡ÂºÂ¡nh viÃ¡Â»â€¡c model
        # nuÃ¡Â»â€˜t cÃ¡ÂºÂ£ cÃ¡Â»Â¥m Ã¡Â»Å¸ giÃ¡Â»Â¯a khi gÃ¡ÂºÂ·p kÃ¡Â»â€¹ch bÃ¡ÂºÂ£n comma-heavy.
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

            # GÃ¡Â»â„¢p cÃƒÂ¡c mÃ¡ÂºÂ©u quÃƒÂ¡ ngÃ¡ÂºÂ¯n kiÃ¡Â»Æ’u "Yeah," vÃ¡Â»â€ºi vÃ¡ÂºÂ¿ sÃƒÂ¡t sau Ã„â€˜Ã¡Â»Æ’ trÃƒÂ¡nh Ã„â€˜Ã¡Â»Âc cÃ¡Â»Â¥t.
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

        # Háº­u xá»­ lÃ½ tá»‘i thiá»ƒu: chá»‰ dá»“n chunk quÃ¡ ngáº¯n hoáº·c chunk káº¿t thÃºc báº±ng tá»«
        # nhÃ¡ÂºÂ¡y phÃƒÂ¡t ÃƒÂ¢m sang chunk kÃ¡ÂºÂ¿ tiÃ¡ÂºÂ¿p. KhÃƒÂ´ng gÃ¡Â»â„¢p trÃƒÂ n lan Ã„â€˜Ã¡Â»Æ’ trÃƒÂ¡nh model bÃ¡Â»Â
        # mÃ¡ÂºÂ¥t cÃ¡ÂºÂ£ cÃ¡Â»Â¥m Ã¡Â»Å¸ giÃ¡Â»Â¯a mÃ¡Â»â„¢t chunk dÃƒÂ i.
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

        # Khi mÃ¡Â»â„¢t chunk kÃ¡ÂºÂ¿t thÃƒÂºc bÃ¡ÂºÂ±ng dÃ¡ÂºÂ¥u phÃ¡ÂºÂ©y, model thÃ†Â°Ã¡Â»Âng nhÃ¡ÂºÂ£ chÃ¡Â»Â¯ cuÃ¡Â»â€˜i yÃ¡ÂºÂ¿u
        # hoÃ¡ÂºÂ·c cÃ¡Â»Â¥t hÃ†Â¡i. Ã„ÂÃ¡Â»â€¢i riÃƒÂªng dÃ¡ÂºÂ¥u kÃ¡ÂºÂ¿t thÃƒÂºc chunk sang dÃ¡ÂºÂ¥u chÃ¡ÂºÂ¥m Ã„â€˜Ã¡Â»Æ’ nÃƒÂ³ khÃƒÂ©p
        # cÃƒÂ¢u chÃ¡ÂºÂ¯c hÃ†Â¡n, nhÃ†Â°ng vÃ¡ÂºÂ«n giÃ¡Â»Â¯ nguyÃƒÂªn toÃƒÂ n bÃ¡Â»â„¢ tÃ¡Â»Â« ngÃ¡Â»Â¯.
        if text.endswith((",", ";", ":")):
            return text[:-1].rstrip() + "."
        if text[-1] not in ".!?":
            return text + "."
        return text

    def run(self):
        started_at = time.perf_counter()
        try:
            session_id = self.payload.get("session_id")
            if session_id and self.session_manager:
                self.session_manager.mark_running(session_id, float(self.payload.get("elapsed_offset_s") or 0.0))
            self._raise_if_cancelled()
            if hasattr(self.model, "clear_generation_cancel"):
                self.model.clear_generation_cancel()
            self.progress.emit("Đang kiểm tra dữ liệu đầu vào...", 5)
            if self.mode == "clone":
                self._raise_if_cancelled()
                self.progress.emit("Đang tạo prompt clone từ file mẫu...", 20)
                prompt = self._get_or_create_voice_prompt()
                kwargs = {
                    "text": self.payload["text"],
                    "language": self.payload["language"],
                    "generation_config": self.payload["generation_config"],
                    "voice_clone_prompt": prompt,
                }
            else:
                self._raise_if_cancelled()
                self.progress.emit("Đang chuẩn bị cấu hình thiết kế giọng...", 20)
                kwargs = {
                    "text": self.payload["text"],
                    "language": self.payload["language"],
                    "generation_config": self.payload["generation_config"],
                }
                if self.payload["instruct"]:
                    kwargs["instruct"] = self.payload["instruct"]

            self.progress.emit("Đang áp dụng tham số suy luận...", 40)
            self._raise_if_cancelled()
            if self.payload.get("speed") and self.payload["speed"] != 1.0:
                kwargs["speed"] = self.payload["speed"]
            if self.payload.get("duration") and self.payload["duration"] > 0:
                kwargs["duration"] = self.payload["duration"]

            chunks = self._split_text_chunks(self.payload["text"])
            generated_parts = list(self.payload.get("preloaded_parts") or [])
            total_chunks = len(chunks)
            resume_from_index = int(self.payload.get("resume_from_chunk_index") or 0)
            for chunk_index, chunk_text in enumerate(chunks):
                if chunk_index < resume_from_index:
                    continue
                self._raise_if_cancelled()
                chunk_started_at = time.perf_counter()
                chunk_kwargs = dict(kwargs)
                prepared_chunk_text = self._prepare_chunk_text(chunk_text)
                chunk_kwargs["text"] = prepared_chunk_text
                print(f"[TEXT_CHUNK] {chunk_index + 1}/{total_chunks}: {prepared_chunk_text}")
                progress_value = 45 + int(chunk_index / max(total_chunks, 1) * 45)
                self.progress.emit(
                    f"Đang chạy chunk {chunk_index + 1}/{total_chunks} ({len(chunk_text)} ký tự)...",
                    progress_value,
                )
                chunk_audio = self.model.generate(cancel_event=self._cancel_event, **chunk_kwargs)[0]
                self._raise_if_cancelled()
                chunk_file = self._persist_chunk_audio(chunk_index, chunk_audio)
                if chunk_file and session_id and self.session_manager:
                    self.session_manager.mark_chunk_complete(
                        session_id,
                        chunk_index,
                        chunk_file,
                        self._active_elapsed_s(started_at),
                    )
                generated_parts.append(chunk_audio)
                self._soft_throttle_cuda(time.perf_counter() - chunk_started_at)

            if len(generated_parts) == 1:
                final_audio = generated_parts[0]
            else:
                pause = np.zeros(int(self.model.sampling_rate * 0.05), dtype=generated_parts[0].dtype)
                with_pauses = []
                for part in generated_parts:
                    with_pauses.extend([part, pause])
                final_audio = np.concatenate(with_pauses[:-1], axis=-1)
                
            # --- DÃ¡Â»Ân dÃ¡ÂºÂ¹p GPU ngay sau khi tÃ¡ÂºÂ¡o xong ---
            try:
                import torch
                torch.cuda.empty_cache()
            except Exception:
                pass
                
            elapsed_s = self._active_elapsed_s(started_at)
            meta = {
                "session_id": session_id,
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
            self._raise_if_cancelled()
            if session_id and self.session_manager:
                final_audio_path = self.session_manager.final_output_path(session_id)
            else:
                temp_file = _named_temp_wav()
                temp_file.close()
                final_audio_path = Path(temp_file.name)
            temp_final = final_audio_path.with_suffix(final_audio_path.suffix + ".tmp")
            sf.write(str(temp_final), final_audio, self.model.sampling_rate, format="WAV")
            os.replace(temp_final, final_audio_path)
            meta["final_audio_file"] = str(final_audio_path)
            if session_id and self.session_manager:
                self.session_manager.mark_finished(
                    session_id,
                    "completed",
                    elapsed_s,
                    final_audio=str(final_audio_path),
                )
            del final_audio
            self.success.emit(None, meta)
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
        self.current_output_path = None
        self.current_output_session_id = None
        self.result_player = QMediaPlayer(self)
        self.result_audio = QAudioOutput(self)
        self.result_player.setAudioOutput(self.result_audio)
        self.result_player.playbackStateChanged.connect(self._on_result_playback_state_changed)
        
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
        self.active_mode = None
        self._worker_token_seed = 0
        self._active_worker_token = None
        self._finished_workers = []
        self.is_playing = False
        self.session_manager = SessionManager()
        self._voice_prompt_cache = OrderedDict()
        self._reference_audio_cache = OrderedDict()
        self.generation_timer = QTimer(self)
        self.generation_timer.setInterval(1000)
        self.generation_timer.timeout.connect(self._refresh_elapsed_labels)
        self._text_tools_stats_timer = QTimer(self)
        self._text_tools_stats_timer.setSingleShot(True)
        self._text_tools_stats_timer.setInterval(250)
        self._text_tools_stats_timer.timeout.connect(self._refresh_text_tools_stats)
        self._runtime_state = {
            "clone": {"started_at": None, "payload": None, "elapsed_offset_s": 0.0, "session_id": None},
            "design": {"started_at": None, "payload": None, "elapsed_offset_s": 0.0, "session_id": None},
        }

        self.setWindowTitle("OMNIVOICE STUDIO")
        self.resize(1520, 930)
        self.setMinimumSize(400, 400)
        self._apply_style()
        self._build_ui()
        self._refresh_runtime_badge()

    def _apply_style(self):
        qss_path = os.path.join(os.path.dirname(__file__), 'style.qss')
        try:
            with open(qss_path, 'r', encoding='utf-8') as f:
                self.setStyleSheet(f.read())
        except Exception as e:
            print(f"Warning: Could not load style.qss from {qss_path}: {e}")
            # Fallback minimal style so it remains usable
            self.setStyleSheet("QWidget { background: #05070b; color: #f4f7fb; }")

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
            self._voice_prompt_cache.clear()
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
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        
        badge_row = QHBoxLayout()
        badge_row.setAlignment(Qt.AlignCenter)
        badge_row.addWidget(self.runtime_badge)
        
        self.device_combo = QComboBox()
        self.device_combo.addItems(["Tự động", "CPU", "CUDA"])
        self.device_combo.setObjectName("DeviceCombo")
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
        self.tabs.setObjectName("MainTabs")

        clone_scroll = QScrollArea()
        clone_scroll.setWidgetResizable(True)
        clone_scroll.setFrameShape(QFrame.NoFrame)
        clone_scroll.setWidget(self._build_clone_page())
        self.tabs.addTab(clone_scroll, "Clone Giọng Nói (Sao chép)")

        design_scroll = QScrollArea()
        design_scroll.setWidgetResizable(True)
        design_scroll.setFrameShape(QFrame.NoFrame)
        design_scroll.setWidget(self._build_design_page())
        self.tabs.addTab(design_scroll, "Thiết Kế Giọng (Tạo giọng mới)")

        text_tools_scroll = QScrollArea()
        text_tools_scroll.setWidgetResizable(True)
        text_tools_scroll.setFrameShape(QFrame.NoFrame)
        text_tools_scroll.setWidget(self._build_text_tools_page())
        self.tabs.addTab(text_tools_scroll, "Chu\u1ea9n B\u1ecb V\u0103n B\u1ea3n")

        recovery_scroll = QScrollArea()
        recovery_scroll.setWidgetResizable(True)
        recovery_scroll.setFrameShape(QFrame.NoFrame)
        recovery_scroll.setWidget(self._build_recovery_page())
        self.tabs.addTab(recovery_scroll, "Phục hồi phiên dang dở")

        main_layout.addWidget(self.tabs)
        self._refresh_elapsed_labels()
        self._refresh_recovery_list()

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

    def _panel_badge(self, text: str):
        badge = QLabel(text)
        badge.setObjectName("PanelBadge")
        return badge

    def _attach_spellcheck(self, editor: QPlainTextEdit):
        if not hasattr(self, "_spellcheckers"):
            self._spellcheckers = []
        highlighter = SpellcheckHighlighter(editor.document())
        if isinstance(editor, SpellcheckTextEdit):
            editor.set_spellcheck_highlighter(highlighter)
        self._spellcheckers.append(highlighter)
        return highlighter

    def _build_text_tools_page(self):
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setAlignment(Qt.AlignTop)

        left = self._card()
        left_l = QVBoxLayout(left)
        left_l.addWidget(self._build_runtime_strip("Text", "Nhap, upload, sap xep SRT va format truoc khi dua sang clone hoac design."))
        left_l.addWidget(self._panel_badge("B\u01b0\u1edbc 1 \u00b7 N\u1ea1p n\u1ed9i dung"), alignment=Qt.AlignLeft)
        left_l.addWidget(self._label("Ngu\u1ed3n v\u0103n b\u1ea3n", "SectionTitle"))

        upload_row = QHBoxLayout()
        self.text_tools_file = QLineEdit()
        self.text_tools_file.setReadOnly(True)
        self.text_tools_file.setObjectName("SoftField")
        self.text_tools_file.setPlaceholderText("Ch\u01b0a ch\u1ecdn file TXT ho\u1eb7c SRT...")
        upload_btn = QPushButton("Upload TXT/SRT")
        upload_btn.clicked.connect(self._upload_text_tool_file)
        upload_row.addWidget(self.text_tools_file, 1)
        upload_row.addWidget(upload_btn)
        left_l.addLayout(upload_row)

        self.text_tools_editor = SpellcheckTextEdit()
        self.text_tools_editor.setPlaceholderText("D\u00e1n n\u1ed9i dung ho\u1eb7c upload file v\u00e0o \u0111\u00e2y...")
        self.text_tools_editor.setMinimumHeight(380)
        self.text_tools_editor.textChanged.connect(self._schedule_text_tools_stats_refresh)
        self._attach_spellcheck(self.text_tools_editor)
        left_l.addWidget(self.text_tools_editor, 1)

        stats_row = QHBoxLayout()
        self.text_tools_stats = QLabel("")
        self.text_tools_stats.setObjectName("SubTitle")
        stats_row.addWidget(self.text_tools_stats)
        stats_row.addStretch(1)
        left_l.addLayout(stats_row)

        tool_row = QHBoxLayout()
        smart_btn = QPushButton("S\u1eafp x\u1ebfp th\u00f4ng minh")
        smart_btn.clicked.connect(self._smart_sort_text_tools)
        format_btn = QPushButton("Format text")
        format_btn.clicked.connect(self._format_text_tools)
        clear_btn = QPushButton("X\u00f3a h\u1ebft")
        clear_btn.clicked.connect(lambda: self.text_tools_editor.setPlainText(""))
        tool_row.addWidget(smart_btn)
        tool_row.addWidget(format_btn)
        tool_row.addWidget(clear_btn)
        tool_row.addStretch(1)
        left_l.addLayout(tool_row)

        right = self._card()
        right_l = QVBoxLayout(right)
        right_l.addWidget(self._build_runtime_strip("Flow", "Sau khi xu ly xong, bam 1 nut de day text sang Clone hoac Design."))
        right_l.addWidget(self._panel_badge("B\u01b0\u1edbc 2 \u00b7 \u0110\u1ea9y sang workflow"), alignment=Qt.AlignLeft)
        right_l.addWidget(self._label("S\u1eed d\u1ee5ng nhanh", "SectionTitle"))

        help_text = QPlainTextEdit()
        help_text.setReadOnly(True)
        help_text.setObjectName("SummaryBox")
        help_text.setPlainText(
            "\n".join(
                [
                    "Upload File:",
                    "- N\u1ea1p nhanh file .txt ho\u1eb7c .srt.",
                    "",
                    "S\u1eafp x\u1ebfp th\u00f4ng minh:",
                    "- Parse SRT thanh noi dung sach.",
                    "- Gom lai va tach theo cau de de lam TTS hon.",
                    "",
                    "Format text:",
                    "- Xoa xuong dong rac.",
                    "- Rut gon khoang trang du thua.",
                    "",
                    "\u0110\u1ea9y sang Clone / Design:",
                    "- Copy thang noi dung da xu ly sang tab tuong ung.",
                ]
            )
        )
        right_l.addWidget(help_text)

        right_l.addWidget(self._label("Từ nghi sai trong đoạn", "SectionTitle"))
        self.text_tools_spelling_list = QListWidget()
        self.text_tools_spelling_list.setObjectName("SpellingList")
        self.text_tools_spelling_list.setMinimumHeight(170)
        self.text_tools_spelling_list.currentItemChanged.connect(self._on_text_tools_spelling_selected)
        right_l.addWidget(self.text_tools_spelling_list)

        suggestion_row = QHBoxLayout()
        suggestion_row.setSpacing(8)
        self.text_tools_replace_buttons = []
        for idx in range(3):
            btn = QPushButton(f"Gợi ý {idx + 1}")
            btn.setEnabled(False)
            btn.clicked.connect(lambda _=False, suggestion_index=idx: self._apply_text_tools_suggestion(suggestion_index))
            self.text_tools_replace_buttons.append(btn)
            suggestion_row.addWidget(btn)
        right_l.addLayout(suggestion_row)

        action_clone = QPushButton("D\u00f9ng cho Clone gi\u1ecdng")
        action_clone.setProperty("variant", "primary")
        action_clone.clicked.connect(lambda: self._push_text_tools_to_target("clone"))
        action_design = QPushButton("D\u00f9ng cho Thi\u1ebft k\u1ebf gi\u1ecdng")
        action_design.clicked.connect(lambda: self._push_text_tools_to_target("design"))
        preview_btn = QPushButton("Xem sau format")
        preview_btn.clicked.connect(self._preview_text_tools_result)
        right_l.addWidget(action_clone)
        right_l.addWidget(action_design)
        right_l.addWidget(preview_btn)
        right_l.addStretch(1)

        layout.addWidget(left, 7)
        layout.addWidget(right, 4)
        QTimer.singleShot(0, self._refresh_text_tools_stats)
        return page

    def _schedule_text_tools_stats_refresh(self):
        if hasattr(self, "_text_tools_stats_timer"):
            self._text_tools_stats_timer.start()

    def _refresh_text_tools_stats(self):
        if not hasattr(self, "text_tools_editor") or not hasattr(self, "text_tools_stats"):
            return
        if hasattr(self, "_text_tools_stats_timer") and self._text_tools_stats_timer.isActive():
            self._text_tools_stats_timer.stop()
        text = self.text_tools_editor.toPlainText()
        words = len([word for word in re.split(r"\s+", text.strip()) if word])
        chars = len(text)
        lines = len([line for line in text.splitlines() if line.strip()]) if text.strip() else 0
        self.text_tools_stats.setText(f"{words} t\u1eeb | {chars} k\u00fd t\u1ef1 | {lines} d\u00f2ng")
        self._refresh_text_tools_spelling_list()

    def _refresh_text_tools_spelling_list(self):
        if not hasattr(self, "text_tools_editor") or not hasattr(self, "text_tools_spelling_list"):
            return
        editor = self.text_tools_editor
        highlighter = getattr(editor, "_spellcheck_highlighter", None)
        self._text_tools_spelling_entries = []
        if highlighter is None:
            self.text_tools_spelling_list.clear()
            self.text_tools_spelling_list.addItem("Chưa có bộ kiểm lỗi.")
            self._update_text_tools_suggestion_buttons([])
            return

        text = editor.toPlainText()
        suspicious_words = highlighter.suspicious_words_in_text(text)
        if not suspicious_words:
            self.text_tools_spelling_list.clear()
            self.text_tools_spelling_list.addItem("Không thấy từ nghi sai.")
            self._update_text_tools_suggestion_buttons([])
            return

        counts = Counter(word.lower() for word in suspicious_words)
        casing_map: dict[str, str] = {}
        for word in suspicious_words:
            casing_map.setdefault(word.lower(), word)

        self.text_tools_spelling_list.clear()
        for normalized, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
            display = casing_map.get(normalized, normalized)
            suggestions = highlighter.suggestions_for(display, limit=3)
            suggestion_text = f" -> {', '.join(suggestions)}" if suggestions else ""
            times_label = "lần" if count > 1 else "lần"
            item = QListWidgetItem(f"{display} ({count} {times_label}){suggestion_text}")
            item.setData(Qt.UserRole, {"word": display, "suggestions": suggestions})
            self.text_tools_spelling_list.addItem(item)
            self._text_tools_spelling_entries.append({"word": display, "suggestions": suggestions})

        self._update_text_tools_suggestion_buttons([])

    def _on_text_tools_spelling_selected(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None):
        if current is None:
            self._update_text_tools_suggestion_buttons([])
            return
        payload = current.data(Qt.UserRole) or {}
        suggestions = payload.get("suggestions") or []
        self._update_text_tools_suggestion_buttons(suggestions)

    def _update_text_tools_suggestion_buttons(self, suggestions: list[str]):
        if not hasattr(self, "text_tools_replace_buttons"):
            return
        self._text_tools_active_suggestions = suggestions
        for idx, btn in enumerate(self.text_tools_replace_buttons):
            if idx < len(suggestions):
                btn.setEnabled(True)
                btn.setText(f"Sửa toàn bộ: {suggestions[idx]}")
            else:
                btn.setEnabled(False)
                btn.setText(f"Gợi ý {idx + 1}")

    def _apply_text_tools_suggestion(self, suggestion_index: int):
        if not hasattr(self, "text_tools_spelling_list"):
            return
        current = self.text_tools_spelling_list.currentItem()
        if current is None:
            return
        payload = current.data(Qt.UserRole) or {}
        source_word = payload.get("word")
        suggestions = payload.get("suggestions") or []
        if not source_word or suggestion_index >= len(suggestions):
            return
        self.text_tools_editor.replace_all_occurrences(source_word, suggestions[suggestion_index])

    def _upload_text_tool_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Ch\u1ecdn file v\u0103n b\u1ea3n", "", "Text (*.txt *.srt);;All Files (*.*)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(path, "r", encoding="utf-8-sig") as f:
                content = f.read()
        except Exception as exc:
            QMessageBox.critical(self, "L\u1ed7i \u0111\u1ecdc file", str(exc))
            return

        if path.lower().endswith(".srt"):
            content = parse_srt_blocks(content)

        self.text_tools_file.setText(path)
        self.text_tools_editor.setPlainText(content)
        self._refresh_text_tools_stats()

    def _smart_sort_text_tools(self):
        text = self.text_tools_editor.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "Ch\u01b0a c\u00f3 n\u1ed9i dung", "H\u00e3y nh\u1eadp ho\u1eb7c upload v\u0103n b\u1ea3n tr\u01b0\u1edbc.")
            return
        self.text_tools_editor.setPlainText(smart_sort_text_content(text))
        self._refresh_text_tools_stats()

    def _format_text_tools(self):
        text = self.text_tools_editor.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "Ch\u01b0a c\u00f3 n\u1ed9i dung", "H\u00e3y nh\u1eadp ho\u1eb7c upload v\u0103n b\u1ea3n tr\u01b0\u1edbc.")
            return
        self.text_tools_editor.setPlainText(format_text_content(text))
        self._refresh_text_tools_stats()

    def _preview_text_tools_result(self):
        text = self.text_tools_editor.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "Ch\u01b0a c\u00f3 n\u1ed9i dung", "H\u00e3y nh\u1eadp ho\u1eb7c upload v\u0103n b\u1ea3n tr\u01b0\u1edbc.")
            return
        formatted = format_text_content(text)
        QMessageBox.information(self, "Preview format", f"Text g\u1ed1c:\n{text}\n\n--- Sau format ---\n{formatted}")

    def _push_text_tools_to_target(self, target: str):
        text = self.text_tools_editor.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "Ch\u01b0a c\u00f3 n\u1ed9i dung", "Kh\u00f4ng c\u00f3 v\u0103n b\u1ea3n \u0111\u1ec3 chuy\u1ec3n.")
            return
        if target == "clone":
            self.clone_text.setPlainText(text)
            self.tabs.setCurrentIndex(0)
            self.clone_text.setFocus()
        else:
            self.design_text.setPlainText(text)
            self.tabs.setCurrentIndex(1)
            self.design_text.setFocus()

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
                r"[Ã¡Ã áº£Ã£áº¡Äƒáº¯áº±áº³áºµáº·Ã¢áº¥áº§áº©áº«áº­Ã©Ã¨áº»áº½áº¹Ãªáº¿á»á»ƒá»…á»‡Ã­Ã¬á»‰Ä©á»‹Ã³Ã²á»Ãµá»Ã´á»‘á»“á»•á»—á»™Æ¡á»›á»á»Ÿá»¡á»£ÃºÃ¹á»§Å©á»¥Æ°á»©á»«á»­á»¯á»±Ã½á»³á»·á»¹á»µÄ‘Ä]",
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
        for label, tag, preview_tag in [
            ("Cười", "hahaha", "[laughter]"),
            ("Thở dài", "[sigh]", "[sigh]"),
            ("Xác nhận", "[confirmation-en]", "[confirmation-en]"),
            ("Bực nhẹ", "[dissatisfaction-hnn]", "[dissatisfaction-hnn]"),
        ]:
            btn = QPushButton(label)
            btn.setMinimumHeight(32)
            btn.clicked.connect(lambda _=False, e=editor, t=tag: self._insert_nonverbal_tag(e, t))
            btn.setToolTip(self._build_normalized_preview(preview_tag, "Vietnamese"))
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
        for label, tag, preview_tag in [
            ("Hỏi EN", "[question-en]", "[question-en]"),
            ("Hỏi ah", "[question-ah]", "[question-ah]"),
            ("Hỏi oh", "[question-oh]", "[question-oh]"),
            ("Ngạc nhiên ah", "[surprise-ah]", "[surprise-ah]"),
            ("Ngạc nhiên oh", "[surprise-oh]", "[surprise-oh]"),
            ("Ngạc nhiên wa", "[surprise-wa]", "[surprise-wa]"),
        ]:
            btn = QPushButton(label)
            btn.setMinimumHeight(32)
            btn.clicked.connect(lambda _=False, e=editor, t=tag: self._insert_nonverbal_tag(e, t))
            btn.setToolTip(self._build_normalized_preview(preview_tag, "Vietnamese"))
            bottom_row.addWidget(btn)
        bottom_row.addStretch(1)

        wrapper.addLayout(top_row)
        wrapper.addLayout(bottom_row)
        return wrapper

    def _apply_generation_preset(self, prefix: str, preset_key: str):
        preset = _GENERATION_PRESETS.get(preset_key)
        if not preset:
            return
        getattr(self, f"{prefix}_num_step").setValue(preset["steps"])
        getattr(self, f"{prefix}_guidance").setValue(preset["guidance"])
        getattr(self, f"{prefix}_speed").setValue(preset["speed"])
        hint = getattr(self, f"{prefix}_preset_hint", None)
        if hint is not None:
            hint.setText(preset["summary"])

    def _build_quick_preset_row(self, prefix: str):
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(self._label("Preset nhanh", "SubTitle"))

        preset_combo = QComboBox()
        preset_combo.addItem("Nhanh", "fast")
        preset_combo.addItem("Can bang", "balanced")
        preset_combo.addItem("Chat luong", "quality")
        preset_combo.setCurrentIndex(1)
        preset_combo.currentIndexChanged.connect(
            lambda _=0, p=prefix, combo=preset_combo: self._apply_generation_preset(
                p,
                combo.currentData(),
            )
        )
        setattr(self, f"{prefix}_preset_combo", preset_combo)
        row.addWidget(preset_combo, 0)

        hint = QLabel("")
        hint.setWordWrap(True)
        hint.setObjectName("PresetHint")
        setattr(self, f"{prefix}_preset_hint", hint)
        row.addWidget(hint, 1)

        return row

    def _build_runtime_strip(self, mode_label: str, note: str):
        frame = QFrame()
        frame.setObjectName("InfoStrip")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(14)

        mode_chip = QLabel(mode_label)
        mode_chip.setObjectName("StripChip")
        layout.addWidget(mode_chip, 0, Qt.AlignTop)

        note_label = QLabel(note)
        note_label.setWordWrap(True)
        note_label.setObjectName("StripNote")
        layout.addWidget(note_label, 1)
        return frame

    def _build_settings_group(self, prefix: str):
        settings_card = self._card()
        settings_l = QVBoxLayout(settings_card)
        # settings_l.setContentsMargins(24, 24, 24, 24)
        # settings_l.setSpacing(14)
        settings_l.addLayout(self._build_quick_preset_row(prefix))
        settings_l.addWidget(self._label("Cài đặt nâng cao", "SectionTitle"))
        
        speed = QDoubleSpinBox()
        speed.setRange(0.5, 2.0)
        speed.setSingleStep(0.05)
        speed.setValue(1.15)
        
        duration = QDoubleSpinBox()
        duration.setRange(0.0, 9999.0)
        duration.setValue(0.0)
        duration.setSingleStep(0.5)

        num_step = QSpinBox()
        num_step.setRange(4, 64)
        num_step.setValue(16)

        guidance = QDoubleSpinBox()
        guidance.setRange(0.0, 8.0)
        guidance.setSingleStep(0.1)
        guidance.setValue(1.5)

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
        settings_l.addLayout(row3)
        QTimer.singleShot(0, lambda p=prefix: self._apply_generation_preset(p, "balanced"))
        return settings_card

    def _build_clone_page(self):
        page = QWidget()
        layout = QHBoxLayout(page)
        # layout.setContentsMargins(28, 28, 28, 28)
        # layout.setSpacing(20)
        layout.setAlignment(Qt.AlignTop)

        left_col = QVBoxLayout()
        left_col.setSpacing(16)

        c1 = self._card()
        c1_l = QVBoxLayout(c1)
        # c1_l.setContentsMargins(24, 24, 24, 24)
        # c1_l.setSpacing(12)
        c1_l.addWidget(self._build_runtime_strip("Clone", "Toi uu cho script YouTube dai. Preset Can bang se nhanh hon ban cu ro ret."))
        c1_l.addWidget(self._panel_badge("Bước 1 · Nhập nội dung"), alignment=Qt.AlignLeft)
        c1_l.addWidget(self._label("Nội dung cần đọc", "SectionTitle"))
        self.clone_text = SpellcheckTextEdit()
        self.clone_text.setPlaceholderText("Nhập văn bản bạn muốn chuyển thành giọng nói vào đây...\nVí dụ: Xin chào mọi người, hôm nay thời tiết rất đẹp!")
        self.clone_text.setMinimumHeight(150)
        self.clone_text.setMaximumHeight(220)
        self._attach_spellcheck(self.clone_text)
        c1_l.addWidget(self.clone_text)
        c1_l.addLayout(self._nonverbal_bar(self.clone_text, lambda: None if self.clone_lang.currentText() == "Tự động" else self.clone_lang.currentText()))
        left_col.addWidget(c1)

        c2 = self._card()
        c2_l = QVBoxLayout(c2)
        # c2_l.setContentsMargins(24, 24, 24, 24)
        # c2_l.setSpacing(12)
        c2_l.addWidget(self._panel_badge("Bước 2 · Chọn mẫu"), alignment=Qt.AlignLeft)
        c2_l.addWidget(self._label("Âm thanh gốc (Giọng mẫu)", "SectionTitle"))
        c2_l.addWidget(self._label("Tải lên 1 đoạn ghi âm giọng nói mà bạn muốn AI bắt chước (Nên dài từ 3 đến 10 giây và rõ lời).", "SubTitle", True))
        
        file_row = QHBoxLayout()
        self.clone_file = QLineEdit()
        self.clone_file.setReadOnly(True)
        self.clone_file.setObjectName("SoftField")
        self.clone_file.setPlaceholderText("Chưa chọn file audio/video nào...")
        browse_btn = QPushButton("Chọn File")
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
        c2_l.addWidget(self._label("Kéo cắt đoạn dùng để clone", "SectionTitle"))
        self.range_selector = TrimRangeSelector()
        self.range_selector.changed.connect(self._sync_trim_spinboxes)
        c2_l.addWidget(self.range_selector)

        trim_row = QHBoxLayout()
        self.preview_play_btn = QPushButton("Phát đoạn đã cắt")
        self.preview_play_btn.clicked.connect(self._toggle_media_preview)
        self.cut_real_btn = QPushButton("Cắt thật")
        self.cut_real_btn.clicked.connect(self._cut_reference_audio_real)
        
        self.trim_start = QDoubleSpinBox()
        self.trim_start.setRange(0.0, 99999.0)
        self.trim_start.setValue(0.0)
        self.trim_start.valueChanged.connect(self._sync_range_from_spin)
        self.trim_end = QDoubleSpinBox()
        self.trim_end.setRange(0.0, 99999.0)
        self.trim_end.setValue(8.0)
        self.trim_end.valueChanged.connect(self._sync_range_from_spin)
        
        trim_row.addWidget(self.preview_play_btn)
        trim_row.addWidget(self.cut_real_btn)
        trim_row.addStretch(1)
        trim_row.addWidget(QLabel("Từ (s):"))
        trim_row.addWidget(self.trim_start)
        trim_row.addWidget(QLabel("Đến (s):"))
        trim_row.addWidget(self.trim_end)
        c2_l.addLayout(trim_row)

        c2_l.addSpacing(10)
        c2_l.addWidget(self._label("Lời của đoạn ghi âm mẫu (Tùy chọn, để trống AI sẽ tự nghe):", "SubTitle"))
        self.clone_ref_text = SpellcheckTextEdit()
        self.clone_ref_text.setPlaceholderText("Nhập lời thoại của đoạn âm thanh trên (nếu máy yếu tắt ASR).")
        self.clone_ref_text.setMinimumHeight(74)
        self.clone_ref_text.setMaximumHeight(90)
        self._attach_spellcheck(self.clone_ref_text)
        c2_l.addWidget(self.clone_ref_text)
        left_col.addWidget(c2)

        c3 = self._card()
        c3_l = QVBoxLayout(c3)
        # c3_l.setContentsMargins(24, 24, 24, 24)
        # c3_l.setSpacing(10)
        c3_l.addWidget(self._build_runtime_strip("Language", "Auto van on, nhung khi biet ro ngon ngu thi chon thang de ket qua deu hon."))
        c3_l.addWidget(self._panel_badge("Bước 3 · Ngôn ngữ"), alignment=Qt.AlignLeft)
        c3_l.addWidget(self._label("Ngôn ngữ đích & Tùy chỉnh", "SectionTitle"))
        self.clone_lang = QComboBox()
        self.clone_lang.addItems(_ALL_LANGUAGES)
        c3_l.addWidget(self.clone_lang)
        left_col.addWidget(c3)

        clone_settings = self._build_settings_group("clone")
        left_col.addWidget(clone_settings)
        left_col.addStretch(1)

        right_col = QVBoxLayout()
        right_col.setSpacing(14)
        right_col.setAlignment(Qt.AlignTop)

        r1 = self._card()
        r1_l = QVBoxLayout(r1)
        # r1_l.setContentsMargins(24, 24, 24, 24)
        # r1_l.setSpacing(12)
        r1_l.addWidget(self._build_runtime_strip("Output", "Neu can test nhanh nhieu lan, dung Nhanh. Ban cuoi hay doi sang Chat luong."))
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
        r1_l.addWidget(self.clone_status)
        self.clone_elapsed_label = QLabel("Thời gian tạo: 00:00")
        r1_l.addWidget(self.clone_elapsed_label)

        self.clone_progress = QProgressBar()
        self.clone_progress.setRange(0, 100)
        self.clone_progress.setValue(0)
        r1_l.addWidget(self.clone_progress)

        self.clone_info = QPlainTextEdit()
        self.clone_info.setReadOnly(True)
        self.clone_info.setObjectName("SummaryBox")
        self.clone_info.setMinimumHeight(132)
        self.clone_info.setMaximumHeight(220)
        r1_l.addWidget(self.clone_info)
        
        self.clone_log_info = QPlainTextEdit()
        self.clone_log_info.setReadOnly(True)
        self.clone_log_info.setObjectName("LogBox")
        self.clone_log_info.setPlaceholderText("Log xử lý...")
        self.clone_log_info.setMinimumHeight(150)
        self.clone_log_info.setMaximumHeight(220)
        r1_l.addWidget(self.clone_log_info)

        action_row = QHBoxLayout()
        self.play_result_btn = QPushButton("Phát Audio")
        self.play_result_btn.setEnabled(False)
        self.play_result_btn.setMinimumHeight(40)
        self.play_result_btn.clicked.connect(self._toggle_generated_audio)
        self.save_result_btn = QPushButton("Tải xuống WAV")
        self.save_result_btn.setEnabled(False)
        self.save_result_btn.setMinimumHeight(40)
        self.save_result_btn.clicked.connect(self._save_output)
        action_row.addWidget(self.play_result_btn, 2)
        action_row.addWidget(self.save_result_btn, 1)
        r1_l.addLayout(action_row)

        right_col.addWidget(r1)
        right_col.addStretch(1)

        layout.addLayout(left_col, 7)
        layout.addLayout(right_col, 5)
        return page

    def _build_design_page(self):
        page = QWidget()
        layout = QHBoxLayout(page)
        # layout.setContentsMargins(28, 28, 28, 28)
        # layout.setSpacing(20)

        left = self._card()
        left_l = QVBoxLayout(left)
        # left_l.setContentsMargins(24, 24, 24, 24)
        # left_l.setSpacing(12)
        left_l.addWidget(self._build_runtime_strip("Design", "Dung khi can tao giong moi. Preset Can bang hien la diem roi hop ly nhat."))
        left_l.addWidget(self._panel_badge("Bước 1 · Nội dung & concept"), alignment=Qt.AlignLeft)
        left_l.addWidget(self._label("Nội dung cần đọc", "SectionTitle"))
        self.design_text = SpellcheckTextEdit()
        self.design_text.setPlainText("Xin chào, đây là giọng nhân vật ảo trên bản desktop mới.")
        self.design_text.setMinimumHeight(150)
        self.design_text.setMaximumHeight(220)
        self._attach_spellcheck(self.design_text)
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
        right_l.addWidget(self._build_runtime_strip("Preview", "Kiem tra toc do, do dai audio va so chunk ngay trong khung ket qua."))
        right_l.addWidget(self._panel_badge("Bước 3 · Xem kết quả"), alignment=Qt.AlignLeft)
        self.design_status = QLabel("Chưa tạo")
        self.design_status.setWordWrap(True)
        self.design_elapsed_label = QLabel("Thời gian tạo: 00:00")
        self.design_info = QPlainTextEdit()
        self.design_info.setReadOnly(True)
        self.design_info.setObjectName("SummaryBox")
        self.design_info.setMinimumHeight(132)
        self.design_info.setMaximumHeight(220)
        self.design_play_btn = QPushButton("Phát kết quả")
        self.design_play_btn.setEnabled(False)
        self.design_play_btn.clicked.connect(self._toggle_generated_audio)
        self.design_save_btn = QPushButton("Lưu WAV")
        self.design_save_btn.setEnabled(False)
        self.design_save_btn.clicked.connect(self._save_output)
        right_l.addWidget(self._label("Kết quả thiết kế giọng", "SectionTitle"))
        right_l.addWidget(self.design_status)
        right_l.addWidget(self.design_elapsed_label)

        self.design_progress = QProgressBar()
        self.design_progress.setRange(0, 100)
        self.design_progress.setValue(0)
        right_l.addWidget(self.design_progress)

        right_l.addWidget(self.design_info, 1)

        self.design_log_info = QPlainTextEdit()
        self.design_log_info.setReadOnly(True)
        self.design_log_info.setObjectName("LogBox")
        self.design_log_info.setPlaceholderText("Log xử lý...")
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

    def _build_recovery_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        header = QLabel("Phiên dang dở có thể tiếp tục")
        header.setObjectName("SectionTitle")
        layout.addWidget(header)
        note = QLabel("Chọn Resume để chạy tiếp từ chunk dang dở, hoặc Delete để xóa session local.")
        note.setWordWrap(True)
        layout.addWidget(note)
        refresh_btn = QPushButton("Làm mới danh sách")
        refresh_btn.clicked.connect(self._refresh_recovery_list)
        layout.addWidget(refresh_btn)
        container = QWidget()
        self.recovery_list_layout = QVBoxLayout(container)
        self.recovery_list_layout.setSpacing(12)
        layout.addWidget(container)
        layout.addStretch(1)
        return page

    def _build_settings_page(self):
        page = self._card()
        layout = QVBoxLayout(page)
        # layout.setContentsMargins(24, 24, 24, 24)
        layout.addWidget(self._label("Cài Đặt Nâng Cao", "SectionTitle"))

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
                extracted = _named_temp_wav()
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
            self.preview_play_btn.setText("Phát đoạn đã cắt")
        else:
            self.media_player.setPosition(int(self.trim_start.value() * 1000))
            self.media_player.play()
            self.preview_play_btn.setText("Dừng")

    def _on_player_position_changed(self, pos_ms: int):
        pos_sec = pos_ms / 1000.0
        self.range_selector.set_playhead(pos_sec)
        if pos_sec >= self.trim_end.value() and self.media_player.playbackState() == QMediaPlayer.PlayingState:
            self.media_player.pause()
            self.preview_play_btn.setText("Phát đoạn đã cắt")
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
        start_sec = self.trim_start.value()
        end_sec = self.trim_end.value()
        if end_sec <= start_sec:
            raise ValueError("Khoang cat khong hop le.")

        cache_key = self._build_reference_audio_cache_key(source, start_sec, end_sec)
        cached_ref = self._get_cached_reference_audio(cache_key)
        if cached_ref:
            self.current_processed_ref = cached_ref
            return cached_ref, start_sec, end_sec

        suffix = Path(source).suffix.lower()
        working_source = source
        if suffix in {".mp4", ".mov", ".mkv", ".avi"}:
            extracted = _named_temp_wav()
            extracted.close()
            self._extract_audio_from_video(source, extracted.name)
            working_source = extracted.name

        audio = AudioSegment.from_file(working_source)
        start_sec = self.trim_start.value()
        end_sec = self.trim_end.value()
        if end_sec <= start_sec:
            raise ValueError("Khoảng cắt không hợp lệ.")
        trimmed = audio[int(start_sec * 1000): int(end_sec * 1000)]
        temp_ref = _named_temp_wav()
        temp_ref.close()
        trimmed.export(temp_ref.name, format="wav")
        self.current_processed_ref = temp_ref.name
        self._set_cached_reference_audio(cache_key, temp_ref.name)
        return temp_ref.name, start_sec, end_sec

    def _build_reference_audio_cache_key(
        self,
        source: str,
        start_sec: float,
        end_sec: float,
    ) -> str | None:
        if not source:
            return None
        try:
            source_path = Path(source).resolve()
            stat = source_path.stat()
        except OSError:
            return None

        digest = hashlib.sha256()
        parts = [
            "reference-audio-v1",
            str(source_path),
            str(stat.st_mtime_ns),
            str(stat.st_size),
            str(int(round(start_sec * 1000))),
            str(int(round(end_sec * 1000))),
        ]
        for part in parts:
            digest.update(part.encode("utf-8", errors="surrogatepass"))
            digest.update(b"\0")
        return digest.hexdigest()

    def _get_cached_reference_audio(self, cache_key: str | None) -> str | None:
        if not cache_key:
            return None
        cached_path = self._reference_audio_cache.get(cache_key)
        if not cached_path:
            return None
        if not os.path.exists(cached_path):
            self._reference_audio_cache.pop(cache_key, None)
            return None
        self._reference_audio_cache.move_to_end(cache_key)
        return cached_path

    def _set_cached_reference_audio(self, cache_key: str | None, audio_path: str) -> None:
        if not cache_key or not audio_path:
            return
        self._reference_audio_cache[cache_key] = audio_path
        self._reference_audio_cache.move_to_end(cache_key)
        while len(self._reference_audio_cache) > _REFERENCE_AUDIO_CACHE_MAX:
            self._reference_audio_cache.popitem(last=False)

    def _build_clone_prompt_cache_key(
        self,
        source: str,
        start_sec: float,
        end_sec: float,
        transcript: str | None,
        preprocess_prompt: bool,
    ) -> str | None:
        if not source:
            return None
        try:
            source_path = Path(source).resolve()
            stat = source_path.stat()
        except OSError:
            return None

        digest = hashlib.sha256()
        parts = [
            "clone-prompt-v1",
            str(source_path),
            str(stat.st_mtime_ns),
            str(stat.st_size),
            str(int(round(start_sec * 1000))),
            str(int(round(end_sec * 1000))),
            transcript or "",
            str(bool(preprocess_prompt)),
            str(getattr(self.model, "sampling_rate", self.sampling_rate)),
        ]
        for part in parts:
            digest.update(part.encode("utf-8", errors="surrogatepass"))
            digest.update(b"\0")
        return digest.hexdigest()

    def _prepare_reference_preview(self):
        pass

    def _cut_reference_audio_real(self):
        try:
            self._prepare_reference_audio()
        except Exception as exc:
            QMessageBox.critical(self, "Lỗi cắt âm thanh", str(exc))
            return
        self._save_processed_ref()
        if self.current_processed_ref and os.path.exists(self.current_processed_ref):
            self.clone_status.setText("Đã cắt thật đoạn âm thanh theo vùng đã chọn.")

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
        generation_config = self._build_generation_config("clone")
        payload = {
            "text": self.clone_text.toPlainText().strip(),
            "language": None if self.clone_lang.currentText() == "Tự động" else self.clone_lang.currentText(),
            "generation_config": generation_config,
            "ref_audio": ref_path,
            "ref_text": transcript,
            "clone_prompt_cache_key": self._build_clone_prompt_cache_key(
                self.clone_file.text().strip(),
                start_sec,
                end_sec,
                transcript,
                generation_config.preprocess_prompt,
            ),
            "speed": float(self.clone_speed.value()),
            "duration": float(self.clone_duration.value()),
            "start": start_sec,
            "end": end_sec,
            "chunk_chars": self._suggest_chunk_chars(self.clone_text.toPlainText().strip()),
        }
        self._run_worker("clone", self._create_session_payload("clone", payload))

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
        self._run_worker("design", self._create_session_payload("design", payload))

    def _build_chunks_for_payload(self, payload: dict) -> list[str]:
        probe_worker = GenerationWorker(self.model, "clone", payload, self.session_manager)
        return probe_worker._split_text_chunks(payload["text"])

    def _create_session_payload(self, mode: str, payload: dict) -> dict:
        chunks = self._build_chunks_for_payload(payload)
        session_id, _manifest = self.session_manager.create_session(mode, payload, chunks)
        new_payload = payload.copy()
        new_payload["session_id"] = session_id
        new_payload["elapsed_offset_s"] = 0.0
        new_payload["resume_from_chunk_index"] = 0
        new_payload["preloaded_parts"] = []
        new_payload["completed_chunk_indexes"] = []
        if mode == "clone":
            saved = self.session_manager.load_session(session_id)
            ref_audio = saved.get("payload", {}).get("ref_audio")
            if ref_audio:
                new_payload["ref_audio"] = ref_audio
        return new_payload

    def _resume_session(self, session_id: str):
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "Đang bận", "Hãy đợi tác vụ hiện tại xong hoặc bấm hủy trước khi resume.")
            return
        manifest = self.session_manager.load_session(session_id)
        payload = dict(manifest.get("payload") or {})
        config_data = payload.get("generation_config") or {}
        payload["generation_config"] = OmniVoiceGenerationConfig(**config_data)
        preloaded_parts = []
        first_incomplete = 0
        for chunk in manifest.get("chunks") or []:
            audio_file = chunk.get("audio_file")
            if chunk.get("status") == "completed" and audio_file and os.path.exists(audio_file):
                audio, _sr = sf.read(audio_file)
                preloaded_parts.append(audio)
                first_incomplete = chunk.get("index", first_incomplete) + 1
                continue
            break
        payload["session_id"] = session_id
        payload["elapsed_offset_s"] = float(manifest.get("timing", {}).get("elapsed_active_s") or 0.0)
        payload["resume_from_chunk_index"] = first_incomplete
        payload["preloaded_parts"] = preloaded_parts
        payload["completed_chunk_indexes"] = list(range(first_incomplete))
        self._refresh_recovery_list()
        self._run_worker(manifest.get("mode") or "clone", payload)

    def _run_worker(self, mode: str, payload: dict):
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "Đang bận", "Hiện đang có một tác vụ tạo giọng chạy rồi. Hãy đợi xong hoặc bấm Hủy.")
            return
        self._worker_token_seed += 1
        worker_token = self._worker_token_seed
        self._active_worker_token = worker_token
        self._runtime_state[mode] = {
            "started_at": time.perf_counter(),
            "payload": payload.copy(),
            "elapsed_offset_s": float(payload.get("elapsed_offset_s") or 0.0),
            "session_id": payload.get("session_id"),
        }
        self.active_mode = mode
        if mode == "clone":
            self.clone_generate_btn.setText("ĐANG XỬ LÝ...")
            self.clone_status.setText("Trạng thái hệ thống: Đang chạy...")
            self.clone_progress.setValue(1)
            self.clone_log_info.clear()
            self.clone_info.setPlainText(self._build_runtime_summary(mode, payload))
            self.clone_cancel_btn.setEnabled(True)
            self.design_generate_btn.setEnabled(False)
            self._log_event(mode, "INFO", "Đã bắt đầu job clone giọng.")
        else:
            self.design_generate_btn.setText("ĐANG XỬ LÝ...")
            self.design_status.setText("Trạng thái hệ thống: Đang chạy...")
            self.design_progress.setValue(1)
            self.design_log_info.clear()
            self.design_info.setPlainText(self._build_runtime_summary(mode, payload))
            self.design_cancel_btn.setEnabled(True)
            self.clone_generate_btn.setEnabled(False)
            self._log_event(mode, "INFO", "Đã bắt đầu job thiết kế giọng.")
            
        self.generation_timer.start()
        self.worker = GenerationWorker(
            self.model,
            mode,
            payload,
            self.session_manager,
            self._voice_prompt_cache,
        )
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

    def _format_elapsed(self, seconds: float) -> str:
        total = max(0, int(seconds))
        hours, remainder = divmod(total, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    def _elapsed_for_mode(self, mode: str) -> float:
        state = self._runtime_state.get(mode, {})
        started_at = state.get("started_at")
        offset = float(state.get("elapsed_offset_s") or 0.0)
        if not started_at:
            return offset
        return offset + (time.perf_counter() - started_at)

    def _refresh_elapsed_labels(self):
        for mode, label_attr in (("clone", "clone_elapsed_label"), ("design", "design_elapsed_label")):
            label = getattr(self, label_attr, None)
            if label is None:
                continue
            label.setText(f"Thời gian tạo: {self._format_elapsed(self._elapsed_for_mode(mode))}")

    def _refresh_recovery_list(self):
        if not hasattr(self, "recovery_list_layout"):
            return
        while self.recovery_list_layout.count():
            item = self.recovery_list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        sessions = self.session_manager.list_recoverable_sessions()
        if not sessions:
            empty = QLabel("Không có phiên dang dở nào.")
            empty.setWordWrap(True)
            self.recovery_list_layout.addWidget(empty)
            return
        for session in sessions:
            card = self._card()
            card_layout = QVBoxLayout(card)
            card_layout.addWidget(QLabel(f"{session['mode']} | {session['completed_chunks']}/{session['total_chunks']} chunk | {self._format_elapsed(session['elapsed_active_s'])}"))
            preview = QLabel(session["text_preview"] or "(không có preview)")
            preview.setWordWrap(True)
            card_layout.addWidget(preview)
            actions = QHBoxLayout()
            resume_btn = QPushButton("Resume")
            resume_btn.clicked.connect(lambda _=False, sid=session["session_id"]: self._resume_session(sid))
            delete_btn = QPushButton("Delete")
            delete_btn.clicked.connect(lambda _=False, sid=session["session_id"]: self._delete_session(sid))
            actions.addWidget(resume_btn)
            actions.addWidget(delete_btn)
            actions.addStretch(1)
            card_layout.addLayout(actions)
            self.recovery_list_layout.addWidget(card)
        self.recovery_list_layout.addStretch(1)

    def _delete_session(self, session_id: str):
        self.session_manager.delete_session(session_id)
        self._refresh_recovery_list()

    def _cleanup_current_output_artifact(self):
        self.result_player.stop()
        self.is_playing = False
        self.play_result_btn.setText("Phát kết quả")
        self.design_play_btn.setText("Phát kết quả")
        output_path = self.current_output_path
        session_id = self.current_output_session_id
        self.current_output_path = None
        self.current_output_session_id = None
        self.audio_output = None
        if session_id:
            self.session_manager.delete_session(session_id)
            self._refresh_recovery_list()
        elif output_path and os.path.exists(output_path):
            try:
                os.remove(output_path)
            except Exception:
                pass

    def _reset_generation_ui(self, mode: str):
        self.active_mode = None
        self.generation_timer.stop()
        self._refresh_elapsed_labels()
        self.clone_generate_btn.setEnabled(True)
        self.clone_generate_btn.setText("BẮT ĐẦU TẠO GIỌNG")
        self.clone_cancel_btn.setEnabled(False)
        self.design_generate_btn.setEnabled(True)
        self.design_generate_btn.setText("BẮT ĐẦU TẠO GIỌNG")
        self.design_cancel_btn.setEnabled(False)

    def _update_progress(self, mode: str, text: str, value: int, worker_token: int | None = None):
        if worker_token is not None and worker_token != self._active_worker_token:
            return
        self._refresh_elapsed_labels()
        if mode == "clone":
            self.clone_status.setText("Trạng thái hệ thống: " + text)
            self.clone_progress.setValue(value)
        else:
            self.design_status.setText("Trạng thái hệ thống: " + text)
            self.design_progress.setValue(value)
        self._log_event(mode, "STEP", f"[{value}%] {text}")

    def _on_worker_success(self, mode: str, audio, meta: dict, worker_token: int | None = None):
        if worker_token is not None and worker_token != self._active_worker_token:
            return
        self._active_worker_token = None
        self._reset_generation_ui(mode)
        if self.current_output_path or self.current_output_session_id:
            self._cleanup_current_output_artifact()
        self.current_output_path = meta.get("final_audio_file")
        self.current_output_session_id = meta.get("session_id")
        self.audio_output = None
        elapsed_s = meta.get("elapsed_s") or self._elapsed_for_mode(mode)
        self._runtime_state[mode]["elapsed_offset_s"] = float(elapsed_s)
        self._refresh_recovery_list()
        if mode == "clone":
            self.clone_status.setText("Trạng thái hệ thống: Hoàn thành xuất sắc!")
            self.clone_progress.setValue(100)
            self.play_result_btn.setEnabled(True)
            self.save_result_btn.setEnabled(True)
            self.clone_info.setPlainText(
                "\n".join([
                    "Đã clone giọng xong.",
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
            self.design_info.setPlainText(
                "\n".join([
                    "Thiết kế giọng thành công.",
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
        self._play_completion_alert()
        self._log_event(mode, "DONE", f"Hoàn tất sau {elapsed_s:.2f}s. Audio đầu ra {meta.get('output_seconds', 0.0):.2f}s.")

    def _on_worker_error(self, mode: str, message: str, detail: str, worker_token: int | None = None):
        if worker_token is not None and worker_token != self._active_worker_token:
            return
        elapsed_s = self._elapsed_for_mode(mode)
        self._active_worker_token = None
        session_id = self._runtime_state.get(mode, {}).get("session_id")
        if session_id:
            status = "cancelled" if message == "Đã hủy tác vụ" else "failed"
            self.session_manager.mark_finished(session_id, status, elapsed_s, error=message)
        self._reset_generation_ui(mode)
        self._refresh_recovery_list()
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
        self._refresh_recovery_list()

    def _build_runtime_summary(self, mode: str, payload: dict) -> str:
        config = payload["generation_config"]
        preset_name = "Tuy chinh"
        for preset in _GENERATION_PRESETS.values():
            if (
                int(config.num_step) == int(preset["steps"])
                and abs(float(config.guidance_scale) - float(preset["guidance"])) < 1e-9
                and abs(float(payload.get("speed", 1.0)) - float(preset["speed"])) < 1e-9
            ):
                preset_name = preset["label"]
                break
        lines = [
            f"Mode: {'Clone giọng' if mode == 'clone' else 'Thiết kế giọng'}",
            f"Thiết bị: {self._device_label()}",
            f"ASR: {'Bật' if getattr(self.model, '_asr_pipe', None) is not None else 'Tắt'}",
            f"Ngôn ngữ: {payload.get('language') or 'Tự động'}",
            f"Số ký tự đầu vào: {len(payload.get('text', ''))}",
            f"Preset: {preset_name}",
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
        state = self._runtime_state.get(mode, {})
        started_at = state.get("started_at")
        offset = float(state.get("elapsed_offset_s") or 0.0)
        if not started_at:
            return offset
        return offset + (time.perf_counter() - started_at)

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

    def _play_completion_alert(self):
        def beep_once():
            if winsound is not None:
                try:
                    winsound.Beep(1350, 140)
                    return
                except Exception:
                    pass
            QApplication.beep()

        for index in range(5):
            QTimer.singleShot(index * 220, beep_once)

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
        if not self.current_output_path or not os.path.exists(self.current_output_path):
            return
        if self.result_player.playbackState() == QMediaPlayer.PlayingState:
            self.result_player.stop()
            return
        self.result_player.setSource(Path(self.current_output_path).as_uri())
        self.result_player.play()

    def _save_output(self):
        if not self.current_output_path or not os.path.exists(self.current_output_path):
            return
        output, _ = QFileDialog.getSaveFileName(self, "Lưu WAV", "", "WAV (*.wav)")
        if output:
            shutil.copy2(self.current_output_path, output)
            QMessageBox.information(self, "Đã lưu", output)

    def _on_result_playback_state_changed(self, state):
        is_playing = state == QMediaPlayer.PlayingState
        self.is_playing = is_playing
        label = "Dừng" if is_playing else "Phát kết quả"
        self.play_result_btn.setText(label)
        self.design_play_btn.setText(label)

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
                if self._active_worker_token is None or not self.active_mode:
                    return
                parts = line.split(" ")[1].split("/")
                step = int(parts[0])
                total = int(parts[1])
                mode = self.active_mode
                pct = 45 + int((step / total) * 50)  # Progress between 45 and 95
                self._update_progress(mode, f"Đang suy luận (bước {step}/{total})...", pct)
            except Exception:
                pass
            return
            
        if hasattr(self, "clone_log_info"):
            self.clone_log_info.appendPlainText(f"[SYS] {line}")
        if hasattr(self, "design_log_info"):
            self.design_log_info.appendPlainText(f"[SYS] {line}")

    def closeEvent(self, event):
        try:
            self.result_player.stop()
            self.media_player.stop()
        except Exception:
            pass
        if self.current_output_path or self.current_output_session_id:
            self._cleanup_current_output_artifact()
        super().closeEvent(event)


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
    
    # HÃ¡ÂºÂ¡n chÃ¡ÂºÂ¿ GPU chÃ¡ÂºÂ¡y 100% bÃ¡ÂºÂ±ng cÃƒÂ¡ch giÃ¡ÂºÂ£m luÃ¡Â»â€œng OMP vÃƒÂ  Torch Thread
    import os
    os.environ["OMP_NUM_THREADS"] = "1"
    torch.set_num_threads(1)
    
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
