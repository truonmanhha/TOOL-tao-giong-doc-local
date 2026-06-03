import argparse
import os
import subprocess
import tempfile
import threading
from pathlib import Path

import customtkinter as ctk
import imageio_ffmpeg
import sounddevice as sd
import soundfile as sf
import torch
from pydub import AudioSegment
from tkinter import filedialog, messagebox

from omnivoice import OmniVoice, OmniVoiceGenerationConfig
from omnivoice.utils.lang_map import LANG_NAMES, lang_display_name


ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

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


class OmniVoiceNativeApp(ctk.CTk):
    def __init__(self, model: OmniVoice | None):
        super().__init__()
        self.model = model
        self.sampling_rate = model.sampling_rate if model else 24000
        self.audio_output = None
        self.output_temp_file = None
        self.current_processed_ref = None
        self.is_playing = False

        self.title("OmniVoice Native Pro")
        self.geometry("1380x860")
        self.minsize(1200, 760)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main_area()
        self._show_screen("clone")

    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=260, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(6, weight=1)

        ctk.CTkLabel(
            self.sidebar,
            text="OmniVoice Native",
            font=ctk.CTkFont(size=28, weight="bold"),
        ).grid(row=0, column=0, padx=24, pady=(24, 6), sticky="w")
        ctk.CTkLabel(
            self.sidebar,
            text="App local xịn hơn bản dởm trước:\nclone giọng, cắt mẫu, thiết kế giọng",
            justify="left",
            text_color=("gray35", "gray70"),
            font=ctk.CTkFont(size=13),
        ).grid(row=1, column=0, padx=24, pady=(0, 18), sticky="w")

        self.clone_btn = ctk.CTkButton(self.sidebar, text="Clone Giọng", command=lambda: self._show_screen("clone"))
        self.clone_btn.grid(row=2, column=0, padx=20, pady=8, sticky="ew")
        self.design_btn = ctk.CTkButton(self.sidebar, text="Thiết Kế Giọng", command=lambda: self._show_screen("design"))
        self.design_btn.grid(row=3, column=0, padx=20, pady=8, sticky="ew")
        self.settings_btn = ctk.CTkButton(self.sidebar, text="Cài Đặt", command=lambda: self._show_screen("settings"))
        self.settings_btn.grid(row=4, column=0, padx=20, pady=8, sticky="ew")

        self.device_label = ctk.CTkLabel(
            self.sidebar,
            text=f"Thiết bị AI: {get_best_device().upper()}",
            anchor="w",
        )
        self.device_label.grid(row=7, column=0, padx=24, pady=(0, 10), sticky="ew")

        self.theme_menu = ctk.CTkOptionMenu(
            self.sidebar,
            values=["System", "Dark", "Light"],
            command=ctk.set_appearance_mode,
        )
        self.theme_menu.grid(row=8, column=0, padx=20, pady=(0, 20), sticky="ew")
        self.theme_menu.set("System")

    def _build_main_area(self):
        self.main = ctk.CTkFrame(self, corner_radius=18)
        self.main.grid(row=0, column=1, padx=18, pady=18, sticky="nsew")
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(1, weight=1)

        self.header = ctk.CTkFrame(self.main, fg_color="transparent")
        self.header.grid(row=0, column=0, padx=24, pady=(20, 10), sticky="ew")
        self.header.grid_columnconfigure(0, weight=1)
        self.title_label = ctk.CTkLabel(self.header, text="", font=ctk.CTkFont(size=30, weight="bold"))
        self.title_label.grid(row=0, column=0, sticky="w")
        self.subtitle_label = ctk.CTkLabel(self.header, text="", text_color=("gray35", "gray70"))
        self.subtitle_label.grid(row=1, column=0, sticky="w", pady=(4, 0))

        self.content = ctk.CTkFrame(self.main, fg_color="transparent")
        self.content.grid(row=1, column=0, padx=24, pady=(0, 24), sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        self.clone_screen = self._build_clone_screen()
        self.design_screen = self._build_design_screen()
        self.settings_screen = self._build_settings_screen()

    def _panel(self, parent):
        return ctk.CTkFrame(parent, corner_radius=16)

    def _build_clone_screen(self):
        frame = ctk.CTkFrame(self.content, fg_color="transparent")
        frame.grid_columnconfigure((0, 1), weight=1)
        frame.grid_rowconfigure(0, weight=1)

        left = self._panel(frame)
        left.grid(row=0, column=0, padx=(0, 10), sticky="nsew")
        left.grid_columnconfigure(0, weight=1)

        right = self._panel(frame)
        right.grid(row=0, column=1, padx=(10, 0), sticky="nsew")
        right.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(left, text="Văn bản cần đọc", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, padx=18, pady=(18, 8), sticky="w")
        self.clone_text = ctk.CTkTextbox(left, height=150)
        self.clone_text.grid(row=1, column=0, padx=18, pady=(0, 14), sticky="ew")

        ctk.CTkLabel(left, text="Nguồn mẫu: audio hoặc video", font=ctk.CTkFont(size=18, weight="bold")).grid(row=2, column=0, padx=18, pady=(0, 8), sticky="w")
        src_row = ctk.CTkFrame(left, fg_color="transparent")
        src_row.grid(row=3, column=0, padx=18, pady=(0, 8), sticky="ew")
        src_row.grid_columnconfigure(0, weight=1)
        self.source_path = ctk.StringVar(value="")
        self.source_entry = ctk.CTkEntry(src_row, textvariable=self.source_path)
        self.source_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkButton(src_row, text="Chọn file", command=self._browse_source).grid(row=0, column=1)

        trim = ctk.CTkFrame(left, fg_color="transparent")
        trim.grid(row=4, column=0, padx=18, pady=(4, 8), sticky="ew")
        ctk.CTkLabel(trim, text="Cắt từ giây").grid(row=0, column=0, sticky="w")
        self.trim_start = ctk.CTkEntry(trim, width=100)
        self.trim_start.grid(row=1, column=0, padx=(0, 14), pady=(4, 0), sticky="w")
        self.trim_start.insert(0, "0")
        ctk.CTkLabel(trim, text="Đến giây").grid(row=0, column=1, sticky="w")
        self.trim_end = ctk.CTkEntry(trim, width=100)
        self.trim_end.grid(row=1, column=1, pady=(4, 0), sticky="w")
        self.trim_end.insert(0, "8")

        self.preview_ref_btn = ctk.CTkButton(left, text="Xử Lý Mẫu Trước", command=self._prepare_reference_preview)
        self.preview_ref_btn.grid(row=5, column=0, padx=18, pady=(8, 8), sticky="ew")

        self.clone_lang = ctk.CTkOptionMenu(left, values=_ALL_LANGUAGES)
        self.clone_lang.grid(row=6, column=0, padx=18, pady=(0, 8), sticky="ew")
        self.clone_lang.set("Tự động")

        self.clone_ref_text = ctk.CTkTextbox(left, height=70)
        self.clone_ref_text.grid(row=7, column=0, padx=18, pady=(0, 8), sticky="ew")
        self.clone_ref_text.insert("1.0", "Nhap loi cua file mau vao day de clone giong.")

        self.clone_generate_btn = ctk.CTkButton(left, text="Tạo Giọng Từ Mẫu", height=46, command=self._start_clone_generation)
        self.clone_generate_btn.grid(row=8, column=0, padx=18, pady=(6, 18), sticky="ew")

        ctk.CTkLabel(right, text="Kết quả", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, padx=18, pady=(18, 8), sticky="w")
        self.clone_status = ctk.CTkLabel(right, text="Sẵn sàng", justify="left", anchor="w")
        self.clone_status.grid(row=1, column=0, padx=18, pady=(0, 8), sticky="ew")
        self.clone_info = ctk.CTkTextbox(right, height=200)
        self.clone_info.grid(row=2, column=0, padx=18, pady=(0, 8), sticky="nsew")
        self.clone_info.insert("1.0", "Bản native này hỗ trợ:\n- Chọn audio hoặc video mẫu\n- Cắt đoạn mẫu trước khi clone\n- Tạo giọng local không cần web\n")

        control_row = ctk.CTkFrame(right, fg_color="transparent")
        control_row.grid(row=3, column=0, padx=18, pady=(4, 18), sticky="ew")
        control_row.grid_columnconfigure((0, 1, 2), weight=1)
        self.play_btn = ctk.CTkButton(control_row, text="Phát", state="disabled", command=self._toggle_play)
        self.play_btn.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        self.save_btn = ctk.CTkButton(control_row, text="Lưu WAV", state="disabled", command=self._save_output)
        self.save_btn.grid(row=0, column=1, padx=8, sticky="ew")
        self.save_ref_btn = ctk.CTkButton(control_row, text="Lưu mẫu đã cắt", state="disabled", command=self._save_processed_ref)
        self.save_ref_btn.grid(row=0, column=2, padx=(8, 0), sticky="ew")

        return frame

    def _build_design_screen(self):
        frame = ctk.CTkFrame(self.content, fg_color="transparent")
        frame.grid_columnconfigure((0, 1), weight=1)

        left = self._panel(frame)
        left.grid(row=0, column=0, padx=(0, 10), sticky="nsew")
        left.grid_columnconfigure((0, 1), weight=1)
        right = self._panel(frame)
        right.grid(row=0, column=1, padx=(10, 0), sticky="nsew")
        right.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(left, text="Nội dung đọc", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, columnspan=2, padx=18, pady=(18, 8), sticky="w")
        self.design_text = ctk.CTkTextbox(left, height=160)
        self.design_text.grid(row=1, column=0, columnspan=2, padx=18, pady=(0, 12), sticky="ew")
        self.design_text.insert("1.0", "Xin chào, đây là giọng nhân vật ảo được thiết kế ngay trên máy tính của bạn.")

        self.design_lang = ctk.CTkOptionMenu(left, values=_ALL_LANGUAGES)
        self.design_lang.grid(row=2, column=0, columnspan=2, padx=18, pady=(0, 12), sticky="ew")
        self.design_lang.set("Tự động")

        self.design_menus = {}
        row = 3
        for idx, (label, options) in enumerate(_CATEGORIES.items()):
            col = idx % 2
            if col == 0 and idx != 0:
                row += 1
            ctk.CTkLabel(left, text=label).grid(row=row, column=col, padx=18, pady=(0, 4), sticky="w")
            menu = ctk.CTkOptionMenu(left, values=["Tự động"] + options)
            menu.grid(row=row + 1, column=col, padx=18, pady=(0, 10), sticky="ew")
            menu.set("Tự động")
            self.design_menus[label] = menu
            if col == 1:
                row += 1

        self.design_btn = ctk.CTkButton(left, text="Tạo Giọng Thiết Kế", height=46, command=self._start_design_generation)
        self.design_btn.grid(row=row + 2, column=0, columnspan=2, padx=18, pady=(8, 18), sticky="ew")

        ctk.CTkLabel(right, text="Mô tả giọng & kết quả", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, padx=18, pady=(18, 8), sticky="w")
        self.design_status = ctk.CTkLabel(right, text="Chưa tạo gì", justify="left", anchor="w")
        self.design_status.grid(row=1, column=0, padx=18, pady=(0, 8), sticky="ew")
        self.design_info = ctk.CTkTextbox(right, height=260)
        self.design_info.grid(row=2, column=0, padx=18, pady=(0, 12), sticky="nsew")
        self.design_play_btn = ctk.CTkButton(right, text="Phát", state="disabled", command=self._toggle_play)
        self.design_play_btn.grid(row=3, column=0, padx=18, pady=(0, 8), sticky="ew")
        self.design_save_btn = ctk.CTkButton(right, text="Lưu WAV", state="disabled", command=self._save_output)
        self.design_save_btn.grid(row=4, column=0, padx=18, pady=(0, 18), sticky="ew")

        return frame

    def _build_settings_screen(self):
        frame = ctk.CTkFrame(self.content, fg_color="transparent")
        panel = self._panel(frame)
        panel.pack(fill="both", expand=True)

        ctk.CTkLabel(panel, text="Cài đặt nâng cao", font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w", padx=18, pady=(18, 8))

        self.num_step_entry = self._settings_entry(panel, "Inference steps", "32")
        self.guidance_entry = self._settings_entry(panel, "Guidance scale", "2.0")
        self.speed_entry = self._settings_entry(panel, "Tốc độ", "1.0")
        self.duration_entry = self._settings_entry(panel, "Thời lượng (để 0 nếu không ép)", "0")

        self.denoise_var = ctk.BooleanVar(value=True)
        self.preprocess_var = ctk.BooleanVar(value=True)
        self.postprocess_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(panel, text="Khử ồn", variable=self.denoise_var).pack(anchor="w", padx=18, pady=6)
        ctk.CTkCheckBox(panel, text="Tiền xử lý mẫu", variable=self.preprocess_var).pack(anchor="w", padx=18, pady=6)
        ctk.CTkCheckBox(panel, text="Hậu xử lý đầu ra", variable=self.postprocess_var).pack(anchor="w", padx=18, pady=6)

        ctk.CTkLabel(
            panel,
            text="Gợi ý: dùng đoạn mẫu 3-10 giây. Video sẽ được tự bóc audio ra để clone.",
            text_color=("gray35", "gray70"),
        ).pack(anchor="w", padx=18, pady=(18, 0))

        return frame

    def _settings_entry(self, parent, label, default):
        ctk.CTkLabel(parent, text=label).pack(anchor="w", padx=18, pady=(10, 4))
        entry = ctk.CTkEntry(parent)
        entry.pack(fill="x", padx=18)
        entry.insert(0, default)
        return entry

    def _show_screen(self, name: str):
        screens = {
            "clone": self.clone_screen,
            "design": self.design_screen,
            "settings": self.settings_screen,
        }
        meta = {
            "clone": ("Clone giọng từ audio/video mẫu", "Chọn file mẫu, cắt đoạn ngon nhất rồi xuất giọng local."),
            "design": ("Thiết kế giọng mới", "Tạo nhân vật giọng ảo giống bản web nhưng chạy local."),
            "settings": ("Cài đặt chất lượng", "Tinh chỉnh thông số sinh giọng thay vì xài bản native dởm trước."),
        }
        for screen in screens.values():
            screen.grid_forget()
        screens[name].grid(row=0, column=0, sticky="nsew")
        title, subtitle = meta[name]
        self.title_label.configure(text=title)
        self.subtitle_label.configure(text=subtitle)

        active = {"clone": self.clone_btn, "design": self.design_btn, "settings": self.settings_btn}
        for key, btn in active.items():
            if key == name:
                btn.configure(fg_color=("#2563eb", "#1d4ed8"))
            else:
                btn.configure(fg_color=("#3b8ed0", "#1f6aa5"))

    def _browse_source(self):
        file_path = filedialog.askopenfilename(
            title="Chọn audio hoặc video mẫu",
            filetypes=[
                ("Media files", "*.wav *.mp3 *.flac *.m4a *.aac *.mp4 *.mov *.mkv *.avi"),
                ("All files", "*.*"),
            ],
        )
        if file_path:
            self.source_path.set(file_path)
            self.clone_status.configure(text=f"Đã chọn mẫu: {Path(file_path).name}")

    def _parse_float(self, entry: ctk.CTkEntry, fallback: float):
        try:
            return float(entry.get().strip())
        except ValueError:
            return fallback

    def _build_generation_config(self):
        return OmniVoiceGenerationConfig(
            num_step=int(self._parse_float(self.num_step_entry, 32)),
            guidance_scale=self._parse_float(self.guidance_entry, 2.0),
            denoise=bool(self.denoise_var.get()),
            preprocess_prompt=bool(self.preprocess_var.get()),
            postprocess_output=bool(self.postprocess_var.get()),
        )

    def _extract_audio_from_video(self, video_path: str, output_wav: str):
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        command = [
            ffmpeg_exe,
            "-y",
            "-i",
            video_path,
            "-vn",
            "-ac",
            "1",
            "-ar",
            "24000",
            output_wav,
        ]
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _prepare_reference_audio(self):
        source = self.source_path.get().strip()
        if not source:
            raise ValueError("Chưa chọn file mẫu.")
        if not os.path.exists(source):
            raise FileNotFoundError("File mẫu không tồn tại.")

        suffix = Path(source).suffix.lower()
        working_source = source

        if suffix in {".mp4", ".mov", ".mkv", ".avi"}:
            extracted = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
            extracted.close()
            self._extract_audio_from_video(source, extracted.name)
            working_source = extracted.name

        audio = AudioSegment.from_file(working_source)
        start_sec = max(0.0, self._parse_float(self.trim_start, 0.0))
        end_sec = self._parse_float(self.trim_end, max(3.0, len(audio) / 1000.0))
        if end_sec <= start_sec:
            raise ValueError("Thời gian cắt không hợp lệ. Giây kết thúc phải lớn hơn giây bắt đầu.")

        trimmed = audio[int(start_sec * 1000): int(end_sec * 1000)]
        temp_ref = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        temp_ref.close()
        trimmed.export(temp_ref.name, format="wav")
        self.current_processed_ref = temp_ref.name
        return temp_ref.name, start_sec, end_sec

    def _prepare_reference_preview(self):
        try:
            path, start_sec, end_sec = self._prepare_reference_audio()
        except Exception as exc:
            messagebox.showerror("Lỗi xử lý mẫu", str(exc))
            return

        self.clone_status.configure(text=f"Đã cắt mẫu từ {start_sec:.2f}s đến {end_sec:.2f}s")
        self.save_ref_btn.configure(state="normal")
        self.clone_info.delete("1.0", "end")
        self.clone_info.insert(
            "1.0",
            f"Đã xử lý mẫu thành công.\n\nFile gốc: {self.source_path.get()}\nFile mẫu sau cắt: {path}\nĐoạn dùng để clone: {start_sec:.2f}s -> {end_sec:.2f}s\n\nGiờ bấm 'Tạo Giọng Từ Mẫu' là dùng đúng đoạn này.",
        )

    def _start_clone_generation(self):
        if self.model is None:
            messagebox.showerror("Lỗi", "Model chưa load xong.")
            return
        if not self.clone_text.get("1.0", "end").strip():
            messagebox.showwarning("Thiếu nội dung", "Nhập văn bản cần đọc đã.")
            return

        self.clone_generate_btn.configure(state="disabled", text="Đang tạo...")
        self.clone_status.configure(text="Đang xử lý mẫu và tạo giọng...")
        threading.Thread(target=self._clone_worker, daemon=True).start()

    def _clone_worker(self):
        try:
            ref_path, start_sec, end_sec = self._prepare_reference_audio()
            gen_config = self._build_generation_config()
            language = self.clone_lang.get()
            if language in {"Auto", "Tự động"}:
                language = None

            ref_text = self.clone_ref_text.get("1.0", "end").strip()
            if not ref_text or ref_text == "Nhap loi cua file mau vao day de clone giong.":
                raise ValueError(
                    "Ban native nay dang tat ASR de tranh tai them model nang."
                    " Hay nhap loi cua file mau de clone giong."
                )

            prompt = self.model.create_voice_clone_prompt(
                ref_audio=ref_path,
                ref_text=ref_text or None,
            )
            kwargs = {
                "text": self.clone_text.get("1.0", "end").strip(),
                "language": language,
                "generation_config": gen_config,
                "voice_clone_prompt": prompt,
            }
            speed = self._parse_float(self.speed_entry, 1.0)
            duration = self._parse_float(self.duration_entry, 0.0)
            if speed != 1.0:
                kwargs["speed"] = speed
            if duration > 0:
                kwargs["duration"] = duration

            audio = self.model.generate(**kwargs)
            self.audio_output = audio[0]
            self.after(0, lambda: self._on_clone_success(start_sec, end_sec, ref_path))
        except Exception as exc:
            self.after(0, lambda: self._on_generation_error(exc, clone_mode=True))

    def _on_clone_success(self, start_sec, end_sec, ref_path):
        self.clone_generate_btn.configure(state="normal", text="Tạo Giọng Từ Mẫu")
        self.clone_status.configure(text="Xong rồi. Có thể phát hoặc lưu file.")
        self.play_btn.configure(state="normal")
        self.save_btn.configure(state="normal")
        self.save_ref_btn.configure(state="normal")
        self.clone_info.delete("1.0", "end")
        self.clone_info.insert(
            "1.0",
            f"Clone thành công.\n\nĐoạn mẫu đã dùng: {start_sec:.2f}s -> {end_sec:.2f}s\nFile mẫu đang dùng: {ref_path}\nTốc độ: {self.speed_entry.get()}\nDuration ép: {self.duration_entry.get()}\nInference steps: {self.num_step_entry.get()}\n",
        )

    def _build_design_instruct(self):
        parts = []
        for label, menu in self.design_menus.items():
            value = menu.get()
            if value and value != "Tự động":
                parts.append(_VI_TO_INSTRUCT.get(value, value))
        return ", ".join(parts) if parts else None

    def _start_design_generation(self):
        if self.model is None:
            messagebox.showerror("Lỗi", "Model chưa load xong.")
            return
        text = self.design_text.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning("Thiếu nội dung", "Nhập văn bản cần đọc đã.")
            return
        self.design_btn.configure(state="disabled", text="Đang tạo...")
        self.design_status.configure(text="Đang thiết kế giọng và sinh audio...")
        threading.Thread(target=self._design_worker, daemon=True).start()

    def _design_worker(self):
        try:
            gen_config = self._build_generation_config()
            language = self.design_lang.get()
            if language in {"Auto", "Tự động"}:
                language = None
            kwargs = {
                "text": self.design_text.get("1.0", "end").strip(),
                "language": language,
                "generation_config": gen_config,
            }
            instruct = self._build_design_instruct()
            if instruct:
                kwargs["instruct"] = instruct
            speed = self._parse_float(self.speed_entry, 1.0)
            duration = self._parse_float(self.duration_entry, 0.0)
            if speed != 1.0:
                kwargs["speed"] = speed
            if duration > 0:
                kwargs["duration"] = duration
            audio = self.model.generate(**kwargs)
            self.audio_output = audio[0]
            self.after(0, lambda: self._on_design_success(instruct or "Auto Voice"))
        except Exception as exc:
            self.after(0, lambda: self._on_generation_error(exc, clone_mode=False))

    def _on_design_success(self, instruct):
        self.design_btn.configure(state="normal", text="Tạo Giọng Thiết Kế")
        self.design_status.configure(text="Đã tạo giọng thiết kế thành công.")
        self.design_play_btn.configure(state="normal")
        self.design_save_btn.configure(state="normal")
        self.design_info.delete("1.0", "end")
        self.design_info.insert(
            "1.0",
            f"Thiết kế giọng thành công.\n\nThuộc tính dùng: {instruct}\nInference steps: {self.num_step_entry.get()}\nGuidance: {self.guidance_entry.get()}\n",
        )

    def _on_generation_error(self, exc, clone_mode: bool):
        if clone_mode:
            self.clone_generate_btn.configure(state="normal", text="Tạo Giọng Từ Mẫu")
            self.clone_status.configure(text="Lỗi khi tạo giọng.")
        else:
            self.design_btn.configure(state="normal", text="Tạo Giọng Thiết Kế")
            self.design_status.configure(text="Lỗi khi tạo giọng thiết kế.")
        messagebox.showerror("Lỗi hệ thống", str(exc))

    def _toggle_play(self):
        if self.audio_output is None:
            return
        if self.is_playing:
            sd.stop()
            self.is_playing = False
            self.play_btn.configure(text="Phát")
            self.design_play_btn.configure(text="Phát")
            return
        self.is_playing = True
        self.play_btn.configure(text="Dừng")
        self.design_play_btn.configure(text="Dừng")
        sd.play(self.audio_output, self.sampling_rate)
        threading.Thread(target=self._wait_playback_done, daemon=True).start()

    def _wait_playback_done(self):
        sd.wait()
        self.is_playing = False
        self.after(0, lambda: self.play_btn.configure(text="Phát"))
        self.after(0, lambda: self.design_play_btn.configure(text="Phát"))

    def _save_output(self):
        if self.audio_output is None:
            return
        output = filedialog.asksaveasfilename(
            title="Lưu file WAV",
            defaultextension=".wav",
            filetypes=[("WAV", "*.wav")],
        )
        if output:
            sf.write(output, self.audio_output, self.sampling_rate)
            messagebox.showinfo("Đã lưu", output)

    def _save_processed_ref(self):
        if not self.current_processed_ref or not os.path.exists(self.current_processed_ref):
            messagebox.showwarning("Chưa có mẫu", "Bạn chưa xử lý mẫu để lưu.")
            return
        output = filedialog.asksaveasfilename(
            title="Lưu mẫu đã cắt",
            defaultextension=".wav",
            filetypes=[("WAV", "*.wav")],
        )
        if output:
            audio, sr = sf.read(self.current_processed_ref)
            sf.write(output, audio, sr)
            messagebox.showinfo("Đã lưu", output)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="k2-fsa/OmniVoice")
    parser.add_argument("--no-model", action="store_true")
    args = parser.parse_args()

    model = None
    if not args.no_model:
        device = get_best_device()
        dtype = torch.float16 if device != "cpu" else torch.float32
        print(f"Dang nap model tren {device}...")
        model = OmniVoice.from_pretrained(
            args.model,
            device_map=device,
            dtype=dtype,
            load_asr=False,
        )
        print("Nap model xong.")

    app = OmniVoiceNativeApp(model)
    app.mainloop()


if __name__ == "__main__":
    main()
