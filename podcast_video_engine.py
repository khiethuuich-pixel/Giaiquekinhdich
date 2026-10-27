import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from config import VIDEOS_DIR, ASSETS_DIR, VIDEO_RESOLUTIONS

def create_podcast_artboards(
    card_img_path: Path,
    hexagram_title: str,
    podcast_title: str,
    output_dir: Path,
    aspect_ratio: str = "16:9"
) -> dict:
    """
    Generate the visual artboards for the podcast video:
    - Base canvas
    - Host active highlight overlay
    - Master active highlight overlay
    """
    is_16_9 = (aspect_ratio == "16:9")
    w = 1920 if is_16_9 else 1080
    h = 1080 if is_16_9 else 1920

    output_dir.mkdir(parents=True, exist_ok=True)
    base_path = output_dir / f"base_{aspect_ratio.replace(':', '_')}.png"
    host_active_path = output_dir / f"host_active_{aspect_ratio.replace(':', '_')}.png"
    master_active_path = output_dir / f"master_active_{aspect_ratio.replace(':', '_')}.png"

    # Base Canvas
    canvas = Image.new("RGBA", (w, h), (11, 10, 8, 255))
    draw = ImageDraw.Draw(canvas)

    # Meditative radial gradient
    cx, cy = w // 2, h // 2
    for r in range(max(w, h), 0, -35):
        alpha = int(24 * (1.0 - (r / max(w, h))))
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(196, 150, 62, alpha))

    # Borders
    draw.rectangle([20, 20, w - 20, h - 20], outline=(196, 150, 62, 130), width=2)
    draw.rectangle([28, 28, w - 28, h - 28], outline=(154, 31, 26, 90), width=1)

    # Fonts
    try:
        font_title = ImageFont.truetype("arialbd.ttf", 34 if is_16_9 else 38)
        font_sub = ImageFont.truetype("arial.ttf", 20 if is_16_9 else 24)
        font_badge = ImageFont.truetype("arialbd.ttf", 16)
        font_badge_small = ImageFont.truetype("arialbd.ttf", 14)
    except Exception:
        font_title = ImageFont.load_default()
        font_sub = ImageFont.load_default()
        font_badge = ImageFont.load_default()
        font_badge_small = ImageFont.load_default()

    if is_16_9:
        # TOP HEADER
        draw.rounded_rectangle([70, 35, 520, 75], radius=6, fill=(30, 25, 20, 220), outline=(212, 175, 55, 180), width=1)
        draw.text((90, 44), "☯ CỬU NHỊ LUẬN ĐẠO · PODCAST DỊCH HỌC", fill=(243, 229, 171), font=font_badge)
        draw.text((70, 85), hexagram_title.upper(), fill=(212, 175, 55), font=font_title)

        # LEFT PANEL: CARD ARTWORK
        card_w, card_h = 460, 760
        card_x, card_y = 80, 150

        draw.rounded_rectangle([card_x - 6, card_y - 6, card_x + card_w + 6, card_y + card_h + 6], radius=16, outline=(212, 175, 55, 120), width=3)
        draw.rounded_rectangle([card_x, card_y, card_x + card_w, card_y + card_h], radius=12, fill=(20, 18, 15, 255), outline=(196, 150, 62, 220), width=2)

        if card_img_path and Path(card_img_path).exists():
            try:
                c_img = Image.open(card_img_path).convert("RGBA")
                c_img.thumbnail((card_w - 20, card_h - 20), Image.Resampling.LANCZOS)
                cw, ch = c_img.size
                canvas.paste(c_img, (card_x + (card_w - cw) // 2, card_y + (card_h - ch) // 2), c_img)
            except Exception as e:
                print(f"Paste card error: {e}")

        # RIGHT PANEL: SPEAKER CARDS (NEUTRAL)
        right_x, spk_w, spk_h = 590, 1250, 155
        s1_y, s2_y = 150, 335

        # Host Neutral Card
        draw.rounded_rectangle([right_x, s1_y, right_x + spk_w, s1_y + spk_h], radius=14, fill=(22, 20, 16, 220), outline=(80, 70, 55), width=2)
        draw.ellipse([right_x + 25, s1_y + 32, right_x + 115, s1_y + 122], fill=(45, 37, 26, 255), outline=(140, 120, 85), width=2)
        draw.text((right_x + 55, s1_y + 52), "🎙", fill=(243, 229, 171), font=font_title)
        draw.text((right_x + 135, s1_y + 38), "HOÀI MY · CHỦ TỌA", fill=(220, 210, 195), font=font_title)
        draw.text((right_x + 135, s1_y + 86), "Người dẫn chuyện · Cầu nối thấu cảm cùng thính giả", fill=(140, 130, 115), font=font_sub)

        # Master Neutral Card
        draw.rounded_rectangle([right_x, s2_y, right_x + spk_w, s2_y + spk_h], radius=14, fill=(22, 20, 16, 220), outline=(80, 70, 55), width=2)
        draw.ellipse([right_x + 25, s2_y + 32, right_x + 115, s2_y + 122], fill=(45, 37, 26, 255), outline=(140, 120, 85), width=2)
        draw.text((right_x + 55, s2_y + 52), "☯", fill=(212, 175, 55), font=font_title)
        draw.text((right_x + 135, s2_y + 38), "DỊCH SƯ NAM MINH", fill=(220, 210, 195), font=font_title)
        draw.text((right_x + 135, s2_y + 86), "Bậc Trưởng Lão Dịch Học · Phân Tích Dịch Lý & Đạo Tùy Thời", fill=(140, 130, 115), font=font_sub)

        # Waveform Container Area
        draw.rounded_rectangle([right_x, 520, right_x + spk_w, 640], radius=10, fill=(16, 14, 12, 200), outline=(50, 42, 30), width=1)
        draw.text((right_x + 25, 530), "SÓNG ÂM THANH THỜI GIAN THỰC", fill=(120, 110, 95), font=font_badge_small)

        # Subtitle Panel Glassmorphism
        draw.rounded_rectangle([right_x, 675, right_x + spk_w, 910], radius=14, fill=(15, 13, 10, 240), outline=(196, 150, 62, 180), width=2)
        draw.text((right_x + 25, 688), "✦ LỜI THOẠI ĐỐI ĐÁP ĐỒNG BỘ ✦", fill=(140, 120, 90), font=font_badge_small)

        canvas.save(base_path, "PNG")

        # Create Host Active Overlay Card
        host_active_img = Image.new("RGBA", (spk_w + 20, spk_h + 20), (0, 0, 0, 0))
        h_draw = ImageDraw.Draw(host_active_img)
        # Glowing border + Gold gradient fill
        h_draw.rounded_rectangle([5, 5, spk_w + 5, spk_h + 5], radius=14, fill=(35, 28, 18, 250), outline=(243, 229, 171, 255), width=3)
        h_draw.ellipse([30, 37, 120, 127], fill=(60, 48, 30, 255), outline=(243, 229, 171), width=2)
        h_draw.text((60, 57), "🎙", fill=(255, 245, 200), font=font_title)
        h_draw.text((140, 43), "HOÀI MY · CHỦ TỌA  [🎙 ĐANG PHÁT BIỂU]", fill=(255, 240, 180), font=font_title)
        h_draw.text((140, 91), "Người dẫn chuyện · Cầu nối thấu cảm cùng thính giả", fill=(220, 210, 185), font=font_sub)
        host_active_img.save(host_active_path, "PNG")

        # Create Master Active Overlay Card
        master_active_img = Image.new("RGBA", (spk_w + 20, spk_h + 20), (0, 0, 0, 0))
        m_draw = ImageDraw.Draw(master_active_img)
        m_draw.rounded_rectangle([5, 5, spk_w + 5, spk_h + 5], radius=14, fill=(35, 28, 18, 250), outline=(212, 175, 55, 255), width=3)
        m_draw.ellipse([30, 37, 120, 127], fill=(60, 48, 30, 255), outline=(212, 175, 55), width=2)
        m_draw.text((60, 57), "☯", fill=(212, 175, 55), font=font_title)
        m_draw.text((140, 43), "DỊCH SƯ NAM MINH  [☯ ĐANG GIẢNG NGHĨA]", fill=(212, 175, 55), font=font_title)
        m_draw.text((140, 91), "Bậc Trưởng Lão Dịch Học · Phân Tích Dịch Lý & Đạo Tùy Thời", fill=(220, 210, 185), font=font_sub)
        master_active_img.save(master_active_path, "PNG")

    else:
        # 9:16 VERTICAL BASE
        draw.rounded_rectangle([50, 60, w - 50, 120], radius=8, fill=(30, 25, 20, 220), outline=(212, 175, 55, 180), width=1)
        draw.text((80, 77), "☯ CỬU NHỊ LUẬN ĐẠO · PODCAST DỊCH HỌC", fill=(243, 229, 171), font=font_badge)
        draw.text((50, 145), hexagram_title.upper(), fill=(212, 175, 55), font=font_title)

        card_w, card_h = 640, 760
        card_x = (w - card_w) // 2
        card_y = 230
        draw.rounded_rectangle([card_x, card_y, card_x + card_w, card_y + card_h], radius=14, fill=(20, 18, 15, 255), outline=(196, 150, 62, 220), width=2)

        if card_img_path and Path(card_img_path).exists():
            try:
                c_img = Image.open(card_img_path).convert("RGBA")
                c_img.thumbnail((card_w - 20, card_h - 20), Image.Resampling.LANCZOS)
                cw, ch = c_img.size
                canvas.paste(c_img, (card_x + (card_w - cw) // 2, card_y + (card_h - ch) // 2), c_img)
            except Exception as e:
                print(f"Paste vertical error: {e}")

        spk_y = 1040
        draw.rounded_rectangle([50, spk_y, w - 50, spk_y + 130], radius=12, fill=(22, 20, 16, 220), outline=(212, 175, 55, 160), width=1.5)
        draw.text((80, spk_y + 25), "🎙 HOÀI MY (Host)  ·  ☯ DỊCH SƯ NAM MINH (Master)", fill=(243, 229, 171), font=font_title)
        draw.text((80, spk_y + 75), "Đang đàm đạo & phân tích Dịch lý chuyên sâu...", fill=(160, 150, 135), font=font_sub)

        # Waveform area
        draw.rounded_rectangle([50, 1200, w - 50, 1330], radius=10, fill=(16, 14, 12, 200), outline=(50, 42, 30), width=1)

        # Subtitle area
        draw.rounded_rectangle([50, 1370, w - 50, 1840], radius=14, fill=(15, 13, 10, 230), outline=(196, 150, 62, 180), width=2)

        canvas.save(base_path, "PNG")

        # In 9:16 vertical, create simple active badges
        host_active_img = Image.new("RGBA", (w - 100, 130), (0, 0, 0, 0))
        h_draw = ImageDraw.Draw(host_active_img)
        h_draw.rounded_rectangle([0, 0, w - 100, 130], radius=12, fill=(35, 28, 18, 250), outline=(243, 229, 171), width=2)
        h_draw.text((30, 25), "🎙 HOÀI MY · ĐANG PHÁT BIỂU", fill=(255, 240, 180), font=font_title)
        h_draw.text((30, 75), "Chủ tọa đang đặt câu hỏi & đối thoại thính giả", fill=(210, 200, 180), font=font_sub)
        host_active_img.save(host_active_path, "PNG")

        master_active_img = Image.new("RGBA", (w - 100, 130), (0, 0, 0, 0))
        m_draw = ImageDraw.Draw(master_active_img)
        m_draw.rounded_rectangle([0, 0, w - 100, 130], radius=12, fill=(35, 28, 18, 250), outline=(212, 175, 55), width=2)
        m_draw.text((30, 25), "☯ DỊCH SƯ NAM MINH · ĐANG GIẢNG NGHĨA", fill=(212, 175, 55), font=font_title)
        m_draw.text((30, 75), "Đại sư đang giải mã hào biến & Đạo Tùy Thời", fill=(210, 200, 180), font=font_sub)
        master_active_img.save(master_active_path, "PNG")

    return {
        "base_path": base_path,
        "host_active_path": host_active_path,
        "master_active_path": master_active_path
    }

def render_podcast_video(
    card_image_path: str,
    audio_path: str,
    timeline_path: str,
    ass_subtitle_path: str,
    hexagram_title: str,
    podcast_title: str,
    output_video_path: str,
    aspect_ratio: str = "16:9",
    background_video_path: str = None,
    log_cb=None
) -> dict:
    """
    Render complete Full HD MP4 Video Podcast:
    - Base canvas layout
    - Animated Waveform overlay
    - Active speaker highlighting
    - Dynamic ASS subtitles
    """
    def log(msg):
        if log_cb:
            log_cb(msg)
        print(f"[PodcastVideo] {msg}")

    out_mp4 = Path(output_video_path).resolve()
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = out_mp4.parent / f"temp_{out_mp4.stem}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    log("Đang khởi tạo khung hình trường quay Cổ Phong cho Video Podcast...")
    artboards = create_podcast_artboards(
        card_img_path=Path(card_image_path) if card_image_path else None,
        hexagram_title=hexagram_title,
        podcast_title=podcast_title,
        output_dir=temp_dir,
        aspect_ratio=aspect_ratio
    )

    base_png = artboards["base_path"]
    host_active_png = artboards["host_active_path"]
    master_active_png = artboards["master_active_path"]

    # Load timeline to build active speaker enable conditions
    timeline = []
    if Path(timeline_path).exists():
        with open(timeline_path, "r", encoding="utf-8") as f:
            timeline = json.load(f)

    host_intervals = []
    master_intervals = []
    for item in timeline:
        s = item["start_time"]
        e = item["end_time"]
        if item["speaker"] == "host":
            host_intervals.append(f"between(t,{s},{e})")
        else:
            master_intervals.append(f"between(t,{s},{e})")

    host_enable_expr = "+".join(host_intervals) if host_intervals else "0"
    master_enable_expr = "+".join(master_intervals) if master_intervals else "0"

    # Escape subtitle path for FFmpeg
    ass_escaped = str(Path(ass_subtitle_path).resolve()).replace("\\", "/").replace(":", "\\:")

    is_16_9 = (aspect_ratio == "16:9")
    w = 1920 if is_16_9 else 1080
    h = 1080 if is_16_9 else 1920

    log("Đang tổng hợp đồ họa, sóng âm thanh động & phụ đề Full HD...")

    # Build FFmpeg filter_complex
    # Inputs:
    # 0: base_png
    # 1: host_active_png
    # 2: master_active_png
    # 3: audio_mp3
    if is_16_9:
        wave_w, wave_h = 1250, 110
        wave_x, wave_y = 590, 530
        h_x, h_y = 585, 145
        m_x, m_y = 585, 330
    else:
        wave_w, wave_h = 980, 120
        wave_x, wave_y = 50, 1205
        h_x, h_y = 50, 1040
        m_x, m_y = 50, 1040

    filter_complex = (
        f"[3:a]showwaves=s={wave_w}x{wave_h}:mode=line:colors=0xD4AF37@0.85:scale=sqrt[wave];"
        f"[0:v][wave]overlay=x={wave_x}:y={wave_y}:shortest=1[v1];"
        f"[v1][1:v]overlay=x={h_x}:y={h_y}:enable='{host_enable_expr}'[v2];"
        f"[v2][2:v]overlay=x={m_x}:y={m_y}:enable='{master_enable_expr}'[v3];"
        f"[v3]ass='{ass_escaped}'[vout]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-framerate", "25", "-i", str(base_png),
        "-i", str(host_active_png),
        "-i", str(master_active_png),
        "-i", str(audio_path),
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", "3:a",
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(out_mp4)
    ]

    t0 = time.time()
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        log(f"Lỗi render FFmpeg: {res.stderr[-400:]}")
        raise RuntimeError(f"FFmpeg render thất bại: {res.stderr[-300:]}")

    duration = time.time() - t0
    log(f"Hoàn tất dựng phim Podcast MP4 trong {duration:.1f}s! Kích thước: {out_mp4.stat().st_size // 1024} KB")

    # Clean up temp artboards
    try:
        for f in temp_dir.glob("*"):
            f.unlink()
        temp_dir.rmdir()
    except Exception:
        pass

    return {
        "success": True,
        "video_path": str(out_mp4),
        "video_filename": out_mp4.name,
        "render_time": duration
    }

if __name__ == "__main__":
    sample_card = ASSETS_DIR / "card_loi_son_tieu_qua.png"
    aud = "output/audio/test_podcast_engine.mp3"
    tl = "output/audio/test_podcast_engine_timeline.json"
    ass = "output/audio/test_podcast_engine.ass"
    out = "scratch/test_podcast_engine_video.mp4"

    res = render_podcast_video(
        card_image_path=str(sample_card),
        audio_path=aud,
        timeline_path=tl,
        ass_subtitle_path=ass,
        hexagram_title="QUẺ SỐ 3: THỦY LÔI TRUÂN",
        podcast_title="Bản Lĩnh Đội Đá Vươn Lên",
        output_video_path=out,
        aspect_ratio="16:9"
    )
    print("Render finished:", res)
