"""
=============================================================================
HỆ THỐNG TỰ ĐỘNG HÓA LUẬN GIẢI KINH DỊCH & SẢN XUẤT VIDEO PODCAST ĐA AI (1-CLICK)
Hội tụ: Playwright (ichingtarot.com) + ChatGPT & Gemini + Edge-TTS + FFmpeg
=============================================================================
"""

import os
import sys
import time
import argparse

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from crawler import crawl_iching_reading
from ai_podcast_debate import generate_podcast_dialogue
from video_producer import produce_video_from_script

def main():
    parser = argparse.ArgumentParser(description="Bốc quẻ Kinh Dịch & Tạo Video Podcast Đa AI")
    parser.add_argument(
        "--question", "-q",
        type=str,
        default="Định hướng phát triển sự nghiệp và tài chính trong 6 tháng tới nên đi theo hướng nào?",
        help="Câu hỏi hoặc sự việc bạn đang trăn trở gửi đến quẻ dịch"
    )
    args = parser.parse_args()
    user_question = args.question.strip()

    print("=" * 68)
    print("      ☯ HỆ THỐNG TỰ ĐỘNG BỐC QUẺ & SẢN XUẤT VIDEO PODCAST KINH DỊCH ☯")
    print("=" * 68)
    print(f"📌 Câu hỏi của đạo hữu: \"{user_question}\"")
    start_time = time.time()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(base_dir, "output")
    os.makedirs(output_dir, exist_ok=True)

    # -------------------------------------------------------------
    # BƯỚC 1: Nhập câu hỏi, Bốc Tam Kính, Chụp ảnh thẻ bài, Chép toàn thư
    # -------------------------------------------------------------
    img_path, txt_path, raw_text, q = crawl_iching_reading(
        output_dir=output_dir,
        user_question=user_question,
        headless=True
    )

    # -------------------------------------------------------------
    # BƯỚC 2: Đẩy toàn thư & câu hỏi cho Gemini & ChatGPT tranh biện
    # -------------------------------------------------------------
    script_path, dialogue = generate_podcast_dialogue(
        raw_text,
        user_question=user_question,
        output_dir=output_dir
    )

    # -------------------------------------------------------------
    # BƯỚC 3 & 4: Lồng tiếng 2 AI & Render Video với CHÍNH XÁC ảnh chụp thẻ bài
    # -------------------------------------------------------------
    final_video_path = os.path.join(output_dir, "iching_podcast_video.mp4")
    produce_video_from_script(script_path, img_path, output_video_path=final_video_path)

    elapsed = round(time.time() - start_time, 2)
    print("\n" + "=" * 68)
    print(f"✨ TẤT CẢ TÁC VỤ ĐÃ HOÀN TẤT THÀNH CÔNG TRONG {elapsed} GIÂY!")
    print(f"❓ Câu hỏi đã giải đáp  : \"{user_question}\"")
    print(f"📸 Ảnh chụp thẻ bài thật: {img_path}")
    print(f"📖 Toàn thư bách khoa   : {txt_path}")
    print(f"🎙️ Kịch bản Podcast      : {script_path}")
    print(f"🎬 VIDEO PODCAST HOÀN THIỆN: {final_video_path}")
    print("=" * 68)

if __name__ == "__main__":
    main()
