"""VoxCPM2 TTS & Voice Cloning (30 languages incl. Vietnamese, Chinese, English; Voice Design, Controllable Cloning, Ultimate Cloning):
    Batch mode (film lines.json -> out_dir/<id>.wav + dur.json):
        python core/tts/tts_voxcpm.py lines.json out_dir [--control "..."] [--ref-wav voice.wav] [--prompt-text "..."] [--cfg 2.0] [--steps 10] [--seed 42]
    Single-file mode:
        python core/tts/tts_voxcpm.py --text "Xin chào!" --control "Warm Vietnamese male narrator" --out demo.wav

lines.json = [
  {
    "id": "vo1",
    "text": "Câu hỏi: Phiên bản này đã được chưa?",
    "say": "...",                  # optional: text actually spoken
    "control": "...",              # optional: Voice Design / style instruction (gender, age, tone, emotion, pace)
    "voice": "vi_male_warm",       # optional: preset name (or edge-tts/Kokoro voice name) mapped to a control description
    "ref_wav": "path/to/ref.wav",  # optional: reference audio for Controllable / Ultimate Voice Cloning
    "prompt_text": "...",          # optional: transcript of ref_wav (enables Ultimate Cloning continuation mode)
    "cfg": 2.0,                    # optional: guidance scale (1.0 - 3.0)
    "steps": 10,                   # optional: LocDiT flow-matching steps
    "seed": 42                     # optional: random seed
  }, ...
]

Backends (--backend auto|space|local|api):
  - auto (default): uses local VoxCPM2 if installed with CUDA/MPS, otherwise uses the official OpenBMB/VoxCPM-Demo cloud GPU Space.
  - space: calls https://openbmb-voxcpm-demo.hf.space (or --space-url) via Gradio HTTP SSE API (zero extra packages needed).
  - local: runs local OpenBMB/VoxCPM (from ./VoxCPM/src or installed `voxcpm` package) on --device (auto/cuda/mps/cpu).
  - api: calls an OpenAI-compatible vLLM-Omni endpoint (--api-url http://localhost:8000/v1/audio/speech).

Voice Consistency (--anchor-first, enabled by default):
  In multi-line Voice Design mode (when no ref_wav is provided), the first synthesized line for each voice/control profile
  is automatically used as the reference_wav for subsequent lines sharing that profile, keeping narrator timbre consistent
  across the entire film. Pass --no-anchor to synthesize each line independently.
"""
import sys, io, os, re, json, time, uuid, hashlib, subprocess, argparse, urllib.request, urllib.error
import wave, numpy as np
try:
    import soundfile as sf
except ImportError:
    class _WaveSF:
        @staticmethod
        def read(file_or_buf, dtype="float32"):
            with wave.open(file_or_buf, "rb") as wf:
                sr = wf.getframerate()
                nch = wf.getnchannels()
                raw = wf.readframes(wf.getnframes())
                arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                if nch > 1:
                    arr = arr.reshape(-1, nch).mean(axis=1)
                return arr, sr
        @staticmethod
        def write(file_or_buf, data, sr, format="WAV"):
            pcm = np.clip(np.asarray(data, dtype=np.float32) * 32767.0, -32768, 32767).astype(np.int16)
            with wave.open(file_or_buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(int(sr))
                wf.writeframes(pcm.tobytes())
    sf = _WaveSF()

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_SR = 24000
DEFAULT_SPACE_URL = os.environ.get("VOXCPM_SPACE_URL", "https://openbmb-voxcpm-demo.hf.space")
DEFAULT_MODEL_ID = os.environ.get("VOXCPM_MODEL_ID", "openbmb/VoxCPM2")
DEFAULT_VI_REF_WAV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_vi_design.wav")

VOICE_PRESETS = {
    # Vietnamese presets (default to test_vi_design.wav reference timbre)
    "test_vi_design": "Deep, calm, resonant Vietnamese male narrator voice, authoritative and philosophical, clear articulation",
    "nam_tram_am": "Deep, calm, resonant Vietnamese male narrator voice, authoritative and philosophical, clear articulation",
    "vi_male": "Deep, calm, resonant Vietnamese male narrator voice, authoritative and philosophical, clear articulation",
    "vi_male_warm": "Deep, calm, resonant Vietnamese male narrator voice, authoritative and philosophical, clear articulation",
    "vi_male_news": "Professional Vietnamese male news anchor, crisp, steady, authoritative and objective tone",
    "vi_female": "Vietnamese female narrator, gentle, clear, warm and expressive voice, natural storytelling pace",
    "vi_female_gentle": "Young Vietnamese woman, soft, warm, sweet and expressive voice, calm pace",
    "vi_A": "Deep, calm, resonant Vietnamese male narrator voice, authoritative and philosophical, clear articulation",
    "vi_B": "Vietnamese female narrator, gentle, clear, warm and expressive voice",
    "vi-VN-NamMinhNeural": "Vietnamese male narrator, warm, clear, resonant baritone voice, steady and natural pace",
    "vi-VN-HoaiMyNeural": "Vietnamese female narrator, gentle, clear, warm and expressive voice, steady pace",
    # Chinese presets
    "zh_male": "成熟稳重的中文男声旁白，声音低沉温暖，吐字清晰，富有叙事感染力",
    "zh_female": "温柔自然的中文女声旁白，声音清澈柔和，语速平稳，富有表现力",
    "zh-CN-YunxiNeural": "阳光清晰的青年中文男声，自然流畅，富有朝气与叙事感",
    "zh-CN-XiaoxiaoNeural": "温柔甜美的年轻中文女声，清晰自然，情感丰富",
    "zh-CN-YunjianNeural": "深沉浑厚的中文纪录片男声旁白，威严沉稳，充满力量感",
    "zf_xiaoxiao": "温柔甜美的年轻中文女声，清晰自然",
    "zm_yunxi": "阳光清晰的青年中文男声，自然流畅",
    # English presets
    "en_male": "Warm, articulate British-American male documentary narrator, deep baritone, measured and engaging tone",
    "en_female": "Clear, warm, expressive female narrator voice, natural pacing and studio quality",
    "bm_george": "Warm British male narrator, measured, scholarly, resonant baritone voice",
    "bm_lewis": "Calm British male documentary voice, clear, crisp and authoritative",
    "am_adam": "Deep American male narrator, warm, grounded and cinematic",
    "af_bella": "Warm, gentle American female voice, clear, natural and expressive",
    "af_heart": "Soft, expressive young female voice, warm and intimate",
}


def resolve_control(L, default_control, default_voice):
    """Build VoxCPM2 control instruction from line fields (`control`, `voice`, `rate`/`speed`)."""
    ctrl = L.get("control")
    if ctrl is None:
        v = L.get("voice") or default_voice
        if v:
            ctrl = VOICE_PRESETS.get(v, v)
        else:
            ctrl = default_control or ""
    ctrl = re.sub(r"[()（）]", "", str(ctrl)).strip()

    # Optional pace hint from rate/speed if not already mentioned
    rate = L.get("rate")
    speed = L.get("speed")
    pace_hint = ""
    if isinstance(rate, str) and re.fullmatch(r"[+-]\d+%", rate.strip()):
        pct = int(rate.strip()[:-1])
        if pct >= 18:
            pace_hint = "brisk, energetic speaking pace"
        elif pct <= -12:
            pace_hint = "slow, deliberate speaking pace"
    elif isinstance(speed, (int, float)):
        if float(speed) >= 1.15:
            pace_hint = "brisk, energetic speaking pace"
        elif float(speed) <= 0.88:
            pace_hint = "slow, deliberate speaking pace"

    if pace_hint and pace_hint not in ctrl.lower():
        ctrl = f"{ctrl}, {pace_hint}" if ctrl else pace_hint
    return ctrl


_VI_DIGITS = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]
_VI_DIACRITIC_RE = re.compile(
    r"[ăâđêôơưáàảãạắằẳẵặấầẩẫậéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]",
    re.IGNORECASE,
)


def _read_three_digits_vi(num: int, show_zero_hundred: bool) -> str:
    h = num // 100
    rem = num % 100
    t = rem // 10
    u = rem % 10
    parts = []
    if h > 0 or show_zero_hundred:
        parts.append(f"{_VI_DIGITS[h]} trăm")
    if t == 0 and u > 0:
        if h > 0 or show_zero_hundred:
            parts.extend(["linh", _VI_DIGITS[u]])
        else:
            parts.append(_VI_DIGITS[u])
    elif t == 1:
        parts.append("mười")
        if u == 5:
            parts.append("lăm")
        elif u > 0:
            parts.append(_VI_DIGITS[u])
    elif t > 1:
        parts.append(f"{_VI_DIGITS[t]} mươi")
        if u == 1:
            parts.append("mốt")
        elif u == 4:
            parts.append("bốn")
        elif u == 5:
            parts.append("lăm")
        elif u > 0:
            parts.append(_VI_DIGITS[u])
    return " ".join(parts)


def number_to_vietnamese_words(n: int) -> str:
    if n < 0:
        return ""
    if n == 0:
        return "không"
    if n >= 1_000_000_000_000:
        return " ".join(_VI_DIGITS[int(d)] for d in str(n))
    units = ["", "nghìn", "triệu", "tỷ"]
    groups = []
    temp = n
    while temp > 0:
        groups.append(temp % 1000)
        temp //= 1000
    parts = []
    for i in range(len(groups) - 1, -1, -1):
        grp = groups[i]
        if grp == 0:
            continue
        show_zero_hundred = i < len(groups) - 1
        grp_words = _read_three_digits_vi(grp, show_zero_hundred)
        unit_label = units[i] if i < len(units) else ""
        parts.append(f"{grp_words} {unit_label}".strip())
    return " ".join(parts)


def convert_numbers_to_vietnamese_words(raw: str) -> str:
    """Convert all Arabic digits (0-9) in Vietnamese text into Vietnamese spoken words so TTS never reads numbers in English."""
    if not raw:
        return ""
    s = str(raw)
    s = re.sub(
        r"\bLá\s*(?:bài\s*)?(?:số\s*)?(\d+)\b",
        lambda m: f"Lá bài số {number_to_vietnamese_words(int(m.group(1)))}",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"\bHào\s*Động\s*(?:thứ\s*|số\s*)?(\d+)\b",
        lambda m: "Hào động thứ nhất"
        if int(m.group(1)) == 1
        else ("Hào động thứ tư" if int(m.group(1)) == 4 else f"Hào động thứ {number_to_vietnamese_words(int(m.group(1)))}"),
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"\bHào\s*(?:số\s*)?(\d+)\b",
        lambda m: f"Hào số {number_to_vietnamese_words(int(m.group(1)))}",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"\bQuẻ\s*(?:số\s*)?#?(\d+)\b",
        lambda m: f"Quẻ số {number_to_vietnamese_words(int(m.group(1)))}",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(r"\b(thứ|Thứ)\s+1\b", r"\1 nhất", s)
    s = re.sub(r"\b(thứ|Thứ)\s+4\b", r"\1 tư", s)
    s = re.sub(
        r"\b(thứ|Thứ)\s+(\d+)\b",
        lambda m: f"{m.group(1)} {number_to_vietnamese_words(int(m.group(2)))}",
        s,
    )
    s = re.sub(
        r"(?:^|(?<=[.!?;\n]))\s*(\d+)\.\s+",
        lambda m: f" {number_to_vietnamese_words(int(m.group(1)))}, ",
        s,
    )
    s = re.sub(
        r"\s+(\d+)\.\s+(?=[A-ZÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬĐÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴ])",
        lambda m: f". {number_to_vietnamese_words(int(m.group(1)))}, ",
        s,
    )
    s = re.sub(
        r"(\d+)[.,](\d+)\s*%",
        lambda m: f"{number_to_vietnamese_words(int(m.group(1)))} phẩy {number_to_vietnamese_words(int(m.group(2)))} phần trăm",
        s,
    )
    s = re.sub(
        r"(\d+)\s*%",
        lambda m: f"{number_to_vietnamese_words(int(m.group(1)))} phần trăm",
        s,
    )
    s = re.sub(
        r"\b(\d+)\s*/\s*(\d+)\b",
        lambda m: f"{number_to_vietnamese_words(int(m.group(1)))} trên {number_to_vietnamese_words(int(m.group(2)))}",
        s,
    )
    s = re.sub(
        r"\b(\d+)\s*[-–—]\s*(\d+)\b",
        lambda m: f"{number_to_vietnamese_words(int(m.group(1)))} đến {number_to_vietnamese_words(int(m.group(2)))}",
        s,
    )
    s = re.sub(
        r"\b(\d+)[.,](\d+)\b",
        lambda m: f"{number_to_vietnamese_words(int(m.group(1)))} phẩy {number_to_vietnamese_words(int(m.group(2)))}",
        s,
    )
    s = re.sub(
        r"\d+",
        lambda m: f" {number_to_vietnamese_words(int(m.group(0)))} ",
        s,
    )
    s = re.sub(r"\s+([,.;:!?])", r"\1", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def decode_to_wav(audio_bytes_or_path, target_sr=DEFAULT_SR):
    """Decode any audio file or bytes (mp3/wav/flac) to mono float32 at target_sr using ffmpeg."""
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    stdin_bytes = None
    if isinstance(audio_bytes_or_path, (bytes, bytearray)):
        cmd += ["-i", "pipe:0"]
        stdin_bytes = bytes(audio_bytes_or_path)
    else:
        cmd += ["-i", str(audio_bytes_or_path)]
    cmd += ["-ar", str(target_sr), "-ac", "1", "-f", "wav", "-"]
    try:
        r = subprocess.run(cmd, input=stdin_bytes, capture_output=True, check=True)
    except FileNotFoundError:
        sys.exit("tts_voxcpm.py: ffmpeg is required on PATH to decode/resample audio")
    except subprocess.CalledProcessError:
        return None
    try:
        a, sr = sf.read(io.BytesIO(r.stdout), dtype="float32")
    except Exception:
        return None
    return (a, sr) if len(a) else None


def plausible(decoded):
    if decoded is None:
        return False
    a, sr = decoded
    return len(a) >= 0.15 * sr and float(np.abs(a).max()) > 1e-3


def trim_silence(y, sr):
    nz = np.where(np.abs(y) > (np.abs(y).max() if len(y) else 0) * 0.02)[0]
    if len(nz):
        return y[max(0, nz[0] - int(0.03 * sr)) : nz[-1] + int(0.10 * sr)]
    return y


# ---------- Backend 1: HuggingFace Space (OpenBMB/VoxCPM-Demo) ----------

class SpaceClient:
    def __init__(self, space_url=DEFAULT_SPACE_URL):
        self.base_url = space_url.rstrip("/")
        self._uploaded_cache = {}  # local_path -> remote FileData dict

    def upload_file(self, filepath):
        abspath = os.path.abspath(filepath)
        if not os.path.exists(abspath):
            raise FileNotFoundError(f"Reference audio not found: {abspath}")
        mtime = os.path.getmtime(abspath)
        cache_key = (abspath, mtime)
        if cache_key in self._uploaded_cache:
            return self._uploaded_cache[cache_key]

        boundary = uuid.uuid4().hex
        filename = os.path.basename(abspath)
        with open(abspath, "rb") as f:
            file_bytes = f.read()
        header = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="files"; filename="{filename}"\r\n'
            f"Content-Type: audio/wav\r\n\r\n"
        ).encode("utf-8")
        footer = f"\r\n--{boundary}--\r\n".encode("utf-8")
        body = header + file_bytes + footer

        req = urllib.request.Request(
            f"{self.base_url}/gradio_api/upload",
            data=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "User-Agent": "VoxCPM-Client/2.0",
            },
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            uploaded_paths = json.loads(resp.read().decode("utf-8"))
        remote_path = uploaded_paths[0]
        file_data = {
            "path": remote_path,
            "orig_name": filename,
            "meta": {"_type": "gradio.FileData"},
        }
        self._uploaded_cache[cache_key] = file_data
        return file_data

    def generate(
        self,
        text,
        control="",
        ref_wav=None,
        prompt_text="",
        cfg=2.0,
        normalize=False,
        denoise=False,
    ):
        ref_data = self.upload_file(ref_wav) if ref_wav else None
        use_prompt_text = bool(ref_wav and prompt_text and prompt_text.strip())
        actual_prompt_text = prompt_text.strip() if use_prompt_text else ""
        actual_control = "" if use_prompt_text else (control or "")

        if _VI_DIACRITIC_RE.search(str(text)) or "vietnamese" in actual_control.lower():
            text = convert_numbers_to_vietnamese_words(str(text))
            normalize = False

        payload = {
            "data": [
                text,
                actual_control,
                ref_data,
                use_prompt_text,
                actual_prompt_text,
                float(cfg),
                bool(normalize),
                bool(denoise),
            ]
        }
        call_url = f"{self.base_url}/gradio_api/call/generate"
        req = urllib.request.Request(
            call_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "VoxCPM-Client/2.0"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            event_id = json.loads(resp.read().decode("utf-8"))["event_id"]

        stream_url = f"{call_url}/{event_id}"
        req_stream = urllib.request.Request(stream_url, headers={"User-Agent": "VoxCPM-Client/2.0"})
        event_type = None
        result_data = None
        with urllib.request.urlopen(req_stream, timeout=180) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                if line.startswith("event:"):
                    event_type = line.split(":", 1)[1].strip()
                elif line.startswith("data:"):
                    data_str = line.split(":", 1)[1].strip()
                    if event_type == "error":
                        raise RuntimeError(f"VoxCPM Space error: {data_str}")
                    if event_type == "complete":
                        result_data = json.loads(data_str)
                        break

        if not result_data or not isinstance(result_data, list) or not result_data[0]:
            raise RuntimeError("VoxCPM Space returned empty result")

        file_info = result_data[0]
        file_url = file_info.get("url")
        if not file_url:
            remote_path = file_info.get("path")
            file_url = f"{self.base_url}/gradio_api/file={remote_path}"

        req_dl = urllib.request.Request(file_url, headers={"User-Agent": "VoxCPM-Client/2.0"})
        with urllib.request.urlopen(req_dl, timeout=60) as resp:
            audio_bytes = resp.read()
        if not audio_bytes:
            raise RuntimeError("Downloaded audio file from VoxCPM Space is empty")
        return audio_bytes


# ---------- Backend 2: Local VoxCPM2 PyTorch Engine ----------

class LocalVoxCPMClient:
    def __init__(self, model_id=DEFAULT_MODEL_ID, device="auto", load_denoiser=False):
        self.model_id = model_id
        self.device = device
        self.load_denoiser = load_denoiser
        self._model = None

    def _get_model(self):
        if self._model is not None:
            return self._model
        # Allow importing from cloned workspace VoxCPM/src if not installed in site-packages
        for candidate in [
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "VoxCPM", "src")),
            r"C:\Users\Admin\Downloads\lamphim\VoxCPM\src",
        ]:
            if os.path.isdir(candidate) and candidate not in sys.path:
                sys.path.insert(0, candidate)
        try:
            from voxcpm import VoxCPM
        except ImportError as e:
            sys.exit(
                f"tts_voxcpm.py: local backend requested but `voxcpm` dependencies are not installed ({e}).\n"
                f"  Either use `--backend space` (cloud GPU, zero install) or install local requirements:\n"
                f"  pip install -e C:/Users/Admin/Downloads/lamphim/VoxCPM"
            )
        optimize = self.device not in ("cpu",)
        self._model = VoxCPM.from_pretrained(
            self.model_id,
            load_denoiser=self.load_denoiser,
            optimize=optimize,
            device=None if self.device == "auto" else self.device,
        )
        return self._model

    def generate(
        self,
        text,
        control="",
        ref_wav=None,
        prompt_text="",
        cfg=2.0,
        steps=10,
        seed=42,
        normalize=False,
        denoise=False,
    ):
        model = self._get_model()
        use_prompt = bool(ref_wav and prompt_text and prompt_text.strip())
        ctrl = "" if use_prompt else re.sub(r"[()（）]", "", control or "").strip()
        final_text = f"({ctrl}){text}" if ctrl else text

        kwargs = dict(
            text=final_text,
            reference_wav_path=ref_wav if ref_wav else None,
            cfg_value=float(cfg),
            inference_timesteps=int(steps),
            normalize=bool(normalize),
            denoise=bool(denoise),
            seed=seed,
        )
        if use_prompt:
            kwargs["prompt_wav_path"] = ref_wav
            kwargs["prompt_text"] = prompt_text.strip()

        wav = model.generate(**kwargs)
        sr = model.tts_model.sample_rate
        buf = io.BytesIO()
        sf.write(buf, wav, sr, format="WAV")
        return buf.getvalue()


# ---------- Backend 3: OpenAI-Compatible API (vLLM-Omni) ----------

class OpenAIAudioClient:
    def __init__(self, api_url="http://localhost:8000/v1/audio/speech", model_id=DEFAULT_MODEL_ID):
        self.api_url = api_url
        self.model_id = model_id

    def generate(self, text, control="", voice="default"):
        ctrl = re.sub(r"[()（）]", "", control or "").strip()
        final_text = f"({ctrl}){text}" if ctrl else text
        payload = {
            "model": self.model_id,
            "input": final_text,
            "voice": voice or "default",
        }
        req = urllib.request.Request(
            self.api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.read()


def detect_backend(requested):
    if requested != "auto":
        return requested
    try:
        import torch
        if torch.cuda.is_available() or (hasattr(torch.backends, "mps") and torch.backends.mps.is_available()):
            import voxcpm  # noqa: F401
            return "local"
    except Exception:
        pass
    return "space"


def synthesize_one(
    client,
    backend,
    text,
    control,
    ref_wav,
    prompt_text,
    cfg,
    steps,
    seed,
    normalize,
    denoise,
):
    if _VI_DIACRITIC_RE.search(str(text)) or "vietnamese" in str(control or "").lower():
        text = convert_numbers_to_vietnamese_words(str(text))
        normalize = False
    last_err = None
    for attempt in range(3):
        try:
            if backend == "space":
                return client.generate(
                    text=text,
                    control=control,
                    ref_wav=ref_wav,
                    prompt_text=prompt_text,
                    cfg=cfg,
                    normalize=normalize,
                    denoise=denoise,
                )
            elif backend == "local":
                return client.generate(
                    text=text,
                    control=control,
                    ref_wav=ref_wav,
                    prompt_text=prompt_text,
                    cfg=cfg,
                    steps=steps,
                    seed=seed,
                    normalize=normalize,
                    denoise=denoise,
                )
            elif backend == "api":
                return client.generate(text=text, control=control)
            else:
                raise ValueError(f"Unknown backend: {backend}")
        except Exception as e:
            last_err = e
            if attempt < 2:
                time.sleep(2.0 * (attempt + 1))
    raise last_err


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lines", nargs="?", help="Path to lines.json (batch mode)")
    ap.add_argument("out_dir", nargs="?", help="Output folder for <id>.wav and dur.json (batch mode)")
    ap.add_argument("--text", help="Single-file mode: text to synthesize")
    ap.add_argument("--out", help="Single-file mode: output .wav path")
    ap.add_argument("--backend", choices=["auto", "space", "local", "api"], default="auto")
    ap.add_argument("--space-url", default=DEFAULT_SPACE_URL, help="Gradio Space URL for --backend space")
    ap.add_argument("--api-url", default="http://localhost:8000/v1/audio/speech", help="Endpoint for --backend api")
    ap.add_argument("--model-id", default=DEFAULT_MODEL_ID, help="Model ID or local path for --backend local/api")
    ap.add_argument("--device", default="auto", help="Device for --backend local (auto, cuda, mps, cpu)")
    ap.add_argument("--voice", default="", help="Preset voice name or control description")
    ap.add_argument("--control", default="", help="Natural language Voice Design / style instruction")
    ap.add_argument("--ref-wav", default=None, help="Reference audio path for Voice Cloning")
    ap.add_argument("--prompt-text", default="", help="Reference transcript for Ultimate Cloning mode")
    ap.add_argument("--cfg", type=float, default=2.0, help="CFG guidance scale (1.0 - 3.0, default 2.0)")
    ap.add_argument("--steps", type=int, default=10, help="LocDiT flow-matching steps (default 10)")
    ap.add_argument("--seed", type=int, default=42, help="Seed for local generation (default 42)")
    ap.add_argument("--normalize", action="store_true", help="Enable wetext text normalization")
    ap.add_argument("--denoise", action="store_true", help="Enable ZipEnhancer reference audio denoising")
    ap.add_argument("--sr", type=int, default=DEFAULT_SR, help="Output WAV sample rate (default 24000; use 48000 for native VoxCPM2)")
    ap.add_argument("--no-anchor", action="store_true", help="Do not reuse the first line's generated voice as reference_wav for subsequent Voice Design lines")
    ap.add_argument("--list-presets", action="store_true", help="List built-in voice preset aliases and exit")
    a = ap.parse_args()

    if a.list_presets:
        for k, v in VOICE_PRESETS.items():
            print(f"{k:22s} -> {v}")
        sys.exit(0)

    backend = detect_backend(a.backend)
    if backend == "space":
        client = SpaceClient(a.space_url)
    elif backend == "local":
        client = LocalVoxCPMClient(a.model_id, device=a.device, load_denoiser=a.denoise)
    else:
        client = OpenAIAudioClient(a.api_url, model_id=a.model_id)

    # Single-file mode
    if a.text:
        if not a.out:
            sys.exit("tts_voxcpm.py: --text requires --out <path.wav>")
        ctrl = resolve_control({}, a.control, a.voice)
        single_ref = a.ref_wav
        v_single = str(a.voice or "").strip().lower()
        if not single_ref and v_single in ("test_vi_design", "nam_tram_am", "vi_male_warm", "vi_male", "vi_a", "vi-vn-namminhneural") and os.path.exists(DEFAULT_VI_REF_WAV):
            single_ref = DEFAULT_VI_REF_WAV
        try:
            raw_audio = synthesize_one(
                client,
                backend,
                text=a.text,
                control=ctrl,
                ref_wav=single_ref,
                prompt_text=a.prompt_text,
                cfg=a.cfg,
                steps=a.steps,
                seed=a.seed,
                normalize=a.normalize,
                denoise=a.denoise,
            )
        except Exception as e:
            print(f"tts_voxcpm.py: synthesis failed ({backend}): {e}", file=sys.stderr)
            sys.exit(2)
        decoded = decode_to_wav(raw_audio, target_sr=a.sr)
        if not plausible(decoded):
            sys.exit("tts_voxcpm.py: generated audio could not be decoded or was silent")
        y, sr = decoded
        y = trim_silence(y, sr)
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        sf.write(a.out, y, sr)
        print(f"{a.out} ({round(len(y) / sr, 3)}s, {sr} Hz)")
        return

    # Batch mode (lines.json -> out_dir)
    if not a.lines or not a.out_dir:
        ap.print_help()
        sys.exit(2)

    lines = json.load(open(a.lines, encoding="utf-8"))
    cache_dir = os.path.join(a.out_dir, ".cache")
    os.makedirs(cache_dir, exist_ok=True)
    for n in os.listdir(cache_dir):
        if n.endswith(".part"):
            os.remove(os.path.join(cache_dir, n))

    dur = {}
    anchor_wavs = {}  # profile_key -> path to first synthesized wav for voice consistency

    for L in lines:
        line_id = L["id"]
        say = L.get("say", L["text"])
        ctrl = resolve_control(L, a.control, a.voice)
        ref_wav = L.get("ref_wav") or a.ref_wav
        v_name = str(L.get("voice") or a.voice or "").strip().lower()
        if not ref_wav and v_name in ("test_vi_design", "nam_tram_am", "vi_male_warm", "vi_male", "vi_a", "vi-vn-namminhneural") and os.path.exists(DEFAULT_VI_REF_WAV):
            ref_wav = DEFAULT_VI_REF_WAV
        prompt_text = L.get("prompt_text") if "prompt_text" in L else a.prompt_text
        cfg = float(L.get("cfg", a.cfg))
        steps = int(L.get("steps", a.steps))
        seed = int(L.get("seed", a.seed))
        norm = bool(L.get("normalize", a.normalize))
        den = bool(L.get("denoise", a.denoise))

        # Voice consistency anchor for Voice Design mode across multiple lines
        base_profile = L.get("control") or L.get("voice") or a.control or a.voice or "default"
        if not ref_wav and not a.no_anchor and base_profile in anchor_wavs:
            ref_wav = anchor_wavs[base_profile]
            prompt_text = ""  # Controllable Cloning mode (preserves speaker timbre while allowing line control)

        ref_sig = ""
        if ref_wav and os.path.exists(ref_wav):
            ref_sig = f"{os.path.abspath(ref_wav)}:{os.path.getmtime(ref_wav):.0f}"

        key_data = [
            "voxcpm2",
            backend,
            ctrl,
            ref_sig,
            prompt_text or "",
            cfg,
            steps,
            seed,
            norm,
            den,
            say,
        ]
        key = hashlib.sha1(json.dumps(key_data, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]
        cached_file = os.path.join(cache_dir, key + ".audio")

        decoded = decode_to_wav(cached_file, target_sr=a.sr) if os.path.exists(cached_file) else None
        if not plausible(decoded):
            decoded = None
        if decoded is None and os.path.exists(cached_file):
            os.remove(cached_file)
            print(f"tts_voxcpm.py: cached audio for line '{line_id}' was damaged; regenerating", file=sys.stderr)

        if decoded is None:
            part = cached_file + ".part"
            try:
                raw_audio = synthesize_one(
                    client,
                    backend,
                    text=say,
                    control=ctrl,
                    ref_wav=ref_wav,
                    prompt_text=prompt_text,
                    cfg=cfg,
                    steps=steps,
                    seed=seed,
                    normalize=norm,
                    denoise=den,
                )
                with open(part, "wb") as f:
                    f.write(raw_audio)
                os.replace(part, cached_file)
            except Exception as e:
                if os.path.exists(part):
                    os.remove(part)
                print(
                    f"tts_voxcpm.py: failed to synthesize line '{line_id}' via VoxCPM ({backend}): {type(e).__name__}: {str(e)[:240]}",
                    file=sys.stderr,
                )
                sys.exit(2)
            decoded = decode_to_wav(cached_file, target_sr=a.sr)
            if not plausible(decoded):
                sys.exit(f"tts_voxcpm.py: audio returned for line '{line_id}' could not be decoded")

        y, sr = decoded
        y = trim_silence(y, sr)
        out_wav = os.path.join(a.out_dir, line_id + ".wav")
        sf.write(out_wav, y, sr)
        dur[line_id] = round(len(y) / sr, 3)
        print(line_id, dur[line_id], L["text"])

        if not (L.get("ref_wav") or a.ref_wav) and not a.no_anchor and base_profile not in anchor_wavs:
            anchor_wavs[base_profile] = out_wav

    json.dump(dur, open(os.path.join(a.out_dir, "dur.json"), "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main()
