import os
from pathlib import Path
from dotenv import load_dotenv

# Base Directory
BASE_DIR = Path(__file__).resolve().parent

# Load .env file
load_dotenv(BASE_DIR / ".env")

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# Directory Paths
OUTPUT_DIR = BASE_DIR / "output"
IMAGES_DIR = OUTPUT_DIR / "images"
AUDIO_DIR = OUTPUT_DIR / "audio"
VIDEOS_DIR = OUTPUT_DIR / "videos"
PODCASTS_DIR = OUTPUT_DIR / "podcasts"
ASSETS_DIR = BASE_DIR / "assets"

for d in [OUTPUT_DIR, IMAGES_DIR, AUDIO_DIR, VIDEOS_DIR, PODCASTS_DIR, ASSETS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Podcast Voice Personas
PODCAST_HOST_NAME = "Hoài My (Chủ Tọa)"
PODCAST_HOST_VOICE = os.getenv("PODCAST_HOST_VOICE", "vi-VN-HoaiMyNeural")

PODCAST_MASTER_NAME = "Dịch Sư Nam Minh"
PODCAST_MASTER_VOICE = os.getenv("PODCAST_MASTER_VOICE", "vi-VN-NamMinhNeural")

# Default Video & Voice Settings
DEFAULT_VOICE = os.getenv("DEFAULT_VOICE", "vi-VN-NamMinhNeural")
DEFAULT_ASPECT_RATIO = os.getenv("DEFAULT_ASPECT_RATIO", "16:9")  # "16:9" or "9:16"

# Resolution Presets
VIDEO_RESOLUTIONS = {
    "16:9": {"width": 1920, "height": 1080},
    "9:16": {"width": 1080, "height": 1920}
}

VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
VIDEO_FPS = 30

def save_gemini_api_key(key: str):
    """Save or update Gemini API key in .env file."""
    env_path = BASE_DIR / ".env"
    lines = []
    found = False
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("GEMINI_API_KEY="):
                    lines.append(f"GEMINI_API_KEY={key.strip()}\n")
                    found = True
                else:
                    lines.append(line)
    if not found:
        lines.append(f"GEMINI_API_KEY={key.strip()}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    # Update current environment
    os.environ["GEMINI_API_KEY"] = key.strip()
    global GEMINI_API_KEY
    GEMINI_API_KEY = key.strip()
