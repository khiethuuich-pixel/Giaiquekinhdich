import subprocess
import os
import sys
import re
import time
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from config import VIDEOS_DIR, VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS
from sound_fx import ensure_singing_bowl
from voice_engine import get_audio_duration

def is_valid_card(crop_img) -> bool:
    """
    Check if a cropped region is an actual card with artwork and text,
    or just empty divination mat / grid tiles.
    """
    if crop_img is None or crop_img.size == 0:
        return False
    if len(crop_img.shape) == 3:
        gray = cv2.cvtColor(crop_img, cv2.COLOR_BGR2GRAY)
    else:
        gray = crop_img
    std = float(np.std(gray))
    edges = cv2.Canny(gray, 30, 100)
    edge_ratio = float(np.count_nonzero(edges)) / float(edges.size)
    return std > 20.0 and edge_ratio > 0.015


def _order_grid_cards_by_spread_geometry(detected: list[tuple[int, int, int, int]], w: int, h: int) -> list[tuple[int, int, int, int]]:
    """
    Map detected bounding boxes `(x1, y1, x2, y2)` to the exact canonical card order `1 .. N`
    used by IChingTarot spreads:
    - 7 cards (Trận Pháp Thất Tinh Bắc Đẩu):
      Top (1 card) = Lá 4
      Middle row (3 cards L->R) = Lá 2, Lá 3, Lá 5
      Bottom row (3 cards L->R) = Lá 7, Lá 1, Lá 6
      -> Returns [Lá 1, Lá 2, Lá 3, Lá 4, Lá 5, Lá 6, Lá 7]
    - 10 cards (Trận Pháp Thập Tinh):
      Sorted by X center into 5 columns:
      idx 0 (Col 1) = Lá 10
      idx 1..3 (Col 2, sorted by Y) = Lá 7, Lá 8, Lá 9
      idx 4 (Col 3) = Lá 2
      idx 5..7 (Col 4, sorted by Y) = Lá 4, Lá 1, Lá 3
      idx 8..9 (Col 5, sorted by Y) = Lá 5, Lá 6
      -> Returns [Lá 1 .. Lá 10]
    - Tháp La (3..8 cards in 2 rows where leftmost column has Quẻ Chủ top & Quẻ Biến bottom):
      -> Returns [Quẻ Chủ, Hào 1, Hào 2, ..., Quẻ Biến]
    """
    n = len(detected)
    cx = lambda b: (b[0] + b[2]) / 2.0
    cy = lambda b: (b[1] + b[3]) / 2.0

    if n == 7:
        # Check if this 7-card spread is Tháp La (leftmost column has 2 cards vertically aligned: Quẻ Chủ top, Quẻ Biến bottom)
        by_x_7 = sorted(detected, key=cx)
        min_cx_7 = cx(by_x_7[0])
        col0_7 = [b for b in detected if abs(cx(b) - min_cx_7) < w * 0.12]
        if len(col0_7) == 2:
            col0_sorted = sorted(col0_7, key=cy)  # [Quẻ Chủ (top), Quẻ Biến (bottom)]
            rest_7 = [b for b in detected if b not in col0_7]
            rest_sorted = sorted(rest_7, key=lambda b: (int(cy(b) > h * 0.5), cx(b)))
            return [col0_sorted[0]] + rest_sorted + [col0_sorted[1]]

        # Otherwise 7 cards = Trận Pháp Thất Tinh Bắc Đẩu (1 top card, 3 middle cards, 3 bottom cards)
        by_y = sorted(detected, key=cy)
        c4 = by_y[0]
        mid_3 = sorted(by_y[1:4], key=cx)  # [Lá 2, Lá 3, Lá 5]
        bot_3 = sorted(by_y[4:7], key=cx)  # [Lá 7, Lá 1, Lá 6]
        c2, c3, c5 = mid_3[0], mid_3[1], mid_3[2]
        c7, c1, c6 = bot_3[0], bot_3[1], bot_3[2]
        return [c1, c2, c3, c4, c5, c6, c7]

    if n == 10:
        by_x = sorted(detected, key=cx)
        c10 = by_x[0]
        col2 = sorted(by_x[1:4], key=cy)   # [Lá 7, Lá 8, Lá 9]
        c7, c8, c9 = col2[0], col2[1], col2[2]
        c2 = by_x[4]
        col4 = sorted(by_x[5:8], key=cy)   # [Lá 4, Lá 1, Lá 3]
        c4, c1, c3 = col4[0], col4[1], col4[2]
        col5 = sorted(by_x[8:10], key=cy)  # [Lá 5, Lá 6]
        c5, c6 = col5[0], col5[1]
        return [c1, c2, c3, c4, c5, c6, c7, c8, c9, c10]

    # Check if this is a 2-row layout (e.g. Tháp La where Col 0 has Quẻ Chủ on top & Quẻ Biến on bottom, or 5-card mobile)
    by_x = sorted(detected, key=cx)
    if n >= 3:
        min_cx = cx(by_x[0])
        col0 = [b for b in detected if abs(cx(b) - min_cx) < w * 0.12]
        rest = [b for b in detected if b not in col0]
        if len(col0) == 2:
            col0_sorted = sorted(col0, key=cy)  # [Quẻ Chủ (top), Quẻ Biến (bottom)]
            rest_sorted = sorted(rest, key=lambda b: (int(cy(b) > h * 0.5), cx(b)))
            return [col0_sorted[0]] + rest_sorted + [col0_sorted[1]]

    # Default: top-to-bottom bands, then left-to-right
    return sorted(detected, key=lambda b: (int(cy(b) // (h / 3.2)), cx(b)))


def extract_cards_from_spread(spread_img_path: Path, output_dir: Path) -> list[Path]:
    """
    Extract individual isolated card images from any spread screenshot in EXACT 1..N divination order.
    Supports 1-card, 2-card (horizontal & vertical), 3-card, 5-card, 7-card (Thất Tinh), 10-card (Thập Tinh), and Tháp La spreads.
    Returns list of paths to cropped card images.
    """
    spread_img_path = Path(spread_img_path).resolve()
    im = Image.open(spread_img_path)
    w, h = im.size
    ratio = w / h
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = spread_img_path.stem

    cv_img = cv2.imread(str(spread_img_path))
    if cv_img is None:
        p = output_dir / f"{stem}_card_1.png"
        im.save(p)
        return [p]

    # Background color estimation from corners
    corner_samples = np.concatenate([
        cv_img[:20, :20].reshape(-1, 3),
        cv_img[:20, -20:].reshape(-1, 3),
        cv_img[-20:, :20].reshape(-1, 3),
        cv_img[-20:, -20:].reshape(-1, 3)
    ], axis=0)
    bg = np.median(corner_samples, axis=0)
    diff = np.linalg.norm(cv_img.astype(np.float32) - bg, axis=2)

    card_boxes = []

    if ratio >= 2.40:
        # Case 1: 5-card horizontal spread (Ngũ Hành Tương Sinh: 1 -> 5 left-to-right)
        cw = int(w * 0.165)
        y1 = int(h * 0.05)
        y2 = int(h * 0.95)
        centers_x = [0.133, 0.313, 0.494, 0.674, 0.854]
        for cx in centers_x:
            card_boxes.append((int(cx*w - cw//2), y1, int(cx*w + cw//2), y2))

    elif ratio >= 1.30 and h < 1100:
        center_strip = diff[:, int(w * 0.46):int(w * 0.54)]
        center_active = np.mean(center_strip > 30)

        if center_active < 0.10:
            # Case 2: 2-card horizontal spread (Thể - Dụng / Âm Dương)
            cw = int(w * 0.36)
            y1 = int(h * 0.05)
            y2 = int(h * 0.95)
            card_boxes.append((int(0.22*w - cw//2), y1, int(0.22*w + cw//2), y2))
            card_boxes.append((int(0.78*w - cw//2), y1, int(0.78*w + cw//2), y2))
        else:
            # Case 3: 3-card horizontal spread (Tam Tài: 1 -> 2 -> 3 left-to-right)
            mask = (diff > 35).astype(np.uint8) * 255
            cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            detected_3 = []
            for c in cnts:
                x, y, cw_c, ch_c = cv2.boundingRect(c)
                if cw_c > w * 0.10 and ch_c > h * 0.20:
                    pad_x = int(cw_c * 0.02)
                    pad_y = int(ch_c * 0.02)
                    detected_3.append((max(0, x - pad_x), max(0, y - pad_y), min(w, x + cw_c + pad_x), min(h, y + ch_c + pad_y)))
            if len(detected_3) == 3:
                card_boxes = sorted(detected_3, key=lambda b: b[0])
            else:
                cw = int(w * 0.28)
                y1 = int(h * 0.05)
                y2 = int(h * 0.95)
                centers_x = [0.165, 0.50, 0.835]
                for cx in centers_x:
                    card_boxes.append((int(cx*w - cw//2), y1, int(cx*w + cw//2), y2))

    elif ratio < 0.65 and h > 1500:
        # Case 4: 2-card vertical spread (Quẻ Chủ top, Quẻ Biến bottom)
        cw = int(w * 0.66)
        ch = int(h * 0.44)
        card_boxes.append((int(0.50 * w - cw // 2), int(0.28 * h - ch // 2), int(0.50 * w + cw // 2), int(0.28 * h + ch // 2)))
        card_boxes.append((int(0.50 * w - cw // 2), int(0.74 * h - ch // 2), int(0.50 * w + cw // 2), int(0.74 * h + ch // 2)))

    elif 0.65 <= ratio <= 1.65 and (w > 900 or h > 900):
        # Case 5: Multi-card Grid Spreads: Tháp La (3..7 cards), Thất Tinh (7 cards), Thập Tinh (10 cards)
        mask = (diff > 35).astype(np.uint8) * 255
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        detected = []
        for c in cnts:
            x, y, cw_c, ch_c = cv2.boundingRect(c)
            # Filter out tiny top badges so we detect the main card bodies, then expand upward to include the top badge!
            if cw_c > w * 0.08 and ch_c > h * 0.14 and (cw_c * ch_c) > (w * h * 0.015):
                pad_x = int(cw_c * 0.02)
                pad_top = int(ch_c * 0.105)  # Include position badge (e.g. "1. Quá Khứ") cleanly without bleeding into card above
                pad_bot = int(ch_c * 0.015)
                detected.append((
                    max(0, x - pad_x),
                    max(0, y - pad_top),
                    min(w, x + cw_c + pad_x),
                    min(h, y + ch_c + pad_bot)
                ))

        if len(detected) >= 2:
            card_boxes = _order_grid_cards_by_spread_geometry(detected, w, h)
        else:
            cw_tl = int(w * 0.27)
            ch_tl = int(h * 0.40)
            tl_positions = [
                (int(0.21 * w), int(0.28 * h)),
                (int(0.50 * w), int(0.28 * h)),
                (int(0.79 * w), int(0.28 * h)),
                (int(0.50 * w), int(0.72 * h)),
                (int(0.79 * w), int(0.72 * h)),
                (int(0.21 * w), int(0.72 * h)),
            ]
            card_boxes = [(cx - cw_tl//2, cy - ch_tl//2, cx + cw_tl//2, cy + ch_tl//2) for cx, cy in tl_positions]
    else:
        # Case 6: 1-card spread (Đơn Quẻ Chí Tôn)
        mask = (diff > 30).astype(np.uint8) * 255
        active_y = np.where(np.sum(mask, axis=1) > w * 0.08)[0]
        active_x = np.where(np.sum(mask, axis=0) > h * 0.08)[0]
        if len(active_y) > 0 and len(active_x) > 0:
            pad_x = int(w * 0.02)
            pad_y = int(h * 0.02)
            card_boxes.append((
                int(max(0, active_x[0] - pad_x)),
                int(max(0, active_y[0] - pad_y)),
                int(min(w, active_x[-1] + pad_x)),
                int(min(h, active_y[-1] + pad_y))
            ))
        else:
            card_boxes.append((0, 0, w, h))

    # Strict Validation: Save in exact card_boxes order (1 .. N)
    out_paths = []
    valid_boxes = []
    card_idx = 1
    for (x1, y1, x2, y2) in card_boxes:
        x1_c = max(0, min(w - 1, x1))
        y1_c = max(0, min(h - 1, y1))
        x2_c = max(x1_c + 1, min(w, x2))
        y2_c = max(y1_c + 1, min(h, y2))
        crop_cv = cv_img[y1_c:y2_c, x1_c:x2_c]
        if is_valid_card(crop_cv):
            overlap = False
            for (ex1, ey1, ex2, ey2) in valid_boxes:
                ix1, iy1 = max(x1_c, ex1), max(y1_c, ey1)
                ix2, iy2 = min(x2_c, ex2), min(y2_c, ey2)
                if ix2 > ix1 and iy2 > iy1:
                    inter_area = (ix2 - ix1) * (iy2 - iy1)
                    box_area = (x2_c - x1_c) * (y2_c - y1_c)
                    if inter_area / max(1, box_area) > 0.45:
                        overlap = True
                        break
            if not overlap:
                valid_boxes.append((x1_c, y1_c, x2_c, y2_c))
                cropped = im.crop((x1_c, y1_c, x2_c, y2_c))
                p = output_dir / f"{stem}_card_{card_idx}.png"
                cropped.save(p)
                out_paths.append(p)
                card_idx += 1
        else:
            print(f"[VideoEngine] Bỏ qua vùng trống không có lá bài tại ({x1},{y1}) -> ({x2},{y2})")

    if not out_paths:
        p = output_dir / f"{stem}_card_1.png"
        im.save(p)
        out_paths.append(p)

    return out_paths


def render_vertical_video(
    card_image_path: str,
    voice_audio_path: str,
    ass_subtitle_path: str,
    question: str,
    hexagram_title: str,
    output_video_path: str,
    section_timings: dict = None,
    ordered_card_paths: list[str] = None,
    log_cb=None
) -> dict:
    """
    Render a high-end 9:16 vertical video (1080x1920) synchronized 100% with the hexagram & cards being interpreted:
    - PHẦN 1 (Intro): Hiển thị Toàn Cảnh Trận Pháp đúng bằng thời lượng đọc Phần 1 (`t_intro`).
    - PHẦN 2 (Từng Lá Bài 1 -> N): Khi giọng đọc chuyển sang Lá k, video lập tức chuyển cận cảnh đúng Lá k (`seg_card_k.mp4`)
      với thời lượng khớp chính xác tới từng mili-giây (`t_cards[k-1]`).
    - PHẦN 3 & 4 (Outro): Khi giọng đọc chuyển sang Phần 3 & 4, video quay lại Toàn Cảnh Trận Pháp (`t_outro`).
    """
    def log(msg):
        if log_cb:
            log_cb(msg)
        print(f"[VideoEngine] {msg}")

    card_img_raw = Path(card_image_path).resolve()
    voice_audio = Path(voice_audio_path).resolve()
    ass_sub = Path(ass_subtitle_path).resolve()
    out_video = Path(output_video_path).resolve()
    bell_audio = ensure_singing_bowl().resolve()

    out_video.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = out_video.parent / f"temp_{out_video.stem}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    with Image.open(card_img_raw) as im:
        raw_w, raw_h = im.size
    ratio = raw_w / raw_h

    duration = get_audio_duration(str(voice_audio))
    log(f"Thời lượng audio: {duration:.1f}s | Kích thước quẻ: {raw_w}x{raw_h} (Tỷ lệ: {ratio:.2f})")

    # Clean old segment files in temp_dir
    for old_f in temp_dir.glob("*.mp4"):
        try:
            old_f.unlink()
        except Exception:
            pass
    for old_p in temp_dir.glob("*_card_*.png"):
        try:
            old_p.unlink()
        except Exception:
            pass

    # 3. Use ordered_card_paths if provided from Homepage DOM, otherwise extract in canonical 1..N order
    if ordered_card_paths and all(Path(p).exists() for p in ordered_card_paths):
        card_paths = [Path(p).resolve() for p in ordered_card_paths]
        num_cards = len(card_paths)
        log(f"Sử dụng {num_cards} ảnh lá bài theo đúng thứ tự 1 -> {num_cards} trực tiếp từ Trang Chủ.")
    else:
        log("Đang trích xuất chi tiết từng lá bài theo đúng thứ tự cung vị 1 -> N...")
        card_paths = extract_cards_from_spread(card_img_raw, temp_dir)
        num_cards = len(card_paths)
        log(f"Đã định vị và sắp xếp chuẩn xác {num_cards} lá bài (Lá 1 -> Lá {num_cards}).")

    # 4. Calculate exact timing per segment (synchronized with TTS sections if available + tail buffer so AI finishes reading 100%)
    fps = VIDEO_FPS
    tail_pad_sec = 2.2
    total_vid_dur = duration + tail_pad_sec
    if (
        section_timings
        and isinstance(section_timings.get("t_cards"), list)
        and len(section_timings["t_cards"]) == num_cards
    ):
        t_intro = max(0.0, float(section_timings.get("t_intro", 0.0)))
        t_cards_list = [max(1.2, float(x) + 0.25) for x in section_timings["t_cards"]]
        t_outro = max(1.8, float(section_timings.get("t_outro", 0.0)) + tail_pad_sec)
        total_vid_dur = max(total_vid_dur, t_intro + sum(t_cards_list) + t_outro)
        log(
            f"Đồng bộ thời gian chuẩn 100% theo giọng đọc (+đệm dư cuối): Intro={t_intro:.2f}s | "
            f"Lá 1..{num_cards}={[round(x, 2) for x in t_cards_list]} | Outro={t_outro:.2f}s"
        )
    else:
        t_intro = min(4.5, duration * 0.14)
        t_outro = min(6.5, duration * 0.16) + tail_pad_sec
        t_rem = max(1.0, total_vid_dur - t_intro - t_outro)
        t_per = t_rem / max(1, num_cards)
        t_cards_list = [t_per] * num_cards

    # Strip any Chinese characters (Hanzi) from question before displaying on video
    clean_q_vi = re.sub(r'[\u2e80-\u2eff\u3000-\u303f\u3400-\u4dbf\u4dc0-\u4dff\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef]+', ' ', question)
    safe_q = re.sub(r'[\':"\\;`]', '', clean_q_vi)
    safe_q = re.sub(r'\s+', ' ', safe_q).strip()
    if len(safe_q) > 46:
        safe_q = safe_q[:43] + "..."

    log(f"Bắt đầu dựng chuỗi cận cảnh đồng bộ 100% cho quẻ: {hexagram_title}...")

    try:
        segment_files = []

        # A. Render Intro Segment (Spread Overview during PHẦN 1)
        if t_intro >= 0.4:
            intro_file = temp_dir / "seg_00_intro.mp4"
            f_intro = max(12, int(round(t_intro * fps)))
            z_intro = f"1.00+0.04*(on/{f_intro})"
            vf_intro = (
                f"scale=w=840:h=1260:force_original_aspect_ratio=decrease,"
                f"pad=840:1260:(840-iw)/2:(1260-ih)/2:color=0x00000000,"
                f"zoompan=z='{z_intro}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=840x1260:fps={fps}"
            )
            cmd_intro = [
                'ffmpeg', '-y', '-loglevel', 'error',
                '-loop', '1', '-framerate', str(fps), '-t', f"{t_intro:.3f}", '-i', str(card_img_raw),
                '-vf', vf_intro,
                '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p',
                str(intro_file)
            ]
            subprocess.run(cmd_intro, check=True)
            segment_files.append(intro_file)

        # B. Render Each Card Segment (Card 1 .. Card N synced to exact duration t_cards_list[idx])
        for idx, cp in enumerate(card_paths):
            t_this_card = t_cards_list[idx] if idx < len(t_cards_list) else (duration / max(1, num_cards))
            log(f"Đang dựng cảnh cận cảnh Lá bài {idx+1}/{num_cards} ({t_this_card:.1f}s · Ken Burns HD)...")
            f_total_card = max(15, int(round(t_this_card * fps)))
            z_card = f"1.00+0.07*(on/{f_total_card})"
            x_card = "iw/2-(iw/zoom/2)"
            y_card = "ih/2-(ih/zoom/2)"
            vf_card = (
                f"scale=w=840:h=1200:force_original_aspect_ratio=decrease,"
                f"pad=840:1260:(840-iw)/2:(1260-ih)/2:color=0x00000000,"
                f"zoompan=z='{z_card}':x='{x_card}':y='{y_card}':d=1:s=840x1260:fps={fps},"
                f"unsharp=3:3:0.4:3:3:0.0"
            )
            seg_file = temp_dir / f"seg_card_{idx+1}.mp4"
            cmd_card = [
                'ffmpeg', '-y', '-loglevel', 'error',
                '-loop', '1', '-framerate', str(fps), '-t', f"{t_this_card:.3f}", '-i', str(cp),
                '-vf', vf_card,
                '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p',
                str(seg_file)
            ]
            subprocess.run(cmd_card, check=True)
            segment_files.append(seg_file)

        # C. Render Outro Segment (Spread Overview during PHẦN 3 & PHẦN 4)
        if t_outro >= 0.4:
            log("Đang dựng cảnh kết toàn cảnh trận pháp (Phần 3 & 4)...")
            outro_file = temp_dir / "seg_99_outro.mp4"
            f_outro = max(12, int(round(t_outro * fps)))
            z_outro = f"1.04-0.04*(on/{f_outro})"
            vf_outro = (
                f"scale=w=840:h=1260:force_original_aspect_ratio=decrease,"
                f"pad=840:1260:(840-iw)/2:(1260-ih)/2:color=0x00000000,"
                f"zoompan=z='{z_outro}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=840x1260:fps={fps}"
            )
            cmd_outro = [
                'ffmpeg', '-y', '-loglevel', 'error',
                '-loop', '1', '-framerate', str(fps), '-t', f"{t_outro:.3f}", '-i', str(card_img_raw),
                '-vf', vf_outro,
                '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p',
                str(outro_file)
            ]
            subprocess.run(cmd_outro, check=True)
            segment_files.append(outro_file)

        # D. Concat Card Track
        concat_txt = temp_dir / "concat_list.txt"
        with open(concat_txt, "w", encoding="utf-8") as f:
            for sf in segment_files:
                f.write(f"file '{sf.as_posix()}'\n")

        concat_video = temp_dir / "cards_track.mp4"
        cmd_concat = [
            'ffmpeg', '-y', '-loglevel', 'error',
            '-f', 'concat', '-safe', '0', '-i', str(concat_txt),
            '-c', 'copy',
            str(concat_video)
        ]
        subprocess.run(cmd_concat, check=True)

        # E. Final Composition
        work_dir = ass_sub.parent
        sub_rel_name = ass_sub.name
        bg_banner_png = temp_dir / "bg_banner.png"

        filter_bg_static = (
            f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
            f"boxblur=30:5,eq=brightness=-0.35:saturation=1.2"
        )
        cmd_bg_static = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(card_img_raw),
            "-vf", filter_bg_static,
            "-frames:v", "1",
            str(bg_banner_png)
        ]
        subprocess.run(cmd_bg_static, check=True)

        # Render 100% crisp Vietnamese TrueType typography onto bg_banner_png via Pillow
        try:
            with Image.open(bg_banner_png).convert("RGBA") as bg_im:
                draw = ImageDraw.Draw(bg_im)
                font_candidates_bold = [
                    "C:/Windows/Fonts/segoeuib.ttf",
                    "C:/Windows/Fonts/timesbd.ttf",
                    "C:/Windows/Fonts/arialbd.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                ]
                font_candidates_reg = [
                    "C:/Windows/Fonts/segoeui.ttf",
                    "C:/Windows/Fonts/times.ttf",
                    "C:/Windows/Fonts/arial.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                ]
                font_title = None
                font_q = None
                for fp in font_candidates_bold:
                    if os.path.exists(fp):
                        font_title = ImageFont.truetype(fp, 44)
                        break
                for fp in font_candidates_reg:
                    if os.path.exists(fp):
                        font_q = ImageFont.truetype(fp, 34)
                        break
                if font_title is None:
                    font_title = ImageFont.load_default()
                if font_q is None:
                    font_q = ImageFont.load_default()

                title_txt = "KINH DỊCH CHIÊM BỐC"
                q_txt = f"Hỏi: {safe_q}" if safe_q else "Luận Giải Quẻ Kinh Dịch"

                tb1 = draw.textbbox((0, 0), title_txt, font=font_title)
                tw1 = tb1[2] - tb1[0]
                draw.text(((1080 - tw1) / 2, 152), title_txt, font=font_title, fill=(212, 175, 55, 255))

                tb2 = draw.textbbox((0, 0), q_txt, font=font_q)
                tw2 = tb2[2] - tb2[0]
                draw.text(((1080 - tw2) / 2, 218), q_txt, font=font_q, fill=(229, 221, 203, 255))

                bg_im.convert("RGB").save(bg_banner_png)
        except Exception as font_err:
            log(f"Cảnh báo vẽ tiêu đề tiếng Việt bằng Pillow: {font_err}")

        filter_composite = (
            f"[0:v][1:v]overlay=(W-w)/2:(H-h)/2-30[v1];"
            f"[v1]subtitles={sub_rel_name}[vout];"
            f"[2:a][3:a]amix=inputs=2:duration=first:weights=1.2 0.35[aout]"
        )

        cmd_final = [
            "ffmpeg", "-y",
            "-loglevel", "error",
            "-loop", "1", "-framerate", str(fps), "-t", f"{total_vid_dur:.3f}", "-i", str(bg_banner_png),
            "-i", str(concat_video),
            "-i", str(voice_audio),
            "-i", str(bell_audio),
            "-filter_complex", filter_composite,
            "-map", "[vout]",
            "-map", "[aout]",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "21",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-t", f"{total_vid_dur:.3f}",
            str(out_video)
        ]

        log("Đang xuất bản video hoàn thiện đồng bộ 100% với phụ đề và âm thanh...")
        res = subprocess.run(cmd_final, cwd=str(work_dir), stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if res.returncode != 0:
            err_msg = res.stderr.decode("utf-8", errors="ignore")
            log(f"Lỗi FFmpeg: {err_msg[-400:]}")
            raise RuntimeError(f"FFmpeg render thất bại: {err_msg[-300:]}")

    except Exception as e:
        log(f"Lỗi trong quá trình render động: {e}. Đang thực hiện phương án fallback nhanh...")
        filter_fallback = (
            f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=30:5,eq=brightness=-0.35:saturation=1.2[bg];"
            f"[0:v]scale=920:-1,zoompan=z='1.10+0.03*sin(on/15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=920x1300:fps={fps}[card];"
            f"[bg][card]overlay=(W-w)/2:(H-h)/2-30[v1];"
            f"[v1]drawtext=text='KINH DỊCH CHIÊM BỐC':font='Segoe UI':fontsize=42:fontcolor=#D4AF37:x=(w-text_w)/2:y=160[v2];"
            f"[v2]drawtext=text='Hỏi\\: {safe_q}':font='Segoe UI':fontsize=34:fontcolor=#E5DDCB:x=(w-text_w)/2:y=230[v3];"
            f"[v3]subtitles={ass_sub.name}[vout];"
            f"[1:a][2:a]amix=inputs=2:duration=first:weights=1.2 0.35[aout]"
        )
        cmd_fallback = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-loop", "1", "-t", f"{duration:.3f}", "-i", str(card_img_raw),
            "-i", str(voice_audio),
            "-i", str(bell_audio),
            "-filter_complex", filter_fallback,
            "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-t", f"{duration:.3f}",
            str(out_video)
        ]
        subprocess.run(cmd_fallback, cwd=str(ass_sub.parent), check=True)

    file_size_mb = out_video.stat().st_size / (1024 * 1024)
    log(f"Xuất video cận cảnh động thành công: {out_video.name} ({file_size_mb:.2f} MB)")

    return {
        "success": True,
        "video_path": str(out_video),
        "file_size_mb": file_size_mb
    }
