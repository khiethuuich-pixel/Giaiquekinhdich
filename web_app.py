import os
import sys
import threading
from pathlib import Path
from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Silence Windows Proactor connection reset error on browser video range/seek requests
if sys.platform == 'win32':
    try:
        from functools import wraps
        from asyncio.proactor_events import _ProactorBasePipeTransport
        _orig_call_connection_lost = _ProactorBasePipeTransport._call_connection_lost

        @wraps(_orig_call_connection_lost)
        def _silent_connection_lost(self, exc):
            try:
                return _orig_call_connection_lost(self, exc)
            except (ConnectionResetError, OSError):
                pass

        _ProactorBasePipeTransport._call_connection_lost = _silent_connection_lost
    except Exception:
        pass

from config import (
    BASE_DIR, OUTPUT_DIR, IMAGES_DIR, AUDIO_DIR, VIDEOS_DIR, PODCASTS_DIR,
    GEMINI_API_KEY, save_gemini_api_key, DEFAULT_ASPECT_RATIO, DEFAULT_VOICE,
    PODCAST_HOST_NAME, PODCAST_MASTER_NAME, DEEPSEEK_API_KEY
)
from pipeline_direct import run_direct_pipeline
from pipeline_direct_full import run_direct_full_pipeline
from pipeline_podcast import run_podcast_pipeline
from crawler import cast_and_collect

app = FastAPI(title="Cửu Nhị · Hệ Thống Luận Giải Kinh Dịch & Studio Podcast")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_private_network=True,
)

# Mount media directories
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
if (BASE_DIR / "static" / "images" / "dragon").exists():
    app.mount("/images/dragon", StaticFiles(directory=str(BASE_DIR / "static" / "images" / "dragon")), name="dragon_images")
if (BASE_DIR / "static" / "videos").exists():
    app.mount("/videos", StaticFiles(directory=str(BASE_DIR / "static" / "videos")), name="dragon_videos")
app.mount("/media/videos", StaticFiles(directory=str(VIDEOS_DIR)), name="videos")
app.mount("/media/podcasts", StaticFiles(directory=str(PODCASTS_DIR)), name="podcasts")
app.mount("/media/audio", StaticFiles(directory=str(AUDIO_DIR)), name="audio")
app.mount("/media/images", StaticFiles(directory=str(IMAGES_DIR)), name="images")

import time

# ==========================================
# INDEPENDENT STATE TRACKERS & SMART ETA ENGINE
# ==========================================

STAGE_CEILINGS = {
    "init": 16,
    "crawler": 33,
    "gemini": 58,
    "sage": 62,
    "voice": 78,
    "audio": 82,
    "video": 98,
    "done": 100
}

def format_eta_vi(seconds: float) -> str:
    sec = max(0, int(round(seconds)))
    if sec <= 0:
        return "Đã hoàn tất"
    if sec < 60:
        return f"~{sec} giây"
    m = sec // 60
    s = sec % 60
    return f"~{m} phút {s:02d} giây" if s > 0 else f"~{m} phút"

def create_empty_job(default_msg: str) -> dict:
    return {
        "job_id": "",
        "status": "idle",
        "percent": 0,
        "base_percent": 0,
        "stage": "",
        "message": default_msg,
        "started_at": 0.0,
        "stage_started_at": 0.0,
        "elapsed_seconds": 0.0,
        "estimated_total_seconds": 60.0,
        "eta_remaining_seconds": 0,
        "eta_text": "",
        "num_cards": 0,
        "audio_duration": 0.0,
        "result": None,
        "error": None
    }

def start_job_tracker(job: dict, init_msg: str, initial_eta: float = 65.0):
    now = time.time()
    job["job_id"] = f"job_{int(now * 1000)}"
    job["status"] = "running"
    job["percent"] = 5
    job["base_percent"] = 5
    job["stage"] = "init"
    job["message"] = init_msg
    job["started_at"] = now
    job["stage_started_at"] = now
    job["elapsed_seconds"] = 0.0
    job["estimated_total_seconds"] = float(initial_eta)
    job["eta_remaining_seconds"] = int(round(initial_eta))
    job["eta_text"] = format_eta_vi(initial_eta)
    job["num_cards"] = 0
    job["audio_duration"] = 0.0
    job["result"] = None
    job["error"] = None

def update_job_tracker(job: dict, p: dict):
    now = time.time()
    new_stage = p.get("stage", job["stage"])
    if new_stage != job["stage"]:
        job["stage_started_at"] = now
    job["stage"] = new_stage
    job["base_percent"] = int(p.get("percent", job["percent"]))
    job["percent"] = max(job["percent"], job["base_percent"])
    job["message"] = p.get("message", job["message"])

    elapsed = max(0.1, now - (job.get("started_at") or now))
    job["elapsed_seconds"] = round(elapsed, 1)

    if "num_cards" in p and p["num_cards"]:
        job["num_cards"] = int(p["num_cards"])
    if "audio_duration" in p and p["audio_duration"]:
        job["audio_duration"] = float(p["audio_duration"])

    if "eta_remaining" in p and p["eta_remaining"] is not None:
        rem = max(0.0, float(p["eta_remaining"]))
        job["estimated_total_seconds"] = round(elapsed + rem, 1)
        job["eta_remaining_seconds"] = int(round(rem))
        job["eta_text"] = format_eta_vi(rem)

def compute_live_job_view(job: dict) -> dict:
    view = dict(job)
    if view.get("status") == "running" and view.get("started_at", 0) > 0:
        now = time.time()
        elapsed = max(0.1, now - view["started_at"])
        view["elapsed_seconds"] = round(elapsed, 1)

        est_total = float(view.get("estimated_total_seconds") or 65.0)
        # Adaptive cushion if FFmpeg or Gemini takes slightly longer than initially predicted
        if elapsed >= est_total - 3.0:
            est_total = elapsed + 5.0
            job["estimated_total_seconds"] = round(est_total, 1)

        rem = max(2, int(round(est_total - elapsed)))
        view["eta_remaining_seconds"] = rem
        view["estimated_total_seconds"] = round(est_total, 1)
        view["eta_text"] = format_eta_vi(rem)

        # Smoothly interpolate percentage within current stage ceiling
        stage = view.get("stage", "init")
        ceiling = STAGE_CEILINGS.get(stage, 96)
        base_pct = int(view.get("base_percent") or view.get("percent") or 5)
        stage_spent = max(0.0, now - (view.get("stage_started_at") or view["started_at"]))
        # Gradually approach stage ceiling using exponential decay over ~22 seconds
        span = max(0, ceiling - base_pct)
        bonus = int(round(span * (1.0 - (2.71828 ** (-stage_spent / 18.0)))))
        smooth_pct = min(ceiling, max(int(view.get("percent", 5)), base_pct + bonus))
        job["percent"] = smooth_pct
        view["percent"] = smooth_pct
    elif view.get("status") == "completed":
        view["percent"] = 100
        view["eta_remaining_seconds"] = 0
        view["eta_text"] = "Đã hoàn tất"
    return view

# 1. Bảng Cũ (Luận Giải Trực Tiếp & Video Dọc 9:16)
DIRECT_JOB = create_empty_job("Bảng cũ sẵn sàng.")

# 2. Bảng Mới (Podcast Đàm Đạo & Video MP4 Full HD)
PODCAST_JOB = create_empty_job("Bảng mới sẵn sàng.")

# 3. Bảng Luận & Ghi Âm Full Phân Tích (Copy Hết Nội Dung Gemini Phân Tích Để Ghi Âm Ra Video 9:16)
DIRECT_FULL_JOB = create_empty_job("Bảng Luận & Ghi Âm Full Phân Tích sẵn sàng.")

# Request Models
class DirectRequest(BaseModel):
    question: str
    api_key: str = ""
    layout: str = "random"
    voice: str = DEFAULT_VOICE

class DirectFullRequest(BaseModel):
    question: str
    api_key: str = ""
    layout: str = "random"
    voice: str = DEFAULT_VOICE
    custom_analysis_text: str = ""
    existing_image_path: str = ""
    existing_hexagram_text: str = ""

class DirectHomeRequest(BaseModel):
    question: str = ""
    api_key: str = ""
    voice: str = DEFAULT_VOICE
    image_base64: str = ""
    card_images_base64: list[str] = []
    hexagram_text: str = ""
    custom_analysis_text: str = ""
    cards_order_version: int = 1

class CrawlOnlyRequest(BaseModel):
    question: str = ""
    layout: str = "random"

class PodcastRequest(BaseModel):
    question: str
    api_key: str = ""
    layout: str = "random"
    aspect_ratio: str = "16:9"
    duration_mode: str = "deep"
    voice: str = "duet_standard"

class SaveKeyRequest(BaseModel):
    api_key: str

class DragonAgentChatRequest(BaseModel):
    user_message: str
    main_question: str = ""
    hexagram_text: str = ""
    full_interpretation: str = ""
    history: list[dict] = []
    with_voice: bool = True
    voice: str = DEFAULT_VOICE
    api_key: str = ""

class InkWashInterpretRequest(BaseModel):
    question: str = ""
    hexagram_text: str = ""
    num_cards: int = 4
    api_key: str = ""
    skip_summary: bool = False

# ==========================================
# HTML ROUTING
# ==========================================

@app.get("/", response_class=HTMLResponse)
async def serve_home():
    """Default entrypoint serves the new Podcast Board."""
    html_path = BASE_DIR / "templates" / "podcast.html"
    if html_path.exists():
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return RedirectResponse(url="/podcast")

@app.get("/podcast", response_class=HTMLResponse)
async def serve_podcast_board():
    """BẢNG MỚI: Studio Podcast Đàm Đạo & Video MP4 Full HD."""
    html_path = BASE_DIR / "templates" / "podcast.html"
    if html_path.exists():
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Bảng Podcast chưa sẵn sàng.</h1>")

@app.get("/direct", response_class=HTMLResponse)
async def serve_direct_board():
    """BẢNG CŨ: Luận Giải Trực Tiếp & Video Dọc 9:16 TikTok/Shorts."""
    html_path = BASE_DIR / "templates" / "direct.html"
    if html_path.exists():
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Bảng cũ chưa sẵn sàng.</h1>")

@app.get("/direct-full", response_class=HTMLResponse)
@app.get("/full", response_class=HTMLResponse)
async def serve_direct_full_board():
    """BẢNG THỨ 3: Luận Trực Tiếp · Copy Hết Nội Dung Gemini Phân Tích Để Ghi Âm Ra Video 9:16."""
    html_path = BASE_DIR / "templates" / "direct_full.html"
    if html_path.exists():
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Bảng Luận & Ghi Âm Full Phân Tích chưa sẵn sàng.</h1>")

# ==========================================
# CONFIG & KEY APIS
# ==========================================

@app.get("/api/config")
async def get_config():
    masked_key = ""
    if GEMINI_API_KEY:
        masked_key = GEMINI_API_KEY[:4] + "..." + GEMINI_API_KEY[-4:] if len(GEMINI_API_KEY) > 8 else "***"
    return {
        "has_api_key": bool(GEMINI_API_KEY or DEEPSEEK_API_KEY),
        "has_gemini_key": bool(GEMINI_API_KEY),
        "has_deepseek_key": bool(DEEPSEEK_API_KEY),
        "masked_key": masked_key,
        "default_voice": DEFAULT_VOICE,
        "default_aspect_ratio": DEFAULT_ASPECT_RATIO,
        "host_name": PODCAST_HOST_NAME,
        "master_name": PODCAST_MASTER_NAME
    }

@app.post("/api/save_key")
async def api_save_key(req: SaveKeyRequest):
    if req.api_key.strip():
        save_gemini_api_key(req.api_key.strip())
        return {"success": True, "message": "Đã lưu Gemini API Key vào .env thành công!"}
    return {"success": False, "message": "API Key không hợp lệ."}

def _transcribe_audio_bytes_sync(raw_audio: bytes) -> dict:
    """Synchronous worker: convert recorded audio via FFmpeg (normalized + raw) and transcribe to Vietnamese."""
    import subprocess
    import time
    import speech_recognition as sr

    ts = f"{int(time.time() * 1000)}_{threading.get_ident()}"
    temp_input = AUDIO_DIR / f"mic_{ts}.webm"
    temp_wav_norm = AUDIO_DIR / f"mic_{ts}_norm.wav"
    temp_wav_raw = AUDIO_DIR / f"mic_{ts}_raw.wav"

    try:
        with open(temp_input, "wb") as f:
            f.write(raw_audio)

        # Pass 1 WAV: 16kHz mono PCM with voice bandpass + dynamic audio normalization (boosts quiet mics)
        cmd_norm = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(temp_input),
            "-vn", "-acodec", "pcm_s16le",
            "-ar", "16000", "-ac", "1",
            "-af", "highpass=f=80,lowpass=f=7500,dynaudnorm=f=150:g=15",
            str(temp_wav_norm)
        ]
        subprocess.run(cmd_norm, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)

        # Pass 2 WAV: 16kHz mono PCM raw
        cmd_raw = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(temp_input),
            "-vn", "-acodec", "pcm_s16le",
            "-ar", "16000", "-ac", "1",
            str(temp_wav_raw)
        ]
        res_raw = subprocess.run(cmd_raw, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)

        if not temp_wav_norm.exists() and (res_raw.returncode != 0 or not temp_wav_raw.exists()):
            return {"success": False, "status_code": 500, "error": "Lỗi chuyển đổi tệp âm thanh ghi âm (FFmpeg)."}

        r = sr.Recognizer()
        r.dynamic_energy_threshold = True

        # Try normalized WAV first, then raw WAV with Google Speech Recognition
        for wav_candidate in (temp_wav_norm, temp_wav_raw):
            if not wav_candidate.exists() or wav_candidate.stat().st_size < 200:
                continue
            try:
                with sr.AudioFile(str(wav_candidate)) as source:
                    audio_data = r.record(source)
                text = r.recognize_google(audio_data, language="vi-VN")
                if text and text.strip():
                    return {"success": True, "text": text.strip()}
            except sr.UnknownValueError:
                continue
            except Exception as e:
                print(f"[Transcribe] Google STT warning on {wav_candidate.name}: {e}")

        # Pass 3 Fallback: Gemini Multimodal Audio transcription if API key is available
        if GEMINI_API_KEY:
            wav_for_gemini = temp_wav_norm if temp_wav_norm.exists() else temp_wav_raw
            if wav_for_gemini.exists() and wav_for_gemini.stat().st_size > 200:
                try:
                    from google import genai
                    from google.genai import types
                    client = genai.Client(api_key=GEMINI_API_KEY)
                    wav_bytes = wav_for_gemini.read_bytes()
                    for model_name in ("gemini-flash-lite-latest", "gemini-flash-latest"):
                        try:
                            resp = client.models.generate_content(
                                model=model_name,
                                contents=[
                                    types.Part.from_bytes(data=wav_bytes, mime_type="audio/wav"),
                                    (
                                        "Hãy nghe đoạn ghi âm tiếng Việt này và chép lại chính xác câu hỏi của người nói "
                                        "thành văn bản tiếng Việt. Chỉ trả về đúng câu nói đã nghe được, không giải thích thêm. "
                                        "Nếu hoàn toàn không có tiếng người nói thì trả về chuỗi rỗng."
                                    )
                                ]
                            )
                            if resp and resp.text and resp.text.strip():
                                cleaned = resp.text.strip().strip('"').strip("'").strip()
                                if cleaned and len(cleaned) > 1:
                                    return {"success": True, "text": cleaned}
                        except Exception:
                            continue
                except Exception as ge:
                    print(f"[Transcribe] Gemini audio fallback warning: {ge}")

        return {
            "success": False,
            "status_code": 422,
            "error": "Không nghe rõ câu hỏi trong bản ghi âm. Vui lòng nói rõ vào micro rồi bấm lại nút mic."
        }
    except Exception as e:
        return {
            "success": False,
            "status_code": 500,
            "error": f"Không thể nhận diện giọng nói: {str(e) or 'Lỗi xử lý âm thanh'}"
        }
    finally:
        for p in (temp_input, temp_wav_norm, temp_wav_raw):
            try:
                if p.exists():
                    p.unlink()
            except Exception:
                pass


@app.post("/api/transcribe")
async def api_transcribe_audio(request: Request):
    """Transcribe voice audio (raw binary or JSON base64) to Vietnamese text."""
    import asyncio
    import base64
    import json
    try:
        raw_body = await request.body()
        if not raw_body:
            return JSONResponse(status_code=400, content={"success": False, "error": "Dữ liệu âm thanh trống."})

        content_type = (request.headers.get("content-type") or "").lower()
        audio_bytes = raw_body

        if "application/json" in content_type or (raw_body[:1] == b"{" and b"audio_base64" in raw_body[:64]):
            try:
                payload = json.loads(raw_body.decode("utf-8"))
                b64_str = payload.get("audio_base64") or ""
                if "," in b64_str:
                    b64_str = b64_str.split(",", 1)[1]
                audio_bytes = base64.b64decode(b64_str)
            except Exception as je:
                return JSONResponse(status_code=400, content={"success": False, "error": f"Dữ liệu JSON âm thanh không hợp lệ: {je}"})

        if not audio_bytes or len(audio_bytes) < 100:
            return JSONResponse(status_code=400, content={"success": False, "error": "Bản ghi âm quá ngắn. Hãy nói câu hỏi dài hơn 1 giây rồi bấm dừng."})

        result = await asyncio.to_thread(_transcribe_audio_bytes_sync, audio_bytes)
        if result.get("success"):
            return {"success": True, "text": result["text"]}
        return JSONResponse(
            status_code=result.get("status_code", 500),
            content={"success": False, "error": result.get("error", "Không nhận diện được giọng nói.")}
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": f"Không thể nhận diện giọng nói: {str(e) or 'Lỗi hệ thống'}"})

# ==========================================
# 1. APIS DÀNH CHO BẢNG CŨ (LUẬN TRỰC TIẾP 9:16)
# ==========================================

@app.get("/api/direct/status")
async def get_direct_status():
    return compute_live_job_view(DIRECT_JOB)

def execute_direct_task(question: str, api_key: str, layout: str, voice: str):
    global DIRECT_JOB
    start_job_tracker(DIRECT_JOB, "Đang khởi tạo bốc quẻ trực tiếp...", initial_eta=48.0)

    def update_p(p):
        update_job_tracker(DIRECT_JOB, p)

    try:
        res = run_direct_pipeline(
            question=question,
            api_key=api_key or None,
            layout=layout,
            voice=voice,
            progress_callback=update_p
        )
        DIRECT_JOB["status"] = "completed"
        DIRECT_JOB["percent"] = 100
        DIRECT_JOB["base_percent"] = 100
        DIRECT_JOB["stage"] = "done"
        DIRECT_JOB["eta_remaining_seconds"] = 0
        DIRECT_JOB["eta_text"] = "Đã hoàn tất"
        DIRECT_JOB["elapsed_seconds"] = round(res.get("total_time", time.time() - DIRECT_JOB["started_at"]), 1)
        DIRECT_JOB["message"] = "Hoàn tất! Video dọc 9:16 đã sẵn sàng."
        DIRECT_JOB["result"] = {
            "question": res["question"],
            "hexagram_title": res["hexagram_title"],
            "hook": res["hook"],
            "summary_advice": res["summary_advice"],
            "full_interpretation": res["full_interpretation"],
            "video_script": res["video_script"],
            "video_url": f"/media/videos/{res['video_filename']}",
            "image_url": f"/media/images/{Path(res['card_image_path']).name}",
            "duration": round(res["duration"], 1),
            "total_time": round(res.get("total_time", DIRECT_JOB["elapsed_seconds"]), 1)
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        DIRECT_JOB["status"] = "error"
        DIRECT_JOB["percent"] = 0
        DIRECT_JOB["stage"] = "error"
        DIRECT_JOB["message"] = f"Lỗi bảng cũ: {str(e)}"
        DIRECT_JOB["error"] = str(e)

@app.post("/api/direct/run")
async def api_direct_run(req: DirectRequest, background_tasks: BackgroundTasks):
    global DIRECT_JOB
    if DIRECT_JOB["status"] == "running" and (time.time() - DIRECT_JOB.get("started_at", 0)) < 180:
        return JSONResponse(status_code=400, content={"error": "Bảng cũ đang thực hiện một quẻ khác. Vui lòng chờ."})

    background_tasks.add_task(
        execute_direct_task,
        req.question,
        req.api_key,
        req.layout,
        req.voice
    )
    return {"status": "started", "message": "Tiến trình luận giải trực tiếp đã kích hoạt."}

# ==========================================
# 1B. APIS DÀNH CHO BẢNG LUẬN & GHI ÂM FULL PHÂN TÍCH (9:16)
# ==========================================

@app.get("/api/direct_full/status")
async def get_direct_full_status():
    return compute_live_job_view(DIRECT_FULL_JOB)

@app.post("/api/direct_full/crawl")
def api_direct_full_crawl(req: CrawlOnlyRequest):
    """Chỉ bốc quẻ trên ichingtarot.com, tải ảnh thẻ bài và lấy nội dung 'Chép Cho AI'."""
    try:
        crawl_res = cast_and_collect(layout=req.layout, headless=True)
        if not crawl_res.get("success"):
            return JSONResponse(status_code=500, content={"success": False, "error": crawl_res.get("error", "Lỗi khi bốc quẻ.")})
        img_path = crawl_res["image_path"]
        hex_text = crawl_res["hexagram_text"]
        q = req.question.strip()
        if q:
            prompt_for_ai = f"CÂU HỎI CỦA NGƯỜI CHIÊM BỐC: {q}\n\n{hex_text}"
        else:
            prompt_for_ai = hex_text
        return {
            "success": True,
            "image_path": img_path,
            "image_url": f"/media/images/{Path(img_path).name}",
            "hexagram_text": hex_text,
            "prompt_for_ai": prompt_for_ai
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

def execute_direct_full_task(
    question: str,
    api_key: str,
    layout: str,
    voice: str,
    custom_analysis_text: str,
    existing_image_path: str,
    existing_hexagram_text: str,
    ordered_card_paths: list[str] = None
):
    global DIRECT_FULL_JOB
    n_cards_hint = len(ordered_card_paths) if ordered_card_paths else 3
    init_eta = (1.5 if existing_image_path else 10.0) + (1.0 if (custom_analysis_text and custom_analysis_text.strip()) else (10.0 + 1.5 * n_cards_hint)) + (6.0 + 1.5 * n_cards_hint) + (12.0 + 2.5 * n_cards_hint)
    start_job_tracker(DIRECT_FULL_JOB, "Đang khởi tạo tiến trình Luận Giải & Thuyết Minh Tinh Gọn...", initial_eta=init_eta)
    DIRECT_FULL_JOB["num_cards"] = n_cards_hint

    def update_p(p):
        update_job_tracker(DIRECT_FULL_JOB, p)

    try:
        res = run_direct_full_pipeline(
            question=question,
            api_key=api_key or None,
            layout=layout,
            voice=voice,
            custom_analysis_text=custom_analysis_text or None,
            existing_image_path=existing_image_path or None,
            existing_hexagram_text=existing_hexagram_text or None,
            ordered_card_paths=ordered_card_paths or None,
            progress_callback=update_p
        )
        DIRECT_FULL_JOB["status"] = "completed"
        DIRECT_FULL_JOB["percent"] = 100
        DIRECT_FULL_JOB["base_percent"] = 100
        DIRECT_FULL_JOB["stage"] = "done"
        DIRECT_FULL_JOB["eta_remaining_seconds"] = 0
        DIRECT_FULL_JOB["eta_text"] = "Đã hoàn tất"
        DIRECT_FULL_JOB["elapsed_seconds"] = round(res.get("total_time", time.time() - DIRECT_FULL_JOB["started_at"]), 1)
        DIRECT_FULL_JOB["message"] = f"Hoàn tất! Đã ghi âm kịch bản thuyết minh tinh gọn ({round(res['duration'], 1)}s) và xuất Video 9:16."
        DIRECT_FULL_JOB["result"] = {
            "question": res["question"],
            "hexagram_title": res["hexagram_title"],
            "hook": res["hook"],
            "summary_advice": res["summary_advice"],
            "hexagram_raw_ai_text": res.get("hexagram_raw_ai_text", ""),
            "full_interpretation": res["full_interpretation"],
            "video_script": res["video_script"],
            "card_image_path": res["card_image_path"],
            "audio_url": f"/media/audio/{res['audio_filename']}",
            "video_url": f"/media/videos/{res['video_filename']}",
            "image_url": f"/media/images/{Path(res['card_image_path']).name}",
            "duration": round(res["duration"], 1),
            "total_time": round(res.get("total_time", DIRECT_FULL_JOB["elapsed_seconds"]), 1)
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        DIRECT_FULL_JOB["status"] = "error"
        DIRECT_FULL_JOB["percent"] = 0
        DIRECT_FULL_JOB["stage"] = "error"
        DIRECT_FULL_JOB["message"] = f"Lỗi: {str(e)}"
        DIRECT_FULL_JOB["error"] = str(e)

@app.post("/api/direct_full/run")
async def api_direct_full_run(req: DirectFullRequest, background_tasks: BackgroundTasks):
    global DIRECT_FULL_JOB
    if DIRECT_FULL_JOB["status"] == "running" and (time.time() - DIRECT_FULL_JOB.get("started_at", 0)) < 180:
        return JSONResponse(status_code=400, content={"error": "Bảng Luận & Ghi Âm Full Phân Tích đang xử lý một quẻ khác. Vui lòng chờ."})

    background_tasks.add_task(
        execute_direct_full_task,
        req.question,
        req.api_key,
        req.layout,
        req.voice,
        req.custom_analysis_text,
        req.existing_image_path,
        req.existing_hexagram_text
    )
    return {"status": "started", "message": "Tiến trình Ghi Âm Full Nội Dung Phân Tích & Xuất Video đã kích hoạt."}

# ==========================================
# 1C. APIS TÍCH HỢP TRỰC TIẾP TRANG CHỦ ICHINGTAROT2 (LẤY HÌNH CHỤP & CHÉP CHO AI TRỰC TIẾP TỪ TRANG CHỦ)
# ==========================================

@app.get("/api/direct_home/status")
async def get_direct_home_status():
    return compute_live_job_view(DIRECT_FULL_JOB)

@app.post("/api/direct_home/run")
async def api_direct_home_run(req: DirectHomeRequest, background_tasks: BackgroundTasks):
    """Nhận trực tiếp ảnh chụp thẻ bài (image_base64) và nội dung 'Chép cho AI' (hexagram_text) đang hiển thị trên Trang Chủ ichingtarot2."""
    global DIRECT_FULL_JOB
    import base64
    from datetime import datetime

    if DIRECT_FULL_JOB["status"] == "running" and (time.time() - DIRECT_FULL_JOB.get("started_at", 0)) < 180:
        return JSONResponse(status_code=400, content={"error": "Hệ thống đang xử lý một quẻ khác. Vui lòng chờ giây lát."})

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    saved_image_path = ""
    if req.image_base64 and len(req.image_base64) > 100:
        try:
            b64_str = req.image_base64
            if "," in b64_str:
                b64_str = b64_str.split(",", 1)[1]
            raw_bytes = base64.b64decode(b64_str)
            out_img = IMAGES_DIR / f"home_que_{ts}.png"
            with open(out_img, "wb") as f:
                f.write(raw_bytes)
            saved_image_path = str(out_img)
        except Exception as e:
            print(f"[DirectHome] Lỗi giải mã ảnh từ trang chủ: {e}")

    saved_card_paths = []
    if req.card_images_base64:
        for idx, c_b64 in enumerate(req.card_images_base64):
            if not c_b64 or len(c_b64) < 100:
                continue
            try:
                cb = c_b64.split(",", 1)[1] if "," in c_b64 else c_b64
                c_bytes = base64.b64decode(cb)
                c_out = IMAGES_DIR / f"home_que_{ts}_card_{idx+1}.png"
                with open(c_out, "wb") as f:
                    f.write(c_bytes)
                saved_card_paths.append(str(c_out))
            except Exception as e:
                print(f"[DirectHome] Lỗi giải mã lá bài {idx+1}: {e}")

    # Nếu tab trình duyệt cũ gửi mảng Tháp La theo thứ tự [Quẻ Chủ, Quẻ Biến, Hào 1..K] (version < 2),
    # tự động chuẩn hóa về thứ tự đọc [Quẻ Chủ, Hào 1..K, Quẻ Biến] để khớp 100% với giọng đọc!
    if (
        len(saved_card_paths) > 2
        and getattr(req, "cards_order_version", 1) < 2
        and "THÁP LA" in (req.hexagram_text or "").upper()
    ):
        saved_card_paths = [saved_card_paths[0]] + saved_card_paths[2:] + [saved_card_paths[1]]

    question_text = (req.question or "").strip() or "Xin quẻ Kinh Dịch chỉ dẫn thời vận và định hướng hành động tối ưu"
    n_cards_hint = len(saved_card_paths) if saved_card_paths else 3
    est_eta = 1.5 + (1.0 if (req.custom_analysis_text and req.custom_analysis_text.strip()) else (10.0 + 1.5 * n_cards_hint)) + (6.0 + 1.5 * n_cards_hint) + (12.0 + 2.5 * n_cards_hint)

    background_tasks.add_task(
        execute_direct_full_task,
        question_text,
        req.api_key,
        "random",
        req.voice or DEFAULT_VOICE,
        req.custom_analysis_text,
        saved_image_path,
        req.hexagram_text,
        saved_card_paths
    )
    return {
        "status": "started",
        "estimated_total_seconds": round(est_eta, 1),
        "eta_text": format_eta_vi(est_eta),
        "saved_image_url": f"/media/images/{Path(saved_image_path).name}" if saved_image_path else "",
        "message": f"Đã chụp xong thẻ bài! Tiến trình đang chạy ngầm (Dự kiến hoàn tất trong {format_eta_vi(est_eta)})..."
    }

@app.post("/api/ink_wash/ai_interpret")
async def api_ink_wash_ai_interpret(req: InkWashInterpretRequest):
    """
    Nhận văn bản 'Chép Toàn Bộ Cho AI' từ trang chủ / Tháp La, đưa vào AI Gemini giải quẻ toàn diện,
    sau đó trả về cả bản tóm tắt giữ trọn ý chính (Bước 1->2->3->4) lẫn bản nguyên văn từng lá bài (Bước 2->4 luôn không qua tóm tắt)
    để đọc trong Xưởng Phim Thủy Mặc.
    """
    import asyncio
    from gemini_sage import analyze_and_script
    from voice_engine import (
        condense_analysis_to_concise_script,
        split_analysis_into_card_sections,
        sanitize_script_for_tts,
        sanitize_full_analysis_for_tts,
    )

    try:
        q = (req.question or "").strip() or "Xin chỉ điểm vận trình và lời khuyên hành động tối ưu?"
        n_cards = max(1, int(req.num_cards or 4))
        gemini_data = await asyncio.to_thread(
            analyze_and_script,
            question=q,
            hexagram_data=req.hexagram_text,
            api_key=req.api_key or None,
            num_cards=n_cards
        )
        full_interp = (gemini_data.get("full_interpretation") or "").strip()
        raw_script = (gemini_data.get("video_script") or "").strip()
        hook = (gemini_data.get("hook") or "").strip()
        summary_advice = (gemini_data.get("summary_advice") or "").strip()
        hex_title = (gemini_data.get("hexagram_title") or "QUẺ KINH DỊCH CỬU NHỊ").strip()

        concise_script = condense_analysis_to_concise_script(
            raw_script or full_interp,
            question=q,
            num_cards=n_cards
        )
        parsed_sections = split_analysis_into_card_sections(concise_script, n_cards)
        card_summaries = []
        if parsed_sections.get("matched") and parsed_sections.get("cards"):
            for c_txt in parsed_sections["cards"]:
                card_summaries.append(sanitize_script_for_tts(c_txt))

        # Bản nguyên văn từng lá bài (phục vụ chế độ Bước 2 -> Bước 4 luôn không qua tóm tắt)
        full_source = raw_script if (raw_script and len(raw_script.split()) > len(concise_script.split()) + 20) else (full_interp or raw_script)
        parsed_full = split_analysis_into_card_sections(full_source, n_cards)
        if not parsed_full.get("matched") and full_interp and full_source != full_interp:
            parsed_full = split_analysis_into_card_sections(full_interp, n_cards)

        card_full_texts = []
        if parsed_full.get("matched") and parsed_full.get("cards"):
            for c_txt in parsed_full["cards"]:
                card_full_texts.append(sanitize_full_analysis_for_tts(c_txt))
        else:
            card_full_texts = list(card_summaries)

        outro_full_raw = parsed_full.get("outro") or summary_advice or parsed_sections.get("outro") or ""
        outro_full_text = sanitize_full_analysis_for_tts(outro_full_raw)

        return {
            "success": True,
            "skip_summary": bool(req.skip_summary),
            "hexagram_title": hex_title,
            "hook": hook,
            "summary_advice": summary_advice,
            "full_interpretation": full_interp,
            "concise_script": concise_script,
            "card_summaries": card_summaries,
            "outro_summary": sanitize_script_for_tts(parsed_sections.get("outro") or summary_advice),
            "card_full_texts": card_full_texts,
            "outro_full_text": outro_full_text,
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

# ==========================================
# 1D. APIS DÀNH CHO 3D AI AGENT TIỂU LONG CỬU NHỊ (VẤN ĐÁP QUẺ DỊCH TRONG ĐIỆN THOẠI Ở TRANG CHỦ)
# ==========================================

@app.get("/api/dragon_agent/poses")
async def api_get_dragon_poses():
    from gemini_sage import DRAGON_AGENT_POSES
    return {"success": True, "poses": list(DRAGON_AGENT_POSES.values())}

@app.post("/api/dragon_agent/chat")
async def api_dragon_agent_chat(req: DragonAgentChatRequest):
    """3D AI Agent Tiểu Long Cửu Nhị vấn đáp trực tiếp về quẻ dịch và câu hỏi trong điện thoại ở trang chủ."""
    import asyncio
    from gemini_sage import dragon_agent_chat
    from voice_engine import _synthesize_text_to_mp3, get_audio_duration

    try:
        chat_res = await asyncio.to_thread(
            dragon_agent_chat,
            user_message=req.user_message,
            main_question=req.main_question,
            hexagram_text=req.hexagram_text,
            full_interpretation=req.full_interpretation,
            history=req.history,
            api_key=req.api_key or None
        )

        audio_url = ""
        audio_duration = 0.0
        if req.with_voice and chat_res.get("reply"):
            try:
                ts = int(time.time() * 1000)
                out_mp3 = AUDIO_DIR / f"dragon_3d_qa_{ts}.mp3"
                voice_id = req.voice or DEFAULT_VOICE
                await _synthesize_text_to_mp3(chat_res["reply"], voice_id, out_mp3, is_full_analysis=False)
                if out_mp3.exists() and out_mp3.stat().st_size > 200:
                    audio_url = f"/media/audio/{out_mp3.name}"
                    audio_duration = round(get_audio_duration(str(out_mp3)), 1)
            except Exception as ve:
                print(f"[DragonAgent TTS Warning]: {ve}")

        return {
            "success": True,
            **chat_res,
            "audio_url": audio_url,
            "audio_duration": audio_duration,
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Lỗi khi vấn đáp cùng Tiểu Long 3D: {str(e)}"}
        )

# ==========================================
# 2. APIS DÀNH CHO BẢNG MỚI (PODCAST & MP4 FULL HD)
# ==========================================

@app.get("/api/podcast/status")
@app.get("/api/status")
async def get_podcast_status():
    return compute_live_job_view(PODCAST_JOB)

def execute_podcast_task(question: str, api_key: str, layout: str, aspect_ratio: str, duration_mode: str, voice: str):
    global PODCAST_JOB
    init_eta = 75.0 if duration_mode == "compact" else 110.0
    start_job_tracker(PODCAST_JOB, "Đang khởi tạo studio sản xuất Podcast & Video MP4...", initial_eta=init_eta)

    def update_p(p):
        update_job_tracker(PODCAST_JOB, p)

    try:
        res = run_podcast_pipeline(
            question=question,
            api_key=api_key or None,
            layout=layout,
            aspect_ratio=aspect_ratio,
            duration_mode=duration_mode,
            voice=voice,
            progress_callback=update_p
        )
        PODCAST_JOB["status"] = "completed"
        PODCAST_JOB["percent"] = 100
        PODCAST_JOB["base_percent"] = 100
        PODCAST_JOB["stage"] = "done"
        PODCAST_JOB["eta_remaining_seconds"] = 0
        PODCAST_JOB["eta_text"] = "Đã hoàn tất"
        PODCAST_JOB["elapsed_seconds"] = round(res.get("total_time", time.time() - PODCAST_JOB["started_at"]), 1)
        PODCAST_JOB["message"] = "Hoàn tất! Video MP4 và Podcast MP3 đã sẵn sàng."
        PODCAST_JOB["result"] = {
            "question": res["question"],
            "podcast_title": res["podcast_title"],
            "hexagram_title": res["hexagram_title"],
            "summary_verdict": res["summary_verdict"],
            "chapters": res["chapters"],
            "dialogue": res["dialogue"],
            "timeline": res["timeline"],
            "full_show_notes": res["full_show_notes"],
            "card_image_url": f"/media/images/{Path(res['card_image_path']).name}",
            "audio_url": f"/media/podcasts/{res['audio_filename']}",
            "audio_filename": res["audio_filename"],
            "video_url": f"/media/videos/{res['video_filename']}",
            "video_filename": res["video_filename"],
            "aspect_ratio": res["aspect_ratio"],
            "voice": voice,
            "duration": round(res["duration"], 1),
            "total_time": round(res["total_time"], 1)
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        PODCAST_JOB["status"] = "error"
        PODCAST_JOB["percent"] = 0
        PODCAST_JOB["stage"] = "error"
        PODCAST_JOB["message"] = f"Lỗi bảng mới: {str(e)}"
        PODCAST_JOB["error"] = str(e)

@app.post("/api/podcast/run")
@app.post("/api/run")
async def api_podcast_run(req: PodcastRequest, background_tasks: BackgroundTasks):
    global PODCAST_JOB
    if PODCAST_JOB["status"] == "running":
        return JSONResponse(status_code=400, content={"message": "Bảng Podcast đang chạy. Vui lòng chờ."})

    background_tasks.add_task(
        execute_podcast_task,
        req.question,
        req.api_key,
        req.layout,
        req.aspect_ratio,
        req.duration_mode,
        req.voice
    )
    return {"status": "started", "message": "Tiến trình sản xuất Podcast & Video MP4 đã được kích hoạt."}

if __name__ == "__main__":
    import uvicorn
    print("\n=================================================================")
    print("☯ CỬU NHỊ · HỆ THỐNG ĐÃ TÁCH BIỆT 2 BẢNG ĐỘC LẬP:")
    print("  1. BẢNG MỚI (Podcast MP4):  http://localhost:8000/podcast")
    print("  2. BẢNG CŨ  (Luận trực tiếp): http://localhost:8000/direct")
    print("=================================================================\n")
    uvicorn.run("web_app:app", host="0.0.0.0", port=8000, reload=False)
