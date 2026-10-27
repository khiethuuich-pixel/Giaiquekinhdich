---
name: call-veo-3.1
description: >-
  Use this skill when the user wants to invoke, automate, or generate videos using Google Veo 3.1 (veo-3.1-generate-preview and veo-3.1-fast-generate-preview) in Gemini API via Python SDK or CLI scripts (Text-to-Video, Image-to-Video, and Frame Interpolation).
---

# Google Veo 3.1 (`generate-videos-veo-3.1`) Safe Execution & Automation Skill

Skill này cung cấp bộ script Python điều phối an toàn và chuẩn hóa cho **Google Veo 3.1 (Gemini API Video Generation - `veo-3.1-generate-preview` và `veo-3.1-fast-generate-preview`)**, giúp tự động hóa tạo video từ văn bản (`Text-to-Video`), làm chuyển động ảnh tĩnh (`Image-to-Video`), và nội suy khung hình (`Frame Interpolation`) trên Windows và Antigravity.

---

## 1. Cơ Chế Điều Phối Đa Tầng & Bảo Vệ An Toàn (BSS Hardened & Zero-Blocker)

> [!IMPORTANT]
> **Tối ưu hóa toàn diện quy trình tạo video AI với Veo 3.1:**
> 1. **Hai mô hình Veo 3.1 chuyên biệt (`--model`):**
>    - **`veo-3.1-generate-preview` (Cinematic Quality):** Tạo video độ chi tiết cao, ánh sáng chân thực, phù hợp cho phim ngắn, B-roll, quảng cáo.
>    - **`veo-3.1-fast-generate-preview` (Fast Prototyping):** Tốc độ xử lý nhanh hơn 2-3 lần, tối ưu chi phí và độ trễ khi cần thử nghiệm nhanh.
> 2. **Dò tìm `GEMINI_API_KEY` đa nguồn & che khóa (Key Masking):**
>    - Dò tự động từ tham số CLI `--api-key` → biến môi trường `GEMINI_API_KEY` / `GOOGLE_API_KEY` → file `.env` (duyệt ngược thư mục) → `~/.clawdbot/moltbot.json`.
>    - Không bao giờ in lộ khóa ra log (tự động che dạng `AQ.A***moaw`).
> 3. **Quản lý Long Running Operation (LRO) thông minh:**
>    - Tự động polling tiến trình không làm treo terminal, có thanh hiển thị tiến trình, kiểm soát timeout và bắt lỗi quota (`429`) / an toàn nội dung.
> 4. **Chế độ kiểm thử giả lập (`--fallback-placeholder`):**
>    - Tạo file MP4 mô phỏng hợp lệ khi kiểm thử offline, kiểm thử quy trình CI/CD hoặc khi chưa có quota video.

---

## 2. Bảng Lệnh Nhanh (Quick Command Reference)

| Tác vụ | Câu lệnh thực thi |
| :--- | :--- |
| **Kiểm tra trạng thái Skill, API Key & Models** | `python .agents/skills/call-veo-3.1/scripts/check-veo-3.1.py` |
| **Tạo video từ prompt văn bản (16:9, 720p)** | `python .agents/skills/call-veo-3.1/scripts/invoke-veo-3.1.py -p "Cinematic drone shot flying through a misty bamboo forest at sunrise, god rays piercing the fog" -f "output/bamboo.mp4"` |
| **Tạo video dạng dọc cho TikTok / Shorts (9:16)** | `python .agents/skills/call-veo-3.1/scripts/invoke-veo-3.1.py -p "Futuristic cyber warrior in neon rain" -a 9:16 -f "output/shorts.mp4"` |
| **Làm chuyển động ảnh tĩnh (Image-to-Video)** | `python .agents/skills/call-veo-3.1/scripts/invoke-veo-3.1.py -i "assets/character.png" -p "Subtle wind blowing through hair, camera slowly zooms in" -f "output/portrait.mp4"` |
| **Chạy với Veo 3.1 Fast (Tốc độ cao)** | `python .agents/skills/call-veo-3.1/scripts/invoke-veo-3.1.py -m veo-3.1-fast-generate-preview -p "Golden retriever playing with a ball" -f "output/dog.mp4"` |
| **Video độ nét 1080p, thời lượng 8 giây** | `python .agents/skills/call-veo-3.1/scripts/invoke-veo-3.1.py -p "Sports car speeding on coastal highway" -r 1080p -d 8 -f "output/car.mp4"` |
| **Nội suy giữa 2 khung hình (Interpolation)** | `python .agents/skills/call-veo-3.1/scripts/invoke-veo-3.1.py -i "start.png" --last-frame "end.png" -p "Smooth sunset to night transition"` |
| **Kiểm thử quy trình offline không tốn quota** | `python .agents/skills/call-veo-3.1/scripts/invoke-veo-3.1.py -p "Test prompt" -f "output/test.mp4" --fallback-placeholder` |

Xem toàn bộ danh mục tham số và kỹ thuật prompt tại [references/veo-3.1-reference.md](./references/veo-3.1-reference.md).

---

## 3. Quy Trình Thực Thi Chuẩn (Execution Procedures)

### Bước 1: Kiểm tra trạng thái cài đặt và cấu hình `GEMINI_API_KEY`
```powershell
python "C:\Users\Admin\.gemini\config\skills\call-veo-3.1\scripts\check-veo-3.1.py"
```

### Bước 2: Chạy lệnh tạo video bằng Veo 3.1
```powershell
python "C:\Users\Admin\.gemini\config\skills\call-veo-3.1\scripts\invoke-veo-3.1.py" `
  --prompt "A close-up cinematic shot of an ancient brass astrolabe turning slowly in warm candlelight, 4k ultra-detailed" `
  --aspect-ratio 16:9 `
  --resolution 720p `
  --duration 5 `
  --filename "output/astrolabe.mp4" `
  --timestamp
```

### Bước 3: Đọc và sử dụng kết quả
1. Script sẽ xuất dòng chuẩn `MEDIA: <đường dẫn file .mp4>` để môi trường Antigravity / chat hiển thị trực quan.
2. Kiểm tra JSON kết quả trên stdout (`ok: true`, `outputPath`, `processingTimeSeconds`, `model`).
