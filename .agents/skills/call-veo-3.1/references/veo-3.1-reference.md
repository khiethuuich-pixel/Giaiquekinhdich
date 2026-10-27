# Tài Liệu Tham Khảo Google Veo 3.1 trong Gemini API

Tài liệu này cung cấp chi tiết kỹ thuật, bảng tham số và hướng dẫn prompt cinematic chuyên sâu cho các mô hình **Google Veo 3.1** (`veo-3.1-generate-preview` và `veo-3.1-fast-generate-preview`) thông qua Gemini API (Google Gen AI SDK).

---

## 1. Danh Sách Mô Hình & Đặc Điểm

| Tên Model | Endpoint / Model ID | Mục đích sử dụng | Đặc điểm nổi bật |
| :--- | :--- | :--- | :--- |
| **Veo 3.1 Quality** | `veo-3.1-generate-preview` | Sản xuất phim ngắn, video quảng cáo, B-roll chất lượng cao | Độ chi tiết cinematic vượt trội, ánh sáng chân thực, chuyển động vật lý chính xác |
| **Veo 3.1 Fast** | `veo-3.1-fast-generate-preview` | Thử nghiệm ý tưởng (prototyping), tạo video mạng xã hội tốc độ cao | Tốc độ kết xuất nhanh hơn 2-3x, tối ưu chi phí và độ trễ |
| **Veo 2.0 Legacy** | `veo-2.0-generate-001` | Dự phòng tương thích ngược | Thế hệ trước của dòng Veo |

---

## 2. Bảng Tham Số Kỹ Thuật (GenerateVideosConfig)

| Tham số | Kiểu dữ liệu | Giá trị hỗ trợ | Mặc định | Ghi chú |
| :--- | :--- | :--- | :--- | :--- |
| `aspect_ratio` | string | `"16:9"`, `"9:16"`, `"1:1"` | `"16:9"` | `16:9` cho YouTube/TV; `9:16` cho TikTok/Shorts/Reels |
| `resolution` | string | `"720p"`, `"1080p"`, `"4k"` | `"720p"` | 1080p và 4k cho chất lượng sắc nét chuẩn điện ảnh |
| `duration_seconds` | int | `5`, `8` | `5` | Thời lượng video tính bằng giây |
| `fps` | int | `24` | `24` | Chuẩn 24 hình/giây điện ảnh (cinematic frame rate) |
| `person_generation` | string | `"dont_allow"`, `"allow_adult"`, `"allow_all"` | `"dont_allow"` | Quy tắc an toàn tạo nhân vật người |
| `negative_prompt` | string | Chuỗi mô tả | `""` | Loại bỏ các yếu tố như: `blurry, distorted, oversaturated, jerky motion` |
| `enhance_prompt` | bool | `true`, `false` | `true` | Tự động làm giàu mô tả phân cảnh bằng AI |
| `generate_audio` | bool | `true`, `false` | `false` | Tạo hiệu ứng âm thanh / nhạc nền đi kèm video |
| `last_frame` | Image | Object hình ảnh | `None` | Khung kết thúc cho hiệu ứng nội suy khung hình (Interpolation) |

---

## 3. Các Chế Độ Tạo Video (Modalities)

### 3.1. Text-to-Video (Tạo video từ văn bản)
Tạo hoàn toàn video từ kịch bản hoặc mô tả chi tiết:
```bash
python scripts/invoke-veo-3.1.py \
  -p "Cinematic drone shot flying through a misty bamboo forest at sunrise, god rays piercing the fog, photorealistic 8k" \
  -a 16:9 \
  -r 1080p \
  -d 5
```

### 3.2. Image-to-Video (Biến ảnh tĩnh thành video)
Truyền ảnh tĩnh đầu vào (`-i`) và chỉ định chuyển động của máy quay hoặc nhân vật:
```bash
python scripts/invoke-veo-3.1.py \
  -i "assets/character.png" \
  -p "The character slowly turns their head towards the camera and gently smiles, soft cinematic wind blowing their hair" \
  -a 9:16 \
  -d 5
```

### 3.3. Frame Interpolation (Chuyển tiếp giữa 2 khung hình)
Chỉ định ảnh đầu (`-i`) và ảnh kết thúc (`--last-frame`) để Veo tạo phân cảnh chuyển đổi mượt mà giữa hai trạng thái:
```bash
python scripts/invoke-veo-3.1.py \
  -i "start_scene.png" \
  --last-frame "end_scene.png" \
  -p "Seamless smooth transition from day to night over the cyberpunk skyline"
```

---

## 4. Cẩm Nang Kỹ Thuật Prompt Điện Ảnh (Cinematic Prompt Engineering)

Để đạt chất lượng tối đa với Veo 3.1, hãy chia cấu trúc prompt thành 4 thành phần:

```
[Chủ thể & Hành động] + [Góc máy & Chuyển động máy quay] + [Ánh sáng & Màu sắc] + [Phong cách & Ống kính]
```

### Chuyển Động Máy Quay (Camera Motion Prompts)
- **Slow Dolly In / Push In:** `Camera slowly pushes in towards the subject, creating an intimate dramatic tension`
- **Orbital 360 Spin:** `Camera smoothly orbits 360 degrees around the statue in a continuous fluid motion`
- **FPV Drone Flythrough:** `High-speed FPV drone tracking shot weaving between ancient neon-lit pagodas`
- **Tracking / Following Shot:** `Low-angle tracking shot following the runner from behind, dynamic motion blur`
- **Crane / Jib Shot:** `Camera cranes upward from a close-up of a blooming lotus to reveal a vast misty lake`

### Ánh Sáng & Khí Quyển (Atmosphere & Lighting)
- **Volumetric God Rays:** `Golden hour sunlight filtering through dust motes, cinematic volumetric atmosphere`
- **Cyberpunk Neo-Noir:** `Reflective wet asphalt, high contrast, vivid cyan and magenta neon rim lighting`
- **Ethereal Mist:** `Moody morning fog rolling over calm dark water, muted monochromatic palette`

### Ống Kính & Độ Sâu Trường Ảnh (Optics & Depth)
- **Anamorphic Lens:** `Shot on 35mm anamorphic lens, oval bokeh, horizontal blue lens flares`
- **Macro Detail:** `Extreme macro shot of dew drops glistening on spider silk, ultra shallow depth of field`
- **Wide Angle Sweep:** `Ultra-wide 16mm perspective capturing the immense scale of the mountain range`

---

## 5. Tích Hợp Python SDK (Google Gen AI SDK)

```python
import time
from google import genai
from google.genai import types

# 1. Khởi tạo Client (Tự động đọc GEMINI_API_KEY)
client = genai.Client()

# 2. Khởi tạo LRO (Long Running Operation)
operation = client.models.generate_videos(
    model="veo-3.1-generate-preview",
    prompt="A majestic eagle soaring over snow-capped mountains, cinematic 4k, slow motion",
    config=types.GenerateVideosConfig(
        aspect_ratio="16:9",
        resolution="1080p",
        duration_seconds=5,
        fps=24,
        person_generation="dont_allow",
    ),
)

print(f"Bắt đầu tác vụ: {operation.name}")

# 3. Polling cho đến khi hoàn thành
while not operation.done:
    time.sleep(10)
    operation = client.operations.get(operation)
    print(".", end="", flush=True)

# 4. Tải và lưu video
if operation.response and operation.response.generated_videos:
    video = operation.response.generated_videos[0].video
    video.save("majestic_eagle.mp4")
    print("\nVideo đã được lưu thành công!")
```

---

## 6. Xử Lý Sự Cố Thường Gặp (Troubleshooting)

1. **Lỗi `404 NOT_FOUND: Model is not found`:**
   - Kiểm tra xem API Key của bạn đã được kích hoạt dịch vụ tạo video của Gemini chưa.
   - Sử dụng đúng tên model: `veo-3.1-generate-preview` hoặc `veo-3.1-fast-generate-preview`.
2. **Lỗi `429 RESOURCE_EXHAUSTED`:**
   - Hạn ngạch (Quota) video bị giới hạn trên gói miễn phí. Hãy đảm bảo tài khoản Google Cloud / Google AI Studio đã liên kết dự án có tính phí (Pay-as-you-go).
3. **Lỗi `SAFETY_VIOLATION` hoặc `person_generation`:**
   - Nếu prompt có người thực, hãy thêm tham số `--person-generation allow_adult`.
