import argparse
import os
from pathlib import Path

import torch
from huggingface_hub import snapshot_download


ROOT = Path(__file__).resolve().parent
MODEL_DIR = ROOT / "models" / "OmniVoice"
ASR_DIR = ROOT / "models" / "whisper-large-v3-turbo"
MODEL_REPO = "k2-fsa/OmniVoice"
ASR_REPO = "openai/whisper-large-v3-turbo"


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def download_repo(repo_id: str, target_dir: Path):
    if target_dir.exists() and any(target_dir.iterdir()):
        print(f"Da co san, bo qua: {target_dir}")
        return
    ensure_dir(target_dir)
    print(f"Dang tai model local: {repo_id}")
    snapshot_download(
        repo_id=repo_id,
        local_dir=str(target_dir),
        local_dir_use_symlinks=False,
        resume_download=True,
    )
    print(f"Da xong: {target_dir}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--with-asr", action="store_true", default=False)
    args = parser.parse_args()

    ensure_dir(ROOT / ".cache" / "huggingface")
    ensure_dir(ROOT / ".cache" / "torch")

    os.environ.setdefault("HF_HOME", str(ROOT / ".cache" / "huggingface"))
    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(ROOT / ".cache" / "huggingface" / "hub"))
    os.environ.setdefault("TRANSFORMERS_CACHE", str(ROOT / ".cache" / "huggingface" / "transformers"))
    os.environ.setdefault("TORCH_HOME", str(ROOT / ".cache" / "torch"))
    os.environ["HF_HUB_OFFLINE"] = "0"
    os.environ["TRANSFORMERS_OFFLINE"] = "0"

    download_repo(MODEL_REPO, MODEL_DIR)
    if args.with_asr:
        download_repo(ASR_REPO, ASR_DIR)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"San sang. Model local da nam trong thu muc models/. Thiet bi hien tai: {device}")


if __name__ == "__main__":
    main()
