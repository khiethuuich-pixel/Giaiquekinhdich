import sys
import time
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from config import GEMINI_API_KEY, IMAGES_DIR, AUDIO_DIR, VIDEOS_DIR, DEFAULT_VOICE
from crawler import cast_and_collect
from gemini_sage import analyze_and_script
from voice_engine import (
    generate_voice_and_subtitles,
    sanitize_script_for_tts,
    condense_analysis_to_concise_script
)
from video_engine import render_vertical_video, extract_cards_from_spread


def run_direct_full_pipeline(
    question: str,
    api_key: str = None,
    layout: str = "random",
    voice: str = None,
    custom_analysis_text: str = None,
    existing_image_path: str = None,
    existing_hexagram_text: str = None,
    ordered_card_paths: list[str] = None,
    progress_callback=None
) -> dict:
    """
    [BẢNG LUẬN FULL PHÂN TÍCH] Quy trình luận giải trực tiếp GHI ÂM TOÀN BỘ NỘI DUNG GEMINI PHÂN TÍCH
    và ĐỒNG BỘ 100% TỪNG LÁ BÀI (1 -> N) TRONG VIDEO 9:16 VỚI GIỌNG ĐỌC AI:
    1. Lấy ảnh trận pháp + ảnh từng lá bài theo đúng thứ tự 1 -> N + dữ liệu 'Chép Cho AI'.
    2. Đưa nội dung 'Chép Cho AI' vào Gemini phân tích 4 phần (hoặc nhận nội dung phân tích có sẵn).
    3. Tách bài phân tích theo từng phần (Phần 1 Intro -> Lá 1 .. Lá N -> Phần 3 & 4 Outro) để ghi âm Edge-TTS,
       đo chính xác thời lượng từng lá bài (`section_timings`) và tạo phụ đề ASS khớp từng câu.
    4. FFmpeg -> Render video dọc 9:16 (1080x1920) chuyển cận cảnh đúng Lá k ngay tại giây giọng đọc bắt đầu đọc Lá k!
    """
    def notify(stage: str, percent: int, message: str, **extra):
        if progress_callback:
            payload = {
                "stage": stage,
                "percent": percent,
                "message": message
            }
            payload.update(extra)
            progress_callback(payload)
        print(f"[{percent}%] [{stage}] {message}")

    start_time = time.time()
    v = voice or DEFAULT_VOICE
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Initial card count hint
    init_cards = len(ordered_card_paths) if ordered_card_paths else 3
    init_eta = (1.5 if existing_image_path else 10.0) + (1.0 if (custom_analysis_text and custom_analysis_text.strip()) else (10.0 + 1.5 * init_cards)) + (6.0 + 1.5 * init_cards) + (12.0 + 2.5 * init_cards)

    # STAGE 1: CRAWL (or reuse already cast card image from Homepage)
    if existing_image_path and Path(existing_image_path).exists():
        notify("crawler", 18, "Sử dụng ảnh quẻ & dữ liệu 'Chép Cho AI' trực tiếp từ Trang Chủ...", eta_remaining=round(init_eta), num_cards=init_cards)
        card_image_path = existing_image_path
        hexagram_text = existing_hexagram_text or ""
    else:
        notify("crawler", 12, "Đang truy cập ichingtarot.com, bốc quẻ và bấm 'Chép Cho AI'...", eta_remaining=round(init_eta), num_cards=init_cards)
        crawl_result = cast_and_collect(layout=layout, headless=True, log_cb=lambda m: notify("crawler", 22, m))
        if not crawl_result.get("success"):
            raise RuntimeError(f"Lỗi khi thu thập quẻ từ ichingtarot.com: {crawl_result.get('error')}")
        card_image_path = crawl_result["image_path"]
        hexagram_text = crawl_result["hexagram_text"]

    # Determine exact ordered cards (1 .. N) before TTS so voice_engine knows `num_cards`
    video_path = VIDEOS_DIR / f"kinhdich_full_{timestamp}.mp4"
    temp_dir = VIDEOS_DIR / f"temp_{video_path.stem}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    if ordered_card_paths and all(Path(p).exists() for p in ordered_card_paths):
        resolved_card_paths = [str(Path(p).resolve()) for p in ordered_card_paths]
    else:
        extracted = extract_cards_from_spread(Path(card_image_path), temp_dir)
        resolved_card_paths = [str(p.resolve()) for p in extracted]
    num_cards = len(resolved_card_paths)

    # Calibrate ETA for Stage 2 + 3 + 4
    t_gemini_est = 1.0 if (custom_analysis_text and custom_analysis_text.strip()) else (10.0 + 1.5 * num_cards)
    t_voice_est_init = 6.0 + 1.5 * num_cards
    t_video_est_init = 12.0 + 2.5 * num_cards

    # STAGE 2: GEMINI ANALYSIS (or use custom pasted Gemini analysis)
    if custom_analysis_text and custom_analysis_text.strip():
        notify("gemini", 42, "Đang tiếp nhận nội dung phân tích & chắt lọc kịch bản thuyết minh cô đọng...", eta_remaining=round(t_voice_est_init + t_video_est_init), num_cards=num_cards)
        full_interpretation = custom_analysis_text.strip()
        hexagram_title = "LUẬN GIẢI KINH DỊCH CỬU NHỊ"
        for line in full_interpretation.splitlines()[:8]:
            clean_l = line.strip().strip("#*✦☯ ")
            if clean_l and ("QUẺ" in clean_l.upper() or "TRẬN" in clean_l.upper()) and len(clean_l) < 80:
                hexagram_title = clean_l
                break
        hook = f"Luận giải câu hỏi: {question}"
        summary_advice = "Kịch bản thuyết minh tinh gọn, đầy đủ thông điệp."
        concise_script = condense_analysis_to_concise_script(full_interpretation, question=question, num_cards=num_cards)
    else:
        key = api_key or GEMINI_API_KEY
        if not key:
            raise ValueError("Chưa thiết lập GEMINI_API_KEY. Vui lòng cung cấp khóa API hoặc dán trực tiếp nội dung phân tích từ Gemini vào ô bên dưới.")

        notify("gemini", 35, f"Đang đưa dữ liệu 'Chép Cho AI' ({num_cards} lá bài) vào Gemini luận giải & biên soạn thuyết minh tinh gọn...", eta_remaining=round(t_gemini_est + t_voice_est_init + t_video_est_init), num_cards=num_cards)
        gemini_data = analyze_and_script(
            question=question,
            hexagram_data=hexagram_text,
            api_key=key,
            num_cards=num_cards
        )
        hexagram_title = gemini_data.get("hexagram_title", "QUẺ KINH DỊCH")
        full_interpretation = gemini_data.get("full_interpretation", "").strip()
        raw_video_script = gemini_data.get("video_script", "").strip()
        hook = gemini_data.get("hook", "")
        summary_advice = gemini_data.get("summary_advice", "")
        if not full_interpretation:
            full_interpretation = raw_video_script
        concise_script = condense_analysis_to_concise_script(
            raw_video_script or full_interpretation,
            question=question,
            num_cards=num_cards
        )

    # STAGE 3: RECORD CONCISE NARRATION SCRIPT (TTS) & SUBTITLES WITH EXACT PER-CARD TIMING
    full_text_to_record = concise_script
    spoken_clean_script = sanitize_script_for_tts(full_text_to_record)
    char_count = len(spoken_clean_script)
    est_audio_sec = max(14.0, char_count / 17.5)
    t_voice_est = 3.0 + (char_count / 1200.0) * 2.0 + 0.8 * num_cards
    t_video_est = 5.0 + 0.30 * est_audio_sec + 1.4 * num_cards

    notify(
        "voice",
        60,
        f"Đang ghi âm thuyết minh cô đọng ({char_count} ký tự) & đồng bộ từng lá bài (Lá 1 -> Lá {num_cards})...",
        eta_remaining=round(t_voice_est + t_video_est),
        num_cards=num_cards
    )
    audio_path = AUDIO_DIR / f"voice_full_{timestamp}.mp3"
    ass_path = AUDIO_DIR / f"sub_full_{timestamp}.ass"

    voice_res = generate_voice_and_subtitles(
        text=full_text_to_record,
        output_audio_path=str(audio_path),
        output_ass_path=str(ass_path),
        voice=v,
        is_full_analysis=False,
        num_cards=num_cards
    )
    duration = voice_res.get("duration", 0)
    section_timings = voice_res.get("section_timings")

    # STAGE 4: VIDEO RENDERING (9:16 FULL HD, 100% SYNCED TO PER-CARD TIMINGS)
    t_video_exact = max(12.0, 6.0 + 0.35 * duration + 1.8 * num_cards)
    video_stage_start = time.time()
    notify(
        "video",
        80,
        f"Đang kết xuất video dọc 9:16 (thời lượng {duration:.1f}s) đồng bộ chính xác {num_cards} lá bài...",
        eta_remaining=round(t_video_exact),
        num_cards=num_cards,
        audio_duration=round(duration, 1)
    )

    video_step = [0]
    total_video_steps = max(4, num_cards + 3)

    def on_video_log(m: str):
        video_step[0] += 1
        frac = min(0.95, video_step[0] / total_video_steps)
        sub_pct = int(80 + frac * 17)
        spent_v = time.time() - video_stage_start
        rem_v = max(3, round(t_video_exact - spent_v))
        notify("video", sub_pct, m, eta_remaining=rem_v, num_cards=num_cards, audio_duration=round(duration, 1))

    render_vertical_video(
        card_image_path=card_image_path,
        voice_audio_path=str(audio_path),
        ass_subtitle_path=str(ass_path),
        question=question,
        hexagram_title=hexagram_title,
        output_video_path=str(video_path),
        section_timings=section_timings,
        ordered_card_paths=resolved_card_paths,
        log_cb=on_video_log
    )

    total_time = time.time() - start_time
    notify("done", 100, f"Hoàn tất! Video 9:16 ({duration:.1f}s) đã xuất xưởng trong {total_time:.1f}s.", eta_remaining=0, num_cards=num_cards, audio_duration=round(duration, 1))

    return {
        "success": True,
        "question": question,
        "hexagram_title": hexagram_title,
        "hook": hook,
        "summary_advice": summary_advice,
        "hexagram_raw_ai_text": hexagram_text,
        "full_interpretation": full_interpretation,
        "video_script": spoken_clean_script,
        "card_image_path": card_image_path,
        "audio_path": str(audio_path),
        "audio_filename": audio_path.name,
        "video_path": str(video_path),
        "video_filename": video_path.name,
        "duration": duration,
        "total_time": total_time
    }
