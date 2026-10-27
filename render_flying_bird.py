# -*- coding: utf-8 -*-
"""
VFX Renderer: Tạo hoạt ảnh Chim Thần (Phi Điểu) thoát ly khỏi lá bài Kinh Dịch (Lôi Sơn Tiểu Quá)
- Hiệu ứng Out-of-Bounds (OOB) 3D: Con chim từ tranh vẽ trong lá bài thức tỉnh, vỗ cánh,
  phá vỡ ranh giới 2D của thẻ bài, phóng to và bay vút ra không gian 3D phía trước màn hình.
- Vệt sao kim quang (Golden Stardust Particle Trail) rực rỡ uốn lượn theo sải cánh.
- Sóng xung kích kim sắc (Golden Shockwave) khi chim vượt qua viền lá bài.
- Xuất file video MP4 chuẩn 9:16 (720x1280, 30fps, H.264/AAC).
"""
import math
import os
import random
import subprocess
import sys
import time
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import cv2
import numpy as np
from PIL import Image

WIDTH = 720
HEIGHT = 1280
FPS = 30
DURATION = 5.0
TOTAL_FRAMES = int(FPS * DURATION) # 150 frames

CARD_PATH = Path("assets/card_loi_son_tieu_qua.png")
SOUND_PATH = Path("assets/singing_bowl.wav")
OUTPUT_VIDEO = Path("output/videos/card_bird_flying_out.mp4")


class Particle:
    def __init__(self, x, y, vx, vy, size, life, color):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.size = size
        self.max_life = life
        self.life = life
        self.color = color

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vx *= 0.94
        self.vy *= 0.94
        self.life -= 1

    def draw(self, img):
        if self.life <= 0:
            return
        alpha = self.life / self.max_life
        radius = max(1, int(self.size * alpha))
        c = (
            int(self.color[0] * alpha),
            int(self.color[1] * alpha),
            int(self.color[2] * alpha),
        )
        cv2.circle(img, (int(self.x), int(self.y)), radius, c, -1)
        # Glow halo
        if radius > 2:
            glow_c = (int(c[0] * 0.4), int(c[1] * 0.4), int(c[2] * 0.4))
            cv2.circle(img, (int(self.x), int(self.y)), radius * 2, glow_c, -1)


def draw_oriental_bird(canvas, cx, cy, scale, angle_deg, flap_phase, glow_strength=1.0):
    """
    Vẽ con chim thần phương Đông (Phi Điểu) với cánh vỗ nhịp nhàng và đuôi lụa mềm mại.
    """
    rad = math.radians(angle_deg)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)

    def rot(lx, ly):
        # Rotate around (0,0) and translate to (cx, cy)
        rx = lx * cos_a - ly * sin_a
        ry = lx * sin_a + ly * cos_a
        return int(cx + rx * scale), int(cy + ry * scale)

    # Flap calculation: -1 (wings down) to +1 (wings up)
    flap = math.sin(flap_phase)
    wing_span = 45.0
    wing_tip_y = -wing_span * flap

    # 1. Tail Feathers (3 flowing streaming ribbons)
    tail_pts_center = [rot(0, 0), rot(-25, 20), rot(-55, 35 + 8 * math.sin(flap_phase - 0.5)), rot(-90, 50 + 15 * math.sin(flap_phase - 1.0))]
    tail_pts_left = [rot(-5, 0), rot(-30, 10), rot(-65, 15 + 8 * math.sin(flap_phase - 0.7)), rot(-105, 25 + 15 * math.sin(flap_phase - 1.2))]
    tail_pts_right = [rot(5, 0), rot(-20, 28), rot(-50, 48 + 8 * math.sin(flap_phase - 0.3)), rot(-85, 70 + 15 * math.sin(flap_phase - 0.8))]

    for tpts, col, thick in [
        (tail_pts_left, (70, 190, 255), max(1, int(3 * scale))),
        (tail_pts_right, (70, 190, 255), max(1, int(3 * scale))),
        (tail_pts_center, (120, 230, 255), max(1, int(4 * scale))),
    ]:
        for i in range(len(tpts) - 1):
            cv2.line(canvas, tpts[i], tpts[i+1], col, thick, cv2.LINE_AA)

    # 2. Main Wings (Feathered layered wings)
    # Left Wing (facing upward in local space)
    lw_root = rot(-5, -5)
    lw_joint = rot(10, -wing_span * 0.55 * (1 + 0.3 * flap))
    lw_tip = rot(20, wing_tip_y - 25)
    lw_feather1 = rot(5, wing_tip_y - 12)
    lw_feather2 = rot(-10, wing_tip_y * 0.6)
    left_wing_poly = np.array([lw_root, lw_joint, lw_tip, lw_feather1, lw_feather2], dtype=np.int32)
    cv2.fillPoly(canvas, [left_wing_poly], (80, 200, 255), cv2.LINE_AA)

    # Right Wing (facing downward in local space)
    rw_root = rot(5, 5)
    rw_joint = rot(20, wing_span * 0.55 * (1 + 0.3 * flap))
    rw_tip = rot(30, -wing_tip_y + 25)
    rw_feather1 = rot(15, -wing_tip_y + 12)
    rw_feather2 = rot(0, -wing_tip_y * 0.6)
    right_wing_poly = np.array([rw_root, rw_joint, rw_tip, rw_feather1, rw_feather2], dtype=np.int32)
    cv2.fillPoly(canvas, [right_wing_poly], (80, 200, 255), cv2.LINE_AA)

    # 3. Bird Body & Head
    body_pts = [
        rot(28, 0),    # Beak tip
        rot(20, -6),   # Crown
        rot(8, -8),    # Upper back
        rot(-15, -4),  # Lower back
        rot(-25, 0),   # Tail base
        rot(-12, 6),   # Lower belly
        rot(10, 8),    # Chest
        rot(22, 4),    # Throat
    ]
    body_poly = np.array(body_pts, dtype=np.int32)
    cv2.fillPoly(canvas, [body_poly], (160, 235, 255), cv2.LINE_AA)

    # Bright golden rim highlights on wings
    cv2.polylines(canvas, [left_wing_poly], True, (200, 250, 255), max(1, int(2 * scale)), cv2.LINE_AA)
    cv2.polylines(canvas, [right_wing_poly], True, (200, 250, 255), max(1, int(2 * scale)), cv2.LINE_AA)

    # Eye of the bird
    eye_pos = rot(17, -2)
    cv2.circle(canvas, eye_pos, max(1, int(2 * scale)), (0, 0, 0), -1, cv2.LINE_AA)
    cv2.circle(canvas, eye_pos, max(1, int(1 * scale)), (255, 255, 255), -1, cv2.LINE_AA)

    # Return wingtips for particle spawning
    return [lw_tip, rw_tip, tpts[-1]]


def main():
    print(f"🎬 Bắt đầu tạo hoạt ảnh 3D Out-Of-Bounds: Chim Thần bay khỏi lá bài Kinh Dịch...")
    OUTPUT_VIDEO.parent.mkdir(parents=True, exist_ok=True)

    # 1. Load và chuẩn bị hình ảnh lá bài
    card_raw = Image.open(CARD_PATH).convert("RGBA")
    card_w, card_h = 460, int(460 * (card_raw.height / card_raw.width))
    card_resized = card_raw.resize((card_w, card_h), Image.Resampling.LANCZOS)
    card_np = np.array(card_resized) # RGBA

    # 2. Chuẩn bị nền mờ huyền mặc
    bg_raw = card_raw.resize((WIDTH, HEIGHT), Image.Resampling.BILINEAR)
    bg_np = cv2.cvtColor(np.array(bg_raw), cv2.COLOR_RGBA2BGR)
    bg_blurred = cv2.GaussianBlur(bg_np, (51, 51), 0)
    # Giảm sáng và tăng độ tương phản để làm nổi bật lá bài và chim
    bg_base = cv2.convertScaleAbs(bg_blurred, alpha=0.35, beta=10)

    # 3. Khởi tạo FFmpeg pipe stream
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-s", f"{WIDTH}x{HEIGHT}", "-pix_fmt", "bgr24", "-r", str(FPS),
        "-i", "-",
        "-i", str(SOUND_PATH.resolve()),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-t", str(DURATION),
        str(OUTPUT_VIDEO.resolve())
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    particles = []
    shockwaves = [] # [(cx, cy, radius, max_radius, alpha)]

    # Điểm xuất phát của con chim trong lá bài (tương đối theo tâm lá bài)
    # Ban đầu chim đậu/bay ở khu vực bầu trời quẻ
    start_x, start_y = WIDTH // 2 - 10, HEIGHT // 2 - 140

    start_time = time.time()

    for f in range(TOTAL_FRAMES):
        t = f / FPS # seconds

        # Tạo frame nền
        frame = bg_base.copy()

        # Thêm hiệu ứng sương mù và ánh sáng vũ trụ chuyển động
        mist_offset = int(math.sin(f * 0.05) * 15)
        fog_color = (int(15 + 8 * math.sin(f * 0.08)), int(18 + 10 * math.cos(f * 0.07)), int(30 + 12 * math.sin(f * 0.06)))
        cv2.rectangle(frame, (0, 0), (WIDTH, HEIGHT), fog_color, 1)

        # -------------------------------------------------------------
        # 1. RENDER CARD (Lá bài nổi bồng bềnh trong không gian)
        # -------------------------------------------------------------
        card_float_y = int(math.sin(f * 0.12) * 12)
        card_pos_x = (WIDTH - card_w) // 2
        card_pos_y = (HEIGHT - card_h) // 2 + card_float_y

        # Viền hào quang kim sắc của lá bài (Pulsating Golden Card Halo)
        halo_intensity = 0.5 + 0.3 * math.sin(f * 0.2)
        halo_pad = 8
        cv2.rectangle(
            frame,
            (card_pos_x - halo_pad, card_pos_y - halo_pad),
            (card_pos_x + card_w + halo_pad, card_pos_y + card_h + halo_pad),
            (int(60 * halo_intensity), int(160 * halo_intensity), int(220 * halo_intensity)),
            3,
            cv2.LINE_AA
        )

        # Dán lá bài lên frame (Alpha Blending)
        y1, y2 = max(0, card_pos_y), min(HEIGHT, card_pos_y + card_h)
        x1, x2 = max(0, card_pos_x), min(WIDTH, card_pos_x + card_w)
        cy1, cy2 = 0, y2 - y1
        cx1, cx2 = 0, x2 - x1

        card_rgb = cv2.cvtColor(card_np[cy1:cy2, cx1:cx2, :3], cv2.COLOR_RGB2BGR)
        card_alpha = card_np[cy1:cy2, cx1:cx2, 3] / 255.0
        for c in range(3):
            frame[y1:y2, x1:x2, c] = (
                card_alpha * card_rgb[:, :, c] + (1 - card_alpha) * frame[y1:y2, x1:x2, c]
            ).astype(np.uint8)

        # -------------------------------------------------------------
        # 2. TÍNH TOÁN QUỸ ĐẠO CỦA CON CHIM (Phá ranh giới bay ra ngoài)
        # -------------------------------------------------------------
        # Giai đoạn 1: t in [0.0, 1.2s] (f in 0..36): Chim thức tỉnh, ánh sáng tụ lại
        # Giai đoạn 2: t in [1.2, 2.4s] (f in 36..72): Cất cánh, lướt sà xuống lấy đà (Nghi hạ)
        # Giai đoạn 3: t in [2.4, 3.8s] (f in 72..114): Phá vỡ viền lá bài, bay vút lên 3D
        # Giai đoạn 4: t in [3.8, 5.0s] (f in 114..150): Bay sát ống kính và hướng tới chân trời mới

        progress = max(0.0, (f - 30) / (TOTAL_FRAMES - 30)) # 0.0 -> 1.0 từ frame 30 trở đi

        if f < 30:
            # Chim đang ở trong lá bài, phát sáng nhấp nháy chuẩn bị thức tỉnh
            bird_x = start_x + math.sin(f * 0.1) * 3
            bird_y = start_y + card_float_y + math.cos(f * 0.1) * 2
            bird_scale = 0.42
            bird_angle = -15.0 + math.sin(f * 0.15) * 5
            flap_speed = 0.2
            # Vòng hào quang tụ sáng trong tranh
            pulse_r = int(15 + 10 * math.sin(f * 0.3))
            cv2.circle(frame, (int(bird_x), int(bird_y)), pulse_r, (80, 200, 255), 2, cv2.LINE_AA)
        else:
            # Quỹ đạo hình sin lượn sóng động học (3D S-Curve Flight)
            p = progress
            # X: Từ giữa sang trái nhẹ rồi lượn vút sang phải màn hình
            bird_x = start_x + 360 * (p ** 1.3) * math.sin(p * math.pi * 0.9) - 60 * math.sin(p * math.pi * 2)
            # Y: Hạ xuống lấy đà (Dịch lý: Nghi hạ), sau đó bay vút lên trời cao (Vượt ranh giới)
            if p < 0.35:
                bird_y = start_y + card_float_y + 110 * math.sin(p / 0.35 * (math.pi / 2))
            else:
                p_up = (p - 0.35) / 0.65
                bird_y = (start_y + card_float_y + 110) - 750 * (p_up ** 1.4)

            # Scale: Phóng to từ 0.45x (bên trong tranh) -> 1.2x (thoát khỏi thẻ) -> 2.8x (sát mắt người xem)
            bird_scale = 0.42 + 2.4 * (p ** 1.5)

            # Angle: Góc nghiêng theo hướng bay
            bird_angle = -20.0 + 35 * math.sin(p * math.pi * 1.5) - 45 * p
            flap_speed = 0.75

            # Kích hoạt sóng xung kích khi con chim vượt qua mép thẻ bài (quanh frame 72)
            if f == 72:
                shockwaves.append({"x": bird_x, "y": bird_y, "r": 10, "max_r": 180, "alpha": 1.0})

        # Cập nhật & vẽ Shockwaves
        for sw in shockwaves:
            sw["r"] += 8
            sw["alpha"] = max(0.0, 1.0 - (sw["r"] / sw["max_r"]))
            if sw["alpha"] > 0:
                col = (int(80 * sw["alpha"]), int(200 * sw["alpha"]), int(255 * sw["alpha"]))
                cv2.circle(frame, (int(sw["x"]), int(sw["y"])), int(sw["r"]), col, max(1, int(3 * sw["alpha"])), cv2.LINE_AA)
        shockwaves = [sw for sw in shockwaves if sw["alpha"] > 0]

        # -------------------------------------------------------------
        # 3. RENDER VỆT HÀO QUANG & HẠT SAO KIM (Particle Trail)
        # -------------------------------------------------------------
        flap_phase = f * flap_speed

        # Tạo layer riêng để vẽ chim và hào quang
        bird_layer = np.zeros_like(frame)
        tips = draw_oriental_bird(bird_layer, bird_x, bird_y, bird_scale, bird_angle, flap_phase)

        # Sinh hạt bụi vàng từ đầu cánh và đuôi chim khi bay
        if f >= 30:
            for tip in tips:
                for _ in range(2):
                    vx = -math.cos(math.radians(bird_angle)) * random.uniform(2, 6) + random.uniform(-1.5, 1.5)
                    vy = -math.sin(math.radians(bird_angle)) * random.uniform(2, 6) + random.uniform(-1.5, 1.5)
                    particles.append(Particle(
                        tip[0], tip[1], vx, vy,
                        size=random.uniform(2.5, 5.0) * bird_scale,
                        life=random.randint(15, 30),
                        color=random.choice([(70, 200, 255), (120, 240, 255), (200, 255, 255), (50, 150, 240)])
                    ))

        # Cập nhật & vẽ hạt
        for pt in particles:
            pt.update()
            pt.draw(frame)
        particles = [pt for pt in particles if pt.life > 0]

        # Áp dụng hiệu ứng phát quang (Bloom/Glow) cho con chim
        glow = cv2.GaussianBlur(bird_layer, (31, 31), 0)
        frame = cv2.add(frame, glow)
        frame = cv2.add(frame, bird_layer)

        # -------------------------------------------------------------
        # 4. THÔNG TIN TIÊU ĐỀ THƯ PHÁP TRANG NHÃ (Dưới đáy màn hình)
        # -------------------------------------------------------------
        text_alpha = min(1.0, f / 40.0)
        overlay_txt = frame.copy()
        cv2.putText(
            overlay_txt, "QUẺ 62: LÔI SƠN TIỂU QUÁ",
            (WIDTH // 2 - 200, HEIGHT - 75),
            cv2.FONT_HERSHEY_TRIPLEX, 0.75, (210, 235, 255), 2, cv2.LINE_AA
        )
        cv2.putText(
            overlay_txt, "PHI ĐIỀU DI CHI ÂM • TỰ DO THOÁT KHỎI KHUÔN KHỔ",
            (WIDTH // 2 - 220, HEIGHT - 45),
            cv2.FONT_HERSHEY_SIMPLEX, 0.48, (140, 190, 230), 1, cv2.LINE_AA
        )
        cv2.addWeighted(overlay_txt, text_alpha, frame, 1 - text_alpha, 0, frame)

        # Đẩy frame vào FFmpeg
        proc.stdin.write(frame.tobytes())

        if f % 30 == 0 or f == TOTAL_FRAMES - 1:
            pct = int(f / TOTAL_FRAMES * 100)
            print(f"[VFX Breakout] Đang dựng phân cảnh: {pct}% ({f}/{TOTAL_FRAMES} frames)...")

    proc.stdin.close()
    proc.wait()

    total_render_time = round(time.time() - start_time, 2)
    print(f"✅ Hoàn tất render video trong {total_render_time}s!")
    print(f"MEDIA: {OUTPUT_VIDEO.resolve()}")
    print(f"File size: {OUTPUT_VIDEO.stat().st_size} bytes")


if __name__ == "__main__":
    main()
