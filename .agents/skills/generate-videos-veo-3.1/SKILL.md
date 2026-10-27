---
name: generate-videos-veo-3-1
description: >-
  Generate videos with Veo 3.1 in Gemini API. Use this skill when the user wants to create, animate, or generate videos from text prompts (text-to-video) or input images (image-to-video), extend videos, and control cinematic camera parameters (aspect ratio 16:9, 9:16, 1:1; resolution 720p, 1080p, 4k; fps; duration) using Google Veo 3.1 models (veo-3.1-generate-preview and veo-3.1-fast-generate-preview) via Google GenAI SDK or safe REST scripts.
---

# Generate Videos with Veo 3.1 in Gemini API

Skill này cung cấp bộ công cụ tự động hóa toàn diện để tạo video chất lượng điện ảnh bằng **Google Veo 3.1** (`veo-3.1-generate-preview` và `veo-3.1-fast-generate-preview`) qua **Gemini API** và thư viện chính thức `google-genai`.

---

## 1. Tính Năng & Kiến Trúc Tự Động Hóa

> [!IMPORTANT]
> **Điểm nổi bật của Skill Veo 3.1:**
> 1. **Đầy đủ các phương thức tạo video:**
>    - **Text-to-Video:** Tạo video từ văn bản miêu tả bối cảnh và góc quay (`--prompt`).
>    - **Image-to-Video:** Đưa ảnh tĩnh vào (`-i / --image`) và tạo chuyển động theo ý muốn.
>    - **Frame Interpolation:** Nối mượt mà giữa ảnh bắt đầu (`-i`) và ảnh kết thúc (`--last-frame`).
> 2. **Hỗ trợ 2 phiên bản mô hình Veo 3.1:**
>    - `veo-3.1-generate-preview`: Chất lượng điện ảnh tối đa, ánh sáng và chi tiết vật lý trung thực.
>    - `veo-3.1-fast-generate-preview`: Tốc độ sinh video nhanh gấp 2-3 lần, phù hợp thử nghiệm nhanh.
> 3. **Cơ chế dò tìm API Key đa tầng & che khóa (Key Masking):**
>    - Dò tự động theo thứ tự: tham số `--api-key` → biến môi trường `GEMINI_API_KEY` / `GOOGLE_API_KEY` → file `.env` (duyệt ngược từ thư mục hiện tại) → `~/.clawdbot/moltbot.json`.
>    - Luôn che khóa (`AQ.A***moaw`) khi in log, bảo vệ an toàn tuyệt đối.
> 4. **Quản lý Long Running Operation (LRO) chuyên nghiệp:**
>    - Polling thông minh kèm timeout, thanh tiến trình và thông báo lỗi chi tiết.
>    - Hỗ trợ chế độ `--fallback-placeholder` khi kiểm thử offline mà không tốn quota.

---

## 2. Bảng Lệnh Nhanh (Quick Command Reference)

| Tác vụ | Câu lệnh thực thi |
| :--- | :--- |
| **Kiểm tra môi trường & API Key** | `python ~/.gemini/config/skills/generate-videos-veo-3.1/scripts/check-veo-3.1.py` |
| **Tạo video từ prompt (16:9, 720p)** | `python ~/.gemini/config/skills/generate-videos-veo-3.1/scripts/invoke-veo-3.1.py -p "Cinematic drone shot over misty mountains" -f "output/mountain.mp4"` |
| **Tạo video dọc cho TikTok/Shorts (9:16)** | `python ~/.gemini/config/skills/generate-videos-veo-3.1/scripts/invoke-veo-3.1.py -p "Futuristic cyber samurai walking in neon rain" -a 9:16 -f "output/samurai.mp4"` |
| **Biến ảnh tĩnh thành video (Image-to-Video)** | `python ~/.gemini/config/skills/generate-videos-veo-3.1/scripts/invoke-veo-3.1.py -i "photo.png" -p "Subtle wind blowing through hair, camera slowly zooms in" -f "output/portrait.mp4"` |
| **Dùng model Veo 3.1 Fast (Tốc độ cao)** | `python ~/.gemini/config/skills/generate-videos-veo-3.1/scripts/invoke-veo-3.1.py -m veo-3.1-fast-generate-preview -p "Golden retriever playing with a ball" -f "output/dog.mp4"` |
| **Video độ phân giải cao 1080p, 8 giây** | `python ~/.gemini/config/skills/generate-videos-veo-3.1/scripts/invoke-veo-3.1.py -p "Luxury sports car speeding on coastal highway" -r 1080p -d 8 -f "output/car.mp4"` |
| **Kiểm thử quy trình offline không tốn quota** | `python ~/.gemini/config/skills/generate-videos-veo-3.1/scripts/invoke-veo-3.1.py -p "Test prompt" -f "output/test.mp4" --fallback-placeholder` |

Xem toàn bộ danh mục tham số và cẩm nang kỹ thuật prompt tại [references/veo-3.1-reference.md](./references/veo-3.1-reference.md).

---

## 3. Quy Trình Thực Thi Chuẩn (Standard Workflow)

### Bước 1: Kiểm tra kết nối và trạng thái mô hình
```powershell
python "C:\Users\Admin\.gemini\config\skills\generate-videos-veo-3.1\scripts\check-veo-3.1.py"
```

### Bước 2: Chạy lệnh tạo video
```powershell
python "C:\Users\Admin\.gemini\config\skills\generate-videos-veo-3.1\scripts\invoke-veo-3.1.py" `
  --prompt "Slow cinematic dolly in on an ancient golden compass spinning in candlelight, 4k ultra-realistic" `
  --aspect-ratio 16:9 `
  --resolution 720p `
  --duration 5 `
  --filename "output/golden_compass.mp4" `
  --timestamp
```

### Bước 3: Đọc kết quả và hiển thị
1. Script sẽ xuất dòng chuẩn `MEDIA: <đường dẫn video>` để giao diện trò chuyện tự động hiển thị video clip.
2. Báo cáo đường dẫn file video đã lưu (`outputPath`) cho người dùng.

---

## 4. Cấu Trúc Thư Mục Skill

```
generate-videos-veo-3.1/
├── SKILL.md                          # Tài liệu chính của Skill
├── scripts/
│   ├── check-veo-3.1.py              # Script chẩn đoán môi trường & API Key
│   └── invoke-veo-3.1.py             # Script chính thực thi tạo video bằng Veo 3.1
└── references/
    └── veo-3.1-reference.md          # Hướng dẫn chi tiết tham số & prompt điện ảnh
```
