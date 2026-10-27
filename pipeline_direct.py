import sys
import time
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from config import GEMINI_API_KEY, IMAGES_DIR, AUDIO_DIR, VIDEOS_DIR, DEFAULT_VOICE
from crawler import cast_and_collect
from gemini_sage import analyze_and_script
from voice_engine import generate_voice_and_subtitles, condense_analysis_to_concise_script
from video_engine import render_vertical_video, extract_cards_from_spread

def run_direct_pipeline(
    question: str,
    api_key: str = None,
    layout: str = "random",
    voice: str = None,
    progress_callback=None
) -> dict:
    """
    [BẢNG CŨ] Quy trình luận giải trực tiếp & kết xuất Video dọc 9:16 TikTok/Shorts đồng bộ 100% từng lá bài.
    """
    def notify(stage: str, percent: int, message: str):
        if progress_callback:
            progress_callback({
                "stage": stage,
                "percent": percent,
                "message": message
            })
        print(f"[{percent}%] [{stage}] {message}")

    start_time = time.time()
    v = voice or DEFAULT_VOICE
    key = api_key or GEMINI_API_KEY
    if not key:
        raise ValueError("Chưa thiết lập GEMINI_API_KEY. Vui lòng cung cấp khóa API để tiếp tục.")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # STAGE 1: CRAWL
    notify("crawler", 15, "Đang truy cập ichingtarot.com, bốc quẻ và lấy dữ liệu...")
    crawl_result = cast_and_collect(layout=layout, headless=True, log_cb=lambda m: notify("crawler", 25, m))
    if not crawl_result.get("success"):
        raise RuntimeError(f"Lỗi khi thu thập quẻ từ ichingtarot.com: {crawl_result.get('error')}")

    card_image_path = crawl_result["image_path"]
    hexagram_text = crawl_result["hexagram_text"]

    video_path = VIDEOS_DIR / f"kinhdich_{timestamp}.mp4"
    temp_dir = VIDEOS_DIR / f"temp_{video_path.stem}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    extracted = extract_cards_from_spread(Path(card_image_path), temp_dir)
    resolved_card_paths = [str(p.resolve()) for p in extracted]
    num_cards = len(resolved_card_paths)

    # STAGE 2: GEMINI ANALYSIS
    notify("gemini", 45, "Đại sư Dịch học Gemini đang luận giải Dịch lý & biên soạn kịch bản video...")
    gemini_data = analyze_and_script(
        question=question,
        hexagram_data=hexagram_text,
        api_key=key,
        num_cards=num_cards
    )

    hexagram_title = gemini_data.get("hexagram_title", "QUẺ KINH DỊCH")
    raw_video_script = gemini_data.get("video_script", "")
    full_interpretation = gemini_data.get("full_interpretation", "")
    summary_advice = gemini_data.get("summary_advice", "")
    hook = gemini_data.get("hook", "")
    video_script = condense_analysis_to_concise_script(
        raw_video_script or full_interpretation,
        question=question,
        num_cards=num_cards
    )

    # STAGE 3: VOICE & SUBTITLES FOR VERTICAL VIDEO
    notify("voice", 65, "Đang tổng hợp giọng thuyết minh AI & đồng bộ thời gian từng lá bài...")
    audio_path = AUDIO_DIR / f"voice_{timestamp}.mp3"
    ass_path = AUDIO_DIR / f"sub_{timestamp}.ass"

    voice_res = generate_voice_and_subtitles(
        text=video_script,
        output_audio_path=str(audio_path),
        output_ass_path=str(ass_path),
        voice=v,
        num_cards=num_cards
    )
    duration = voice_res.get("duration", 0)
    section_timings = voice_res.get("section_timings")

    # STAGE 4: VIDEO RENDERING
    notify("video", 85, "Đang kết xuất video dọc 9:16 (1080x1920) đồng bộ 100% từng lá bài...")

    render_vertical_video(
        card_image_path=card_image_path,
        voice_audio_path=str(audio_path),
        ass_subtitle_path=str(ass_path),
        question=question,
        hexagram_title=hexagram_title,
        output_video_path=str(video_path),
        section_timings=section_timings,
        ordered_card_paths=resolved_card_paths,
        log_cb=lambda m: notify("video", 92, m)
    )

    total_time = time.time() - start_time
    notify("done", 100, f"Hoàn tất! Xuất xưởng video trong {total_time:.1f} giây.")

    return {
        "success": True,
        "question": question,
        "hexagram_title": hexagram_title,
        "hook": hook,
        "summary_advice": summary_advice,
        "full_interpretation": full_interpretation,
        "video_script": video_script,
        "card_image_path": card_image_path,
        "video_path": str(video_path),
        "video_filename": video_path.name,
        "duration": duration,
        "total_time": total_time
    }
