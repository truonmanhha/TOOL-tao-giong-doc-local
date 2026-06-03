import os
import sys
import time
from pathlib import Path

import customtkinter as ctk


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class SplashApp(ctk.CTk):
    def __init__(self, status_file: Path):
        super().__init__()
        self.status_file = status_file
        self.last_text = "Dang khoi dong..."
        self.last_value = 0.03

        self.title("OmniVoice Dang Khoi Dong")
        self.geometry("680x360")
        self.resizable(False, False)
        self.overrideredirect(False)

        self.configure(fg_color="#0b1020")

        outer = ctk.CTkFrame(self, corner_radius=24, fg_color="#11182d", border_width=1, border_color="#22304f")
        outer.pack(fill="both", expand=True, padx=18, pady=18)

        ctk.CTkLabel(
            outer,
            text="OmniVoice App Local",
            font=ctk.CTkFont(size=30, weight="bold"),
            text_color="#f8fafc",
        ).pack(anchor="w", padx=26, pady=(24, 6))

        ctk.CTkLabel(
            outer,
            text="Dang mo giao dien local xinh hon CMD. Ban cu doi mot chut, app se tu bat len.",
            font=ctk.CTkFont(size=14),
            text_color="#94a3b8",
            justify="left",
        ).pack(anchor="w", padx=26, pady=(0, 22))

        self.stage_label = ctk.CTkLabel(
            outer,
            text=self.last_text,
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#e2e8f0",
            anchor="w",
        )
        self.stage_label.pack(fill="x", padx=26)

        self.detail_label = ctk.CTkLabel(
            outer,
            text="Kiem tra moi truong, cache, model va khoi dong app...",
            font=ctk.CTkFont(size=13),
            text_color="#7dd3fc",
            anchor="w",
        )
        self.detail_label.pack(fill="x", padx=26, pady=(8, 18))

        self.progress = ctk.CTkProgressBar(outer, height=18, corner_radius=100, progress_color="#3b82f6")
        self.progress.pack(fill="x", padx=26, pady=(0, 14))
        self.progress.set(self.last_value)

        self.percent_label = ctk.CTkLabel(
            outer,
            text="3%",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color="#f8fafc",
        )
        self.percent_label.pack(anchor="e", padx=26)

        tips = ctk.CTkFrame(outer, fg_color="#0f172a", corner_radius=18)
        tips.pack(fill="x", padx=26, pady=(18, 0))
        ctk.CTkLabel(
            tips,
            text="Meo: lan dau se lau hon vi can cai thu vien va nap model vao bo nho. Cac lan sau se on hon.",
            text_color="#cbd5e1",
            font=ctk.CTkFont(size=12),
            justify="left",
            wraplength=580,
        ).pack(anchor="w", padx=16, pady=14)

        self.after(250, self.poll_status)

    def poll_status(self):
        if self.status_file.exists():
            try:
                raw = self.status_file.read_text(encoding="utf-8").strip()
            except OSError:
                raw = ""

            if raw:
                if raw == "DONE":
                    self.destroy()
                    return
                parts = raw.split("|", 2)
                if len(parts) == 3:
                    stage, percent, detail = parts
                    try:
                        value = max(0.0, min(1.0, float(percent) / 100.0))
                    except ValueError:
                        value = self.last_value
                    self.last_text = stage or self.last_text
                    self.last_value = value
                    self.stage_label.configure(text=self.last_text)
                    self.detail_label.configure(text=detail)
                    self.progress.set(value)
                    self.percent_label.configure(text=f"{int(round(value * 100))}%")

        self.after(350, self.poll_status)


def main():
    if len(sys.argv) < 2:
        raise SystemExit(1)
    status_file = Path(sys.argv[1])
    status_file.parent.mkdir(parents=True, exist_ok=True)
    app = SplashApp(status_file)
    app.mainloop()


if __name__ == "__main__":
    main()
