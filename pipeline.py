import sys
from pipeline_direct import run_direct_pipeline
from pipeline_podcast import run_podcast_pipeline

# Default to podcast pipeline, with direct pipeline available
run_divination_pipeline = run_direct_pipeline

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Cửu Nhị · Điều phối Dịch học")
    parser.add_argument("--mode", type=str, default="podcast", choices=["podcast", "direct"], help="Chọn bản: podcast hoặc direct")
    parser.add_argument("--question", type=str, required=True, help="Câu hỏi cần chiêm bốc")
    parser.add_argument("--api-key", type=str, default="", help="Gemini API Key")
    parser.add_argument("--layout", type=str, default="1_card", help="1_card hoặc 3_card")
    parser.add_argument("--aspect-ratio", type=str, default="16:9", choices=["16:9", "9:16"])
    parser.add_argument("--voice", type=str, default="duet_standard", help="Tùy chọn giọng đọc")
    args = parser.parse_args()

    if args.mode == "direct":
        res = run_direct_pipeline(question=args.question, api_key=args.api_key or None, layout=args.layout, voice=args.voice)
    else:
        res = run_podcast_pipeline(question=args.question, api_key=args.api_key or None, layout=args.layout, aspect_ratio=args.aspect_ratio, voice=args.voice)
