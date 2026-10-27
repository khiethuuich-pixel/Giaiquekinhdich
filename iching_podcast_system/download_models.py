import os
import urllib.request

model_dir = "c:/Users/Admin/Downloads/Giaiquekinhdich/iching_podcast_system/models"
os.makedirs(model_dir, exist_ok=True)

base_hf = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/vi/vi_VN/vais1000/medium"
files = ["vi_VN-vais1000-medium.onnx", "vi_VN-vais1000-medium.onnx.json"]

for f in files:
    dest = os.path.join(model_dir, f)
    if not os.path.exists(dest) or os.path.getsize(dest) < 1000:
        url = f"{base_hf}/{f}"
        print(f"Downloading {f} from {url}...")
        urllib.request.urlretrieve(url, dest)
        print(f"Saved {f} ({os.path.getsize(dest)} bytes).")
    else:
        print(f"Already exists: {f} ({os.path.getsize(dest)} bytes).")
