# -*- coding: utf-8 -*-
"""
Tiện ích gọi nhanh Google Veo 3.1 (Gemini API) trong dự án:
- Sử dụng trực tiếp từ dòng lệnh: python call_veo.py -p "Prompt bối cảnh..."
- Hoặc import vào code Python:
    from call_veo import generate_veo_video
    res = generate_veo_video(prompt="...", aspect_ratio="16:9")
"""
import sys
import os
from pathlib import Path

# Thêm đường dẫn script thực thi của skill call-veo-3.1
SKILL_SCRIPT = Path(__file__).parent / ".agents" / "skills" / "call-veo-3.1" / "scripts" / "invoke-veo-3.1.py"
if not SKILL_SCRIPT.is_file():
    SKILL_SCRIPT = Path.home() / ".gemini" / "config" / "skills" / "call-veo-3.1" / "scripts" / "invoke-veo-3.1.py"

sys.path.insert(0, str(SKILL_SCRIPT.parent))
try:
    from invoke_veo_3_1 import run_veo_generation, main as cli_main
except ImportError:
    # Nếu tên file có dấu gạch ngang
    import importlib.util
    spec = importlib.util.spec_from_file_location("invoke_veo_mod", str(SKILL_SCRIPT))
    invoke_veo_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(invoke_veo_mod)
    run_veo_generation = invoke_veo_mod.run_veo_generation
    cli_main = invoke_veo_mod.main


def generate_veo_video(
    prompt: str = "",
    image_path: str = "",
    output_path: str = "",
    model: str = "veo-3.1-generate-preview",
    aspect_ratio: str = "16:9",
    resolution: str = "720p",
    duration: int = 5,
    fps: int = 24,
    person_generation: str = "dont_allow",
    negative_prompt: str = "",
    enhance_prompt: bool = True,
    fallback_placeholder: bool = False,
    api_key: str = "",
) -> dict:
    """
    Hàm Python gọi trực tiếp tạo video với Veo 3.1.
    Trả về dict: {"ok": bool, "outputPath": str, ...}
    """
    class Args:
        pass

    args = Args()
    args.prompt = prompt
    args.image = image_path
    args.video = ""
    args.last_frame = ""
    args.filename = output_path
    args.model = model
    args.aspect_ratio = aspect_ratio
    args.resolution = resolution
    args.duration = duration
    args.fps = fps
    args.person_generation = person_generation
    args.negative_prompt = negative_prompt
    args.enhance_prompt = enhance_prompt
    args.generate_audio = False
    args.seed = None
    args.timestamp = True if not output_path else False
    args.api_key = api_key
    args.poll_interval = 10
    args.timeout = 600
    args.fallback_placeholder = fallback_placeholder

    return run_veo_generation(args)


if __name__ == "__main__":
    sys.exit(cli_main())
