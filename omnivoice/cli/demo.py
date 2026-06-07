#!/usr/bin/env python3
# Copyright    2026  Xiaomi Corp.        (authors:  Han Zhu)
#
# See ../../LICENSE for clarification regarding multiple authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Gradio demo for OmniVoice.

Supports voice cloning and voice design.

Usage:
    omnivoice-demo --model /path/to/checkpoint --port 8000
"""

import argparse
import logging
from typing import Any, Dict

import gradio as gr
import numpy as np
import torch

from omnivoice import OmniVoice, OmniVoiceGenerationConfig
from omnivoice.utils.lang_map import LANG_NAMES, lang_display_name


def get_best_device():
    """Auto-detect the best available device: CUDA > MPS > CPU."""
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


# ---------------------------------------------------------------------------
# Language list — all 600+ supported languages
# ---------------------------------------------------------------------------
_ALL_LANGUAGES = ["Tự động"] + sorted(lang_display_name(n) for n in LANG_NAMES)


# ---------------------------------------------------------------------------
# Voice Design instruction templates
# ---------------------------------------------------------------------------
# Each option is displayed as "English / 中文".
# The model expects English for accents and Chinese for dialects.
_CATEGORIES = {
    "Giới tính": ["Nam", "Nữ"],
    "Độ tuổi": [
        "Trẻ em",
        "Thiếu niên",
        "Thanh niên",
        "Trung niên",
        "Người già",
    ],
    "Độ cao giọng (Pitch)": [
        "Rất thấp",
        "Thấp",
        "Vừa phải",
        "Cao",
        "Rất cao",
    ],
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
    "Nam": "Male", "Nữ": "Female",
    "Trẻ em": "Child", "Thiếu niên": "Teenager", "Thanh niên": "Young Adult", "Trung niên": "Middle-aged", "Người già": "Elderly",
    "Rất thấp": "Very Low Pitch", "Thấp": "Low Pitch", "Vừa phải": "Moderate Pitch", "Cao": "High Pitch", "Rất cao": "Very High Pitch",
    "Thì thầm": "Whisper",
    "Giọng Mỹ": "American Accent", "Giọng Úc": "Australian Accent", "Giọng Anh": "British Accent", "Giọng Trung": "Chinese Accent",
    "Giọng Canada": "Canadian Accent", "Giọng Ấn Độ": "Indian Accent", "Giọng Hàn Quốc": "Korean Accent", "Giọng Bồ Đào Nha": "Portuguese Accent",
    "Giọng Nga": "Russian Accent", "Giọng Nhật Bản": "Japanese Accent",
    "Tiếng Hà Nam": "河南话", "Tiếng Thiểm Tây": "陕西话", "Tiếng Tứ Xuyên": "四川话", "Tiếng Quý Châu": "贵州话",
    "Tiếng Vân Nam": "云南话", "Tiếng Quế Lâm": "桂林话", "Tiếng Tế Nam": "济南话", "Tiếng Thạch Gia Trang": "石家庄话",
    "Tiếng Cam Túc": "甘肃话", "Tiếng Ninh Hạ": "宁夏话", "Tiếng Thanh Đảo": "青岛话", "Tiếng Đông Bắc": "东北话"
}

_ATTR_INFO = {
    "English Accent / Khẩu âm Tiếng Anh": "Chỉ hiệu quả với tiếng Anh.",
    "Chinese Dialect / Phương ngôn Tiếng Trung": "Chỉ hiệu quả với tiếng Trung.",
}

# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="omnivoice-demo",
        description="Launch a Gradio demo for OmniVoice.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--model",
        default="k2-fsa/OmniVoice",
        help="Model checkpoint path or HuggingFace repo id.",
    )
    parser.add_argument(
        "--device", default=None, help="Device to use. Auto-detected if not specified."
    )
    parser.add_argument("--ip", default="0.0.0.0", help="Server IP (default: 0.0.0.0).")
    parser.add_argument(
        "--port", type=int, default=None, help="Server port (default: auto)."
    )
    parser.add_argument(
        "--root-path",
        default=None,
        help="Root path for reverse proxy.",
    )
    parser.add_argument(
        "--share", action="store_true", default=False, help="Create public link."
    )
    parser.add_argument(
        "--no-asr",
        action="store_true",
        default=False,
        help="Skip loading Whisper ASR model. Reference text auto-transcription"
        " will be unavailable.",
    )
    parser.add_argument(
        "--asr-model",
        default="openai/whisper-large-v3-turbo",
        help="ASR model path or HuggingFace repo id"
        " (default: openai/whisper-large-v3-turbo).",
    )
    return parser


# ---------------------------------------------------------------------------
# Build demo
# ---------------------------------------------------------------------------


def build_demo(
    model: OmniVoice,
    checkpoint: str,
    generate_fn=None,
) -> gr.Blocks:

    sampling_rate = model.sampling_rate

    # -- shared generation core --
    def _gen_core(
        text,
        language,
        ref_audio,
        instruct,
        num_step,
        guidance_scale,
        denoise,
        speed,
        duration,
        preprocess_prompt,
        postprocess_output,
        mode,
        ref_text=None,
    ):
        if not text or not text.strip():
            return None, "Vui lòng nhập văn bản cần tạo giọng."

        gen_config = OmniVoiceGenerationConfig(
            num_step=int(num_step or 32),
            guidance_scale=float(guidance_scale) if guidance_scale is not None else 2.0,
            denoise=bool(denoise) if denoise is not None else True,
            preprocess_prompt=bool(preprocess_prompt),
            postprocess_output=bool(postprocess_output),
        )

        lang = language if (language and language not in ("Auto", "Tự động")) else None

        kw: Dict[str, Any] = dict(
            text=text.strip(), language=lang, generation_config=gen_config
        )

        if speed is not None and float(speed) != 1.0:
            kw["speed"] = float(speed)
        if duration is not None and float(duration) > 0:
            kw["duration"] = float(duration)

        if mode == "clone":
            if not ref_audio:
                return None, "Vui lòng tải lên âm thanh tham chiếu."
            kw["voice_clone_prompt"] = model.create_voice_clone_prompt(
                ref_audio=ref_audio,
                ref_text=ref_text,
            )

        if instruct and instruct.strip():
            kw["instruct"] = instruct.strip()

        try:
            audio = model.generate(**kw)
        except Exception as e:
            return None, f"Error: {type(e).__name__}: {e}"

        waveform = (audio[0] * 32767).astype(np.int16)
        return (sampling_rate, waveform), "Hoàn thành."

    # Allow external wrappers (e.g. spaces.GPU for ZeroGPU Spaces)
    _gen = generate_fn if generate_fn is not None else _gen_core

    # =====================================================================
    # UI
    # =====================================================================
    theme = gr.themes.Soft(
        font=["Inter", "Arial", "sans-serif"],
    )
    css = """
    .gradio-container {max-width: 100% !important; font-size: 16px !important;}
    .gradio-container h1 {font-size: 1.5em !important;}
    .gradio-container .prose {font-size: 1.1em !important;}
    .compact-audio audio {height: 60px !important;}
    .compact-audio .waveform {min-height: 80px !important;}
    """

    # Reusable: language dropdown component
    def _lang_dropdown(label="Ngôn ngữ (tùy chọn)", value="Tự động"):
        return gr.Dropdown(
            label=label,
            choices=_ALL_LANGUAGES,
            value=value,
            allow_custom_value=False,
            interactive=True,
            info="Để 'Tự động' để tự động phát hiện ngôn ngữ.",
        )

    # Reusable: optional generation settings accordion
    def _gen_settings():
        with gr.Accordion("Cài đặt tạo giọng (tùy chọn)", open=False):
            sp = gr.Slider(
                0.5,
                1.5,
                value=1.0,
                step=0.05,
                label="Tốc độ",
                info="1.0 = bình thường. >1 nhanh hơn, <1 chậm hơn. Sẽ bị bỏ qua nếu đặt Thời lượng (Duration).",
            )
            du = gr.Number(
                value=None,
                label="Thời lượng (giây)",
                info=(
                    "Để trống để dùng theo tốc độ."
                    " Đặt thời lượng cố định để bỏ qua tốc độ."
                ),
            )
            ns = gr.Slider(
                4,
                64,
                value=32,
                step=1,
                label="Số bước Inference",
                info="Mặc định: 32. Thấp = nhanh hơn, Cao = chất lượng tốt hơn.",
            )
            dn = gr.Checkbox(
                label="Khử ồn (Denoise)",
                value=True,
                info="Mặc định: Bật. Bỏ chọn để tắt khử tiếng ồn.",
            )
            gs = gr.Slider(
                0.0,
                4.0,
                value=2.0,
                step=0.1,
                label="Mức độ tuân theo văn bản (Guidance Scale CFG)",
                info="Mặc định: 2.0.",
            )
            pp = gr.Checkbox(
                label="Tiền xử lý âm thanh tham chiếu",
                value=True,
                info="Áp dụng loại bỏ khoảng lặng và cắt âm thanh tham chiếu, thêm dấu câu vào cuối văn bản tham chiếu (nếu chưa có)",
            )
            po = gr.Checkbox(
                label="Hậu xử lý đầu ra",
                value=True,
                info="Xóa các khoảng lặng dài khỏi âm thanh được tạo ra.",
            )
        return ns, gs, dn, sp, du, pp, po

    with gr.Blocks(theme=theme, css=css, title="OmniVoice Demo") as demo:
        gr.Markdown(
            """
# Bản Demo OmniVoice (Giao diện Tiếng Việt)

Mô hình Text-to-Speech (Chuyển văn bản thành giọng nói) tiên tiến nhất hỗ trợ **600+ ngôn ngữ**, với các tính năng:

- **Clone Giọng (Voice Clone)** — Sao chép bất kỳ giọng nào từ một âm thanh tham chiếu
- **Thiết kế Giọng (Voice Design)** — Tạo giọng nói tùy chỉnh với các thuộc tính người nói

Được xây dựng bằng [OmniVoice](https://github.com/k2-fsa/OmniVoice)
bởi team Xiaomi AI Lab Next-gen Kaldi.
"""
        )

        with gr.Tabs():
            # ==============================================================
            # Voice Clone
            # ==============================================================
            with gr.TabItem("Clone Giọng (Voice Clone)"):
                with gr.Row():
                    with gr.Column(scale=1):
                        vc_text = gr.Textbox(
                            label="Văn bản cần đọc",
                            lines=4,
                            placeholder="Nhập văn bản bạn muốn tạo giọng nói...",
                        )
                        vc_ref_audio = gr.Audio(
                            label="Âm thanh tham chiếu (Reference Audio)",
                            type="filepath",
                            elem_classes="compact-audio",
                        )
                        gr.Markdown(
                            "<span style='font-size:0.85em;color:#888;'>"
                            "Khuyên dùng: âm thanh dài 3–10 giây. "
                            "</span>"
                        )
                        vc_ref_text = gr.Textbox(
                            label=("Văn bản của âm thanh tham chiếu (Tùy chọn)"),
                            lines=2,
                            placeholder="Văn bản của âm thanh tham chiếu. Để trống"
                            " để tự động nhận dạng (ASR).",
                        )
                        vc_lang = _lang_dropdown("Ngôn ngữ (tùy chọn)")
                        with gr.Accordion("Hướng dẫn (Tùy chọn - Instruct)", open=False):
                            vc_instruct = gr.Textbox(label="Hướng dẫn", lines=2)
                        (
                            vc_ns,
                            vc_gs,
                            vc_dn,
                            vc_sp,
                            vc_du,
                            vc_pp,
                            vc_po,
                        ) = _gen_settings()
                        vc_btn = gr.Button("Tạo Giọng / Generate", variant="primary")
                    with gr.Column(scale=1):
                        vc_audio = gr.Audio(
                            label="Âm thanh Đầu ra",
                            type="numpy",
                        )
                        vc_status = gr.Textbox(label="Trạng thái", lines=2)

                def _clone_fn(
                    text, lang, ref_aud, ref_text, instruct, ns, gs, dn, sp, du, pp, po
                ):
                    return _gen(
                        text,
                        lang,
                        ref_aud,
                        instruct,
                        ns,
                        gs,
                        dn,
                        sp,
                        du,
                        pp,
                        po,
                        mode="clone",
                        ref_text=ref_text or None,
                    )

                vc_btn.click(
                    _clone_fn,
                    inputs=[
                        vc_text,
                        vc_lang,
                        vc_ref_audio,
                        vc_ref_text,
                        vc_instruct,
                        vc_ns,
                        vc_gs,
                        vc_dn,
                        vc_sp,
                        vc_du,
                        vc_pp,
                        vc_po,
                    ],
                    outputs=[vc_audio, vc_status],
                )

            # ==============================================================
            # Voice Design
            # ==============================================================
            with gr.TabItem("Thiết kế Giọng (Voice Design)"):
                with gr.Row():
                    with gr.Column(scale=1):
                        vd_text = gr.Textbox(
                            label="Văn bản cần đọc",
                            lines=4,
                            placeholder="Nhập văn bản bạn muốn tạo giọng nói...",
                        )
                        vd_lang = _lang_dropdown()

                        _AUTO = "Tự động"
                        vd_groups = []
                        for _cat, _choices in _CATEGORIES.items():
                            vd_groups.append(
                                gr.Dropdown(
                                    label=_cat,
                                    choices=[_AUTO] + _choices,
                                    value=_AUTO,
                                    info=_ATTR_INFO.get(_cat),
                                )
                            )

                        (
                            vd_ns,
                            vd_gs,
                            vd_dn,
                            vd_sp,
                            vd_du,
                            vd_pp,
                            vd_po,
                        ) = _gen_settings()
                        vd_btn = gr.Button("Tạo Giọng / Generate", variant="primary")
                    with gr.Column(scale=1):
                        vd_audio = gr.Audio(
                            label="Âm thanh Đầu ra",
                            type="numpy",
                        )
                        vd_status = gr.Textbox(label="Trạng thái", lines=2)

                def _build_instruct(groups):
                    selected = [g for g in groups if g and g not in ("Auto", "Tự động")]
                    if not selected:
                        return None
                    parts = []
                    for v in selected:
                        parts.append(_VI_TO_INSTRUCT.get(v, v))
                    return ", ".join(parts)

                def _design_fn(text, lang, ns, gs, dn, sp, du, pp, po, *groups):
                    return _gen(
                        text,
                        lang,
                        None,
                        _build_instruct(groups),
                        ns,
                        gs,
                        dn,
                        sp,
                        du,
                        pp,
                        po,
                        mode="design",
                    )

                vd_btn.click(
                    _design_fn,
                    inputs=[
                        vd_text,
                        vd_lang,
                        vd_ns,
                        vd_gs,
                        vd_dn,
                        vd_sp,
                        vd_du,
                        vd_pp,
                        vd_po,
                    ]
                    + vd_groups,
                    outputs=[vd_audio, vd_status],
                )

    return demo


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv=None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    )
    parser = build_parser()
    args = parser.parse_args(argv)

    device = args.device or get_best_device()

    checkpoint = args.model
    if not checkpoint:
        parser.print_help()
        return 0
    logging.info(f"Loading model from {checkpoint}, device={device} ...")
    model = OmniVoice.from_pretrained(
        checkpoint,
        device_map=device,
        dtype=torch.float16,
        load_asr=not args.no_asr,
        asr_model_name=args.asr_model,
    )
    print("Model loaded.")

    demo = build_demo(model, checkpoint)

    launch_kwargs = {
        "server_name": args.ip,
        "share": args.share,
        "root_path": args.root_path,
    }
    if args.port is not None:
        launch_kwargs["server_port"] = args.port

    demo.queue().launch(**launch_kwargs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
