# ☯ Cửu Nhị · Hệ Thống Luận Giải Kinh Dịch & Xuất Bản Video Đa Bản Thể

Hệ thống hiện được **tách biệt hoàn toàn thành 2 Bảng độc lập 100%** để bạn tùy ý sử dụng theo nhu cầu mà không bị ghi đè hay xung đột tiến trình:

---

## 🏛 BẢNG 1: BẢNG CŨ · LUẬN GIẢI TRỰC TIẾP & XUẤT VIDEO DỌC 9:16
* **Đường dẫn truy cập:** [http://localhost:8000/direct](http://localhost:8000/direct)
* **Phím tắt Windows:** [run_direct.bat](file:///c:/Users/Admin/Downloads/Giaiquekinhdich/run_direct.bat)
* **Kịch bản dòng lệnh CLI:** `python pipeline_direct.py --question "..."`
* **Đặc tính kỹ thuật:**
  - Tự động bốc quẻ trên `ichingtarot.com`.
  - Luận giải Dịch lý trực tiếp 1 chiều (Direct single narrator).
  - Biên tập kịch bản đọc thoại 70-110 từ (khoảng 35-50 giây).
  - Thu âm 1 giọng thuyết minh trầm ấm (`vi-VN-NamMinhNeural` hoặc `vi-VN-HoaiMyNeural`).
  - Render video dọc chuẩn **1080x1920 (9:16)** tối ưu cho TikTok, Facebook Reels, YouTube Shorts với hiệu ứng zoom cận cảnh thẻ bài và chuông xoay Tây Tạng.

---

## 🎙 BẢNG 2: BẢNG MỚI · STUDIO PODCAST ĐÀM ĐẠO CHUYÊN SÂU & VIDEO MP4
* **Đường dẫn truy cập:** [http://localhost:8000/podcast](http://localhost:8000/podcast)
* **Phím tắt Windows:** [run_podcast.bat](file:///c:/Users/Admin/Downloads/Giaiquekinhdich/run_podcast.bat)
* **Kịch bản dòng lệnh CLI:** `python pipeline_podcast.py --question "..." --aspect-ratio 16:9 --mode deep`
* **Đặc tính kỹ thuật:**
  - Tự động bốc quẻ trên `ichingtarot.com`.
  - **Format Podcast 2 Host đối thoại chuyên sâu 5 Hồi**:
    - **Host Hoài My (Nữ)**: Cầu nối thính giả, đặt câu hỏi phản biện, phân tích tâm lý đương số.
    - **Dịch Sư Nam Minh (Nam)**: Mổ xẻ hào thế, hào biến, quy luật Âm Dương và **Đạo Tùy Thời (Thời - Vị - Trung - Chính)**.
  - Thu âm đối thoại 2 giọng nói tự nhiên, lồng tiếng chuông xoay và **nhạc nền thiền định 432Hz (Ambient Zen Pad)**.
  - Render **Video MP4 Full HD** (hỗ trợ **16:9 Landscape** và **9:16 Vertical**) với:
    - **Sóng âm thanh động thời gian thực (Live Waveform Visualizer)**.
    - **Đèn báo người nói (Active Speaker Glow)**: Tự động sáng viền kim quang khi từng nhân vật phát biểu.
    - **Phụ đề đối thoại phân màu** trong khung kính mờ cổ phong.
  - **Bản Ghi Âm Tương Tác (Interactive Transcript)**: Bấm vào mốc thời gian (*ví dụ `▶ 00:15`*) là video & audio lập tức nhảy đến giây đó.
  - **Bản Phân Tích Chuyên Sâu (Show Notes)**: Báo cáo đầy đủ kèm nút sao chép 1-click.

---

## 🧭 CÁCH CHUYỂN ĐỔI GIỮA 2 BẢNG

1. **Trên Giao diện Web:**
   - Ngay trên thanh Header của trang web có 2 nút chuyển đổi nhanh:
     - `[☯ BẢNG CŨ: LUẬN TRỰC TIẾP (9:16)]`
     - `[🎙 BẢNG MỚI: PODCAST & MP4 (16:9)]`
   - Bấm nút nào là màn hình lập tức chuyển sang bảng đó, trạng thái tiến trình của từng bảng được lưu độc lập.

2. **Khởi động nhanh qua file .bat:**
   - [run_direct.bat](file:///c:/Users/Admin/Downloads/Giaiquekinhdich/run_direct.bat): Mở thẳng Bảng Cũ.
   - [run_podcast.bat](file:///c:/Users/Admin/Downloads/Giaiquekinhdich/run_podcast.bat): Mở thẳng Bảng Mới.
   - [run.bat](file:///c:/Users/Admin/Downloads/Giaiquekinhdich/run.bat): Khởi động Web App Hub chứa cả 2 bảng.
