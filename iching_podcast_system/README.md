# ☯ Hệ Thống Tự Động Luận Giải Kinh Dịch & Sản Xuất Video Podcast (Dual-AI)

Hệ thống tự động hóa hoàn toàn từ A đến Z:
1. **Truy cập `ichingtarot.com`**: Tự động chụp hình thẻ bài, đè giữ nút *"Bắt Đầu Bốc Quẻ"* hơn 3.5 giây qua 3 nghi thức **Tam Kính** (Kính Thiên • Kính Địa • Kính Nhân).
2. **Trích xuất toàn thư**: Tự động nhận diện và nhấn nút *"Chép Toàn Thư Bách Khoa Cho AI (Đắc Pháp)"*, thu thập hơn 28.000 ký tự tri thức chi tiết của quẻ.
3. **Dual-AI Podcast Debate**: Đẩy toàn bộ tri thức vào **ChatGPT** (Đạo Trưởng Cổ Truyền) và **Gemini** (Chiến Lược Gia Hiện Đại) để đối thoại, phản biện và đúc kết "Diệu Kế Hành Động".
4. **Sản xuất Podcast đa giọng**: Dùng **Microsoft Edge-TTS** lồng tiếng tự nhiên 2 nhân vật (`vi-VN-NamMinhNeural` & `vi-VN-HoaiMyNeural`).
5. **Render Video hoàn chỉnh**: Dùng **FFmpeg** kết hợp hình ảnh thẻ bài đã chụp + sóng âm động (audiogram ánh kim) + audio podcast thành file MP4 hoàn thiện 1080p.

---

## 🚀 Hướng Dẫn Chạy Nhanh (1-Click)

Chỉ cần mở terminal tại thư mục này và chạy:

```bash
python run_pipeline.py
```

Toàn bộ thành phẩm sẽ được lưu tự động tại thư mục `output/`:
- `output/hexagram_card.png`: Ảnh chụp quẻ từ web.
- `output/hexagram_encyclopedia.txt`: Toàn thư bách khoa chi tiết của quẻ vừa bốc.
- `output/podcast_script.json`: Kịch bản đối thoại song tấu giữa ChatGPT và Gemini.
- `output/master_podcast.mp3`: File âm thanh Podcast hoàn chỉnh 2 giọng đọc.
- `output/iching_podcast_video.mp4`: Video hoàn thiện sẵn sàng tải lên YouTube / Facebook / TikTok!

---

## ⚙️ Cấu Hình API Key (Tùy chọn)

Nếu bạn có API Key của OpenAI và Google Gemini, hãy điền vào file `.env` hoặc thiết lập biến môi trường:
```bash
set GEMINI_API_KEY=your_gemini_api_key
set OPENAI_API_KEY=your_openai_api_key
```
*Lưu ý: Nếu không có API Key, hệ thống vẫn tự động trích xuất nội hàm tri thức 28.000 ký tự từ quẻ để sinh ra kịch bản đối thoại triết học đỉnh cao.*
