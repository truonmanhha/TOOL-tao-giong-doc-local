import argparse
import logging
from typing import Any, Dict

import gradio as gr
import numpy as np
import torch

from omnivoice import OmniVoice, OmniVoiceGenerationConfig
from omnivoice.utils.lang_map import LANG_NAMES, lang_display_name


def get_best_device():
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


_ALL_LANGUAGES = ["Tự động"] + sorted(lang_display_name(n) for n in LANG_NAMES)

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
    "Khẩu âm Tiếng Anh": "Chỉ hiệu quả với tiếng Anh.",
    "Phương ngôn Tiếng Trung": "Chỉ hiệu quả với tiếng Trung.",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="omnivoice-pro",
        description="Launch a Modern Gradio demo for OmniVoice.",
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
    parser.add_argument("--ip", default="127.0.0.1", help="Server IP (default: 127.0.0.1).")
    parser.add_argument(
        "--port", type=int, default=None, help="Server port (default: auto)."
    )
    parser.add_argument(
        "--no-asr",
        action="store_true",
        default=False,
        help="Skip loading Whisper ASR model. Reference text auto-transcription will be unavailable.",
    )
    parser.add_argument(
        "--asr-model",
        default="openai/whisper-large-v3-turbo",
        help="ASR model path or HuggingFace repo id.",
    )
    parser.add_argument(
        "--local-files-only",
        action="store_true",
        default=False,
        help="Only load files from local disk/cache.",
    )
    return parser


def build_demo(model: OmniVoice, checkpoint: str) -> gr.Blocks:
    sampling_rate = model.sampling_rate
    asr_loaded = getattr(model, "asr_model", None) is not None

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
            return None, "⚠️ Vui lòng nhập văn bản cần tạo giọng."

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
                return None, "⚠️ Vui lòng tải lên âm thanh tham chiếu."
            if not asr_loaded and not (ref_text and ref_text.strip()):
                return None, "⚠️ Ban local hien dang tat ASR de tranh treo may va tai them model nang. Muon Clone Giong thi ban phai nhap san loi cua file mau. Neu muon dung ngay khong nhap transcript, tam thoi hay dung tab Thiet Ke Giong."
            kw["voice_clone_prompt"] = model.create_voice_clone_prompt(
                ref_audio=ref_audio,
                ref_text=ref_text,
            )

        if instruct and instruct.strip():
            kw["instruct"] = instruct.strip()

        try:
            audio = model.generate(**kw)
        except Exception as e:
            return None, f"❌ Lỗi: {type(e).__name__}: {e}"

        waveform = (audio[0] * 32767).astype(np.int16)
        return (sampling_rate, waveform), "✅ Hoàn thành xuất sắc!"

    # =====================================================================
    # CUSTOM MODERN THEME & CSS (BMW M Design)
    # =====================================================================
    custom_theme = gr.themes.Monochrome(
        primary_hue="slate",
        secondary_hue="slate",
        neutral_hue="slate",
        radius_size=gr.themes.sizes.radius_none,
        font=[gr.themes.GoogleFont("Inter"), "BMWTypeNextLatin", "ui-sans-serif", "system-ui", "sans-serif"],
    ).set(
        body_background_fill="#000000",
        body_background_fill_dark="#000000",
        block_background_fill="#1a1a1a",
        block_background_fill_dark="#1a1a1a",
        block_border_width="1px",
        block_border_color="#3c3c3c",
        block_border_color_dark="#3c3c3c",
        block_shadow="none",
        button_primary_background_fill="#000000",
        button_primary_background_fill_hover="#1a1a1a",
        button_primary_text_color="#ffffff",
        button_primary_border_color="#ffffff",
        button_primary_border_color_dark="#ffffff",
        slider_color="#1c69d4",
    )

    custom_css = """
    .gradio-container {
        font-family: 'Inter', sans-serif !important;
        max-width: 1440px !important;
        margin: auto !important;
        background-color: #000000 !important;
        color: #ffffff !important;
    }
    
    /* Header styling with M Stripe */
    .app-header {
        text-align: left;
        padding: 4rem 2rem;
        margin-bottom: 2rem;
        background: #000000;
        border-bottom: 4px solid;
        border-image: linear-gradient(to right, #0066b1 33%, #1c69d4 33% 66%, #e22718 66%) 1;
        color: white;
    }
    .app-header h1 {
        color: #ffffff !important;
        font-size: 56px !important;
        font-weight: 700 !important;
        margin-bottom: 0.5rem !important;
        letter-spacing: 0;
        text-transform: uppercase;
    }
    .app-header p {
        font-size: 16px !important;
        font-weight: 300 !important;
        color: #bbbbbb !important;
    }
    
    /* Panel styling */
    .control-panel {
        border: 1px solid #3c3c3c !important;
        border-radius: 0px !important;
        padding: 1.5rem !important;
        background-color: #1a1a1a !important;
        box-shadow: none !important;
    }
    
    /* Primary Button */
    .primary-btn {
        background: #000000 !important;
        color: #ffffff !important;
        border: 1px solid #ffffff !important;
        border-radius: 0px !important;
        font-weight: 700 !important;
        font-size: 14px !important;
        padding: 16px 32px !important;
        text-transform: uppercase !important;
        letter-spacing: 1.5px !important;
        box-shadow: none !important;
        transition: background 0.2s ease !important;
    }
    .primary-btn:hover {
        background: #1a1a1a !important;
    }
    
    /* Textbox focus */
    textarea, input, .dropdown {
        background-color: #1a1a1a !important;
        color: #ffffff !important;
        border: 1px solid #3c3c3c !important;
        border-radius: 0px !important;
    }
    textarea:focus, input:focus {
        border-color: #ffffff !important;
        box-shadow: none !important;
    }
    
    /* Audio player */
    audio {
        border-radius: 0px !important;
        width: 100% !important;
        margin-top: 1rem !important;
        background: #1a1a1a !important;
    }
    
    /* Tabs */
    .tabs {
        border-radius: 0px !important;
        overflow: hidden;
    }
    .tab-nav {
        border-bottom: 1px solid #3c3c3c !important;
        background: #000000 !important;
    }
    .tab-nav button {
        font-weight: 700 !important;
        color: #bbbbbb !important;
        padding: 12px 0 !important;
        margin-right: 2rem !important;
        text-transform: uppercase !important;
        letter-spacing: 1.5px !important;
        border: none !important;
        background: transparent !important;
    }
    .tab-nav button.selected {
        color: #ffffff !important;
        border-bottom: 4px solid !important;
        border-image: linear-gradient(to right, #0066b1 33%, #1c69d4 33% 66%, #e22718 66%) 1 !important;
    }
    """

    def _lang_dropdown(label="Ngôn ngữ (tùy chọn)", value="Tự động"):
        return gr.Dropdown(
            label=label,
            choices=_ALL_LANGUAGES,
            value=value,
            allow_custom_value=False,
            interactive=True,
            info="Để 'Tự động' máy AI sẽ tự nghe và phát hiện ngôn ngữ.",
        )

    def _gen_settings():
        with gr.Accordion("⚙️ Cài đặt Nâng cao (Tùy chọn)", open=False):
            with gr.Row():
                sp = gr.Slider(0.5, 1.5, value=1.0, step=0.05, label="Tốc độ đọc", info="1.0 là bình thường. Lớn hơn 1 là nhanh hơn.")
                du = gr.Number(value=None, label="Thời lượng ép buộc (giây)", info="Để trống để đọc tự nhiên. Điền số nếu muốn ép AI đọc đúng số giây đó.")
            
            with gr.Row():
                ns = gr.Slider(4, 64, value=32, step=1, label="Số bước Inference (Chất lượng)", info="Mặc định: 32. Cao = nét hơn nhưng chậm hơn.")
                gs = gr.Slider(0.0, 4.0, value=2.0, step=0.1, label="Mức độ tuân thủ văn bản (CFG)", info="Mặc định: 2.0.")
            
            with gr.Row():
                dn = gr.Checkbox(label="Khử tiếng ồn (Denoise)", value=True, info="Khuyên dùng: Bật.")
                pp = gr.Checkbox(label="Tiền xử lý âm thanh mẫu", value=True, info="Tự động cắt khoảng lặng của file ghi âm gốc.")
                po = gr.Checkbox(label="Hậu xử lý kết quả", value=True, info="Tự động xóa các đoạn im lặng quá lâu trong file xuất ra.")
        return ns, gs, dn, sp, du, pp, po

    with gr.Blocks(theme=custom_theme, css=custom_css, title="OmniVoice Pro") as demo:
        
        gr.HTML("""
        <div class="app-header">
            <h1>🎙️ OmniVoice Pro</h1>
            <p>Phần mềm giả lập & Thiết kế giọng nói AI Đỉnh cao (Chạy 100% Local Offline)</p>
        </div>
        """)

        with gr.Tabs(elem_classes="tabs"):
            
            # ==============================================================
            # TÍNH NĂNG 1: CLONE GIỌNG (SAO CHÉP GIỌNG BẤT KỲ)
            # ==============================================================
            with gr.TabItem("🎭 Clone Giọng Nói (Sao chép)"):
                with gr.Row():
                    
                    # Cột Nhập liệu
                    with gr.Column(scale=5):
                        with gr.Group(elem_classes="control-panel"):
                            gr.Markdown("### 📝 Nội dung cần đọc")
                            vc_text = gr.Textbox(
                                label="",
                                lines=5,
                                placeholder="Nhập văn bản bạn muốn chuyển thành giọng nói vào đây...\nVí dụ: Xin chào mọi người, hôm nay thời tiết rất đẹp!",
                            )
                            
                        with gr.Group(elem_classes="control-panel"):
                            gr.Markdown("### 🎧 Âm thanh gốc (Giọng mẫu)")
                            gr.Markdown("<span style='color:#64748b; font-size:0.9em;'>Tải lên 1 đoạn ghi âm giọng nói mà bạn muốn AI bắt chước (Nên dài từ 3 đến 10 giây và rõ lời).</span>")
                            vc_ref_audio = gr.Audio(
                                label="",
                                type="filepath",
                            )
                            vc_ref_text = gr.Textbox(
                                label="Lời của đoạn ghi âm mẫu",
                                lines=1,
                                placeholder="Nhap transcript cua file mau de clone giong trong ban local.",
                            )
                            if not asr_loaded:
                                gr.Markdown(
                                    "<span style='color:#f59e0b;font-size:0.92em;'>"
                                    "ASR dang tat trong ban local de tranh tai them Whisper rat nang."
                                    " Muon clone giong thi ban nhap san loi cua audio mau."
                                    "</span>"
                                )
                        
                        with gr.Group(elem_classes="control-panel"):
                            gr.Markdown("### 🌐 Ngôn ngữ & Tùy chỉnh")
                            vc_lang = _lang_dropdown()
                            with gr.Accordion("Hướng dẫn chi tiết cho AI (Không bắt buộc)", open=False):
                                vc_instruct = gr.Textbox(label="VD: Đọc vui vẻ, đọc buồn bã...", lines=1)
                            
                            vc_ns, vc_gs, vc_dn, vc_sp, vc_du, vc_pp, vc_po = _gen_settings()

                    # Cột Kết quả
                    with gr.Column(scale=4):
                        with gr.Group(elem_classes="control-panel"):
                            gr.Markdown("### 🚀 Xuất File")
                            vc_btn = gr.Button("✨ BẮT ĐẦU TẠO GIỌNG", elem_classes="primary-btn")
                            
                            gr.Markdown("---")
                            gr.Markdown("### 🔊 Kết Quả")
                            vc_audio = gr.Audio(
                                label="",
                                type="numpy",
                                interactive=False
                            )
                            vc_status = gr.Textbox(label="Trạng thái hệ thống", lines=1, interactive=False)

                vc_btn.click(
                    fn=lambda text, lang, ref_aud, ref_text, instruct, ns, gs, dn, sp, du, pp, po: _gen_core(
                        text, lang, ref_aud, instruct, ns, gs, dn, sp, du, pp, po, mode="clone", ref_text=ref_text or None
                    ),
                    inputs=[vc_text, vc_lang, vc_ref_audio, vc_ref_text, vc_instruct, vc_ns, vc_gs, vc_dn, vc_sp, vc_du, vc_pp, vc_po],
                    outputs=[vc_audio, vc_status],
                )

            # ==============================================================
            # TÍNH NĂNG 2: THIẾT KẾ GIỌNG ẢO
            # ==============================================================
            with gr.TabItem("🧬 Thiết Kế Giọng (Tạo giọng mới)"):
                with gr.Row():
                    
                    with gr.Column(scale=5):
                        with gr.Group(elem_classes="control-panel"):
                            gr.Markdown("### 📝 Nội dung cần đọc")
                            vd_text = gr.Textbox(
                                label="",
                                lines=5,
                                placeholder="Nhập văn bản cần đọc vào đây...",
                            )
                            
                        with gr.Group(elem_classes="control-panel"):
                            gr.Markdown("### 🎛️ Tùy chỉnh Nhân vật ảo")
                            vd_lang = _lang_dropdown()
                            
                            _AUTO = "Tự động"
                            vd_groups = []
                            
                            with gr.Row():
                                vd_groups.append(gr.Dropdown(label="Giới tính", choices=[_AUTO] + _CATEGORIES["Giới tính"], value=_AUTO))
                                vd_groups.append(gr.Dropdown(label="Độ tuổi", choices=[_AUTO] + _CATEGORIES["Độ tuổi"], value=_AUTO))
                            
                            with gr.Row():
                                vd_groups.append(gr.Dropdown(label="Độ cao giọng", choices=[_AUTO] + _CATEGORIES["Độ cao giọng (Pitch)"], value=_AUTO))
                                vd_groups.append(gr.Dropdown(label="Phong cách", choices=[_AUTO] + _CATEGORIES["Phong cách"], value=_AUTO))
                            
                            with gr.Row():
                                vd_groups.append(gr.Dropdown(label="Khẩu âm Tiếng Anh", choices=[_AUTO] + _CATEGORIES["Khẩu âm Tiếng Anh"], value=_AUTO, info="Chỉ có tác dụng nếu đọc tiếng Anh"))
                                vd_groups.append(gr.Dropdown(label="Tiếng địa phương Trung", choices=[_AUTO] + _CATEGORIES["Phương ngôn Tiếng Trung"], value=_AUTO, info="Chỉ có tác dụng với tiếng Trung"))
                            
                            vd_ns, vd_gs, vd_dn, vd_sp, vd_du, vd_pp, vd_po = _gen_settings()

                    with gr.Column(scale=4):
                        with gr.Group(elem_classes="control-panel"):
                            gr.Markdown("### 🚀 Xuất File")
                            vd_btn = gr.Button("✨ BẮT ĐẦU TẠO GIỌNG", elem_classes="primary-btn")
                            
                            gr.Markdown("---")
                            gr.Markdown("### 🔊 Kết Quả")
                            vd_audio = gr.Audio(
                                label="",
                                type="numpy",
                                interactive=False
                            )
                            vd_status = gr.Textbox(label="Trạng thái hệ thống", lines=1, interactive=False)

                def _build_instruct(groups):
                    selected = [g for g in groups if g and g not in ("Auto", "Tự động")]
                    if not selected:
                        return None
                    return ", ".join([_VI_TO_INSTRUCT.get(v, v) for v in selected])

                vd_btn.click(
                    fn=lambda text, lang, ns, gs, dn, sp, du, pp, po, *groups: _gen_core(
                        text, lang, None, _build_instruct(groups), ns, gs, dn, sp, du, pp, po, mode="design"
                    ),
                    inputs=[vd_text, vd_lang, vd_ns, vd_gs, vd_dn, vd_sp, vd_du, vd_pp, vd_po] + vd_groups,
                    outputs=[vd_audio, vd_status],
                )

    return demo


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
    
    # Load model
    dtype = torch.float16 if device != "cpu" else torch.float32
    model = OmniVoice.from_pretrained(
        checkpoint,
        device_map=device,
        dtype=dtype,
        load_asr=not args.no_asr,
        asr_model_name=args.asr_model,
        local_files_only=args.local_files_only,
    )
    print("Model loaded successfully.")

    # Build and launch Demo
    demo = build_demo(model, checkpoint)
    
    launch_kwargs = {
        "server_name": args.ip,
        "share": False,
        "inbrowser": False,
    }
    if args.port is not None:
        launch_kwargs["server_port"] = args.port

    demo.queue().launch(**launch_kwargs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
