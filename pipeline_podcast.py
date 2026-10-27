import sys
import time
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from config import (
    GEMINI_API_KEY, IMAGES_DIR, AUDIO_DIR, VIDEOS_DIR, PODCASTS_DIR,
    DEFAULT_ASPECT_RATIO
)
from crawler import cast_and_collect
from podcast_sage import generate_podcast_analysis
from podcast_engine import generate_podcast_audio
from podcast_video_engine import render_podcast_video

def run_podcast_pipeline(
    question: str,
    api_key: str = None,
    layout: str = "random",
    aspect_ratio: str = None,
    duration_mode: str = "deep",
    voice: str = "duet_standard",
    progress_callback=None
) -> dict:
    """
    [BẢNG MỚI] Quy trình xuất bản Video MP4 & Podcast phân tích chuyên sâu 2 người:
    1. ichingtarot.com -> Bốc quẻ -> Tải ảnh đồ hình quẻ -> Lấy dữ liệu Dịch học.
    2. Gemini Multi-Model -> Biên soạn kịch bản đối thoại 2 người (Hoài My & Nam Minh) + Show Notes.
    3. Neural TTS -> Thu âm đa giọng truyền cảm + Chuông xoay Tây Tạng + Nhạc thiền 432Hz.
    4. FFmpeg Engine -> Render Video MP4 Full HD (16:9 / 9:16) với sóng âm động & đèn báo người nói.
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
    ratio = aspect_ratio or DEFAULT_ASPECT_RATIO
    key = api_key or GEMINI_API_KEY
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # STAGE 1: CRAWLER (ichingtarot.com)
    notify("crawler", 15, "Đang kết nối ichingtarot.com, bốc quẻ và lấy dữ liệu...")
    crawl_result = cast_and_collect(layout=layout, headless=True, log_cb=lambda m: notify("crawler", 25, m))
    if not crawl_result.get("success"):
        raise RuntimeError(f"Lỗi khi thu thập quẻ từ ichingtarot.com: {crawl_result.get('error')}")

    card_image_path = crawl_result["image_path"]
    hexagram_text = crawl_result["hexagram_text"]

    # STAGE 2: GEMINI PODCAST SAGE
    notify("sage", 40, "Đại sư Dịch học Gemini đang luận giải Dịch lý chuyên sâu & biên soạn kịch bản Podcast 2 người...")
    podcast_data = generate_podcast_analysis(
        question=question,
        hexagram_data=hexagram_text,
        api_key=key,
        duration_mode=duration_mode,
        log_cb=lambda m: notify("sage", 50, m)
    )

    podcast_title = podcast_data.get("podcast_title", "Cửu Nhị Luận Đạo · Podcast Dịch Học")
    hexagram_title = podcast_data.get("hexagram_title", "QUẺ KINH DỊCH CÁT TƯỜNG")
    summary_verdict = podcast_data.get("summary_verdict", "Thuận thời đắc vị, tâm an vạn sự cát lành.")
    chapters = podcast_data.get("chapters", [])
    dialogue = podcast_data.get("dialogue", [])
    full_show_notes = podcast_data.get("full_show_notes", "")

    # STAGE 3: MULTI-SPEAKER AUDIO & TIMELINE
    notify("audio", 65, f"Đang thu âm theo giọng [{voice}], hòa trộn chuông xoay 432Hz...")
    audio_path = PODCASTS_DIR / f"podcast_{timestamp}.mp3"
    timeline_path = PODCASTS_DIR / f"podcast_{timestamp}_timeline.json"
    ass_path = PODCASTS_DIR / f"podcast_{timestamp}.ass"

    audio_res = generate_podcast_audio(
        dialogue=dialogue,
        output_audio_path=str(audio_path),
        output_timeline_path=str(timeline_path),
        output_ass_path=str(ass_path),
        voice_preset=voice,
        log_cb=lambda m: notify("audio", 75, m)
    )
    duration = audio_res.get("duration", 0)
    timeline = audio_res.get("timeline", [])

    # STAGE 4: MP4 VIDEO PODCAST RENDERING
    notify("video", 85, f"Đang kết xuất Video MP4 Podcast Full HD ({ratio}) với sóng âm thanh động & đèn báo người nói...")
    video_path = VIDEOS_DIR / f"podcast_video_{timestamp}.mp4"

    video_res = render_podcast_video(
        card_image_path=card_image_path,
        audio_path=str(audio_path),
        timeline_path=str(timeline_path),
        ass_subtitle_path=str(ass_path),
        hexagram_title=hexagram_title,
        podcast_title=podcast_title,
        output_video_path=str(video_path),
        aspect_ratio=ratio,
        log_cb=lambda m: notify("video", 92, m)
    )

    total_time = time.time() - start_time
    notify("done", 100, f"Hoàn tất tuyệt đối! Xuất xưởng Video MP4 và Podcast MP3 trong {total_time:.1f} giây.")

    return {
        "success": True,
        "question": question,
        "podcast_title": podcast_title,
        "hexagram_title": hexagram_title,
        "summary_verdict": summary_verdict,
        "chapters": chapters,
        "dialogue": dialogue,
        "timeline": timeline,
        "full_show_notes": full_show_notes,
        "card_image_path": card_image_path,
        "audio_path": str(audio_path),
        "audio_filename": audio_path.name,
        "video_path": str(video_path),
        "video_filename": video_path.name,
        "aspect_ratio": ratio,
        "duration": duration,
        "total_time": total_time
    }

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="[BẢNG MỚI] Cửu Nhị · Studio Video MP4 & Podcast Kinh Dịch Chuyên Sâu")
    parser.add_argument("--question", type=str, required=True, help="Câu hỏi cần chiêm bốc")
    parser.add_argument("--api-key", type=str, default="", help="Gemini API Key")
    parser.add_argument("--layout", type=str, default="1_card", help="1_card hoặc 3_card")
    parser.add_argument("--aspect-ratio", type=str, default="16:9", choices=["16:9", "9:16"])
    parser.add_argument("--mode", type=str, default="deep", choices=["deep", "compact"])
    args = parser.parse_args()

    res = run_podcast_pipeline(
        question=args.question,
        api_key=args.api_key or None,
        layout=args.layout,
        aspect_ratio=args.aspect_ratio,
        duration_mode=args.mode
    )
    print("\n=== THÀNH PHẨM PODCAST CHUYÊN SÂU ===")
    print(f"Tiêu đề: {res['podcast_title']}")
    print(f"Quẻ: {res['hexagram_title']}")
    print(f"File Audio MP3: {res['audio_path']}")
    print(f"File Video MP4: {res['video_path']}")
