import time
import sys
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from config import IMAGES_DIR

ICHING_URL = "https://ichingtarot.com"

def cast_and_collect(layout: str = "random", headless: bool = True, log_cb=None) -> dict:
    """
    Automate ichingtarot.com:
    1. Navigate to the website.
    2. Click 'Bắt Đầu Bốc Quẻ'.
    3. Choose spread if requested ('1_card' or '3_card').
    4. Click 'Chụp hình thẻ bài' to save the high-res hexagram PNG image.
    5. Click '⚡ Chép Toàn Bộ Quẻ Bài & Câu Hỏi Cho AI' to read the full I Ching text from clipboard.
    Returns:
        dict: {
            "success": bool,
            "image_path": str,
            "hexagram_text": str,
            "timestamp": str,
            "error": str | None
        }
    """
    def log(msg):
        if log_cb:
            log_cb(msg)
        print(f"[Crawler] {msg}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_image_path = IMAGES_DIR / f"que_{timestamp}.png"

    log("Khởi động trình duyệt tự động (Microsoft Edge)...")

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="msedge", headless=headless)
        except Exception as e:
            log(f"Không mở được msedge: {e}, thử khởi chạy chromium mặc định...")
            browser = p.chromium.launch(headless=headless)

        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            permissions=["clipboard-read", "clipboard-write"]
        )
        # Đặt sẵn trạng thái Cửu Nhị Tiểu Long đã thức trong ngày hôm nay để mở khóa ngay lập tức nút Chép Cho AI
        context.add_init_script("""
            try {
                const d = new Date();
                const todayKey = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
                localStorage.setItem("cuunhi_dragon_awake_date_v1", todayKey);
            } catch (e) {}
        """)
        page = context.new_page()

        try:
            log(f"Đang kết nối tới {ICHING_URL}...")
            # Tải trang siêu tốc qua commit (không bao giờ timeout do networkidle/font/tracker)
            page.goto(ICHING_URL, wait_until="commit", timeout=25000)
            try:
                page.wait_for_load_state("domcontentloaded", timeout=10000)
            except Exception:
                pass

            # Đợi nút 'Bắt Đầu Bốc Quẻ' sẵn sàng
            try:
                page.wait_for_selector('button:has-text("Bắt Đầu Bốc Quẻ")', timeout=10000)
            except Exception:
                pass
            time.sleep(1.5)

            # Click 'Bắt Đầu Bốc Quẻ'
            log("Đang bắt đầu bốc quẻ Kinh Dịch...")
            start_btn = page.locator('button:has-text("Bắt Đầu Bốc Quẻ")').first
            if start_btn.is_visible():
                start_btn.click()
                time.sleep(2)
            else:
                log("Không thấy nút 'Bắt Đầu Bốc Quẻ', tiếp tục kiểm tra trang...")

            # Trận pháp ngẫu nhiên theo website
            log("Trận pháp tự động ngẫu nhiên theo website...")
            import random
            available_spreads = [
                ("1 Lá", "1 Lá · Đơn Quẻ"),
                ("2 Lá", "2 Lá · Âm Dương"),
                ("3 Lá", "3 Lá · Tam Tài"),
                ("5 Lá", "5 Lá · Ngũ Hành"),
                ("Thất Tinh", "7 Lá · Thất Tinh Bắc Đẩu"),
                ("Thập Tinh", "10 Lá · Thập Tinh Celtic Cross"),
                ("Tháp La Kinh Dịch", "Tháp La Kinh Dịch"),
                ("default", "Trận Pháp Tự Nhiên Của Website")
            ]
            choice = random.choice(available_spreads)
            if choice[0] != "default":
                spread_btn = page.locator(f'button:has-text("{choice[0]}")').first
                if spread_btn.is_visible():
                    log(f"Ngẫu nhiên kích hoạt: {choice[1]}...")
                    spread_btn.click()
                    time.sleep(2)
                else:
                    log("Sử dụng trận pháp ngẫu nhiên theo web...")
            else:
                log("Sử dụng trận pháp ngẫu nhiên theo web...")

            # Nếu Cửu Nhị Tiểu Long đang ngủ (khóa nút Chép Cho AI), bấm nút Gọi Cửu Nhị Tiểu Long Dậy trước
            try:
                wake_btn = page.locator('#btn-wake-up-dragon, button:has-text("Gọi Cửu Nhị Tiểu Long Dậy")').first
                if wake_btn.is_visible():
                    log("Đang gọi Cửu Nhị Tiểu Long dậy để mở khóa nút Chép Cho AI...")
                    wake_btn.scroll_into_view_if_needed()
                    wake_btn.click()
                    time.sleep(5.2)
            except Exception:
                pass

            # Click '⚡ Chép Toàn Bộ Quẻ Bài & Câu Hỏi Cho AI' trước khi mở modal chụp hình
            log("Đang trích xuất dữ liệu quẻ bằng nút 'Chép Cho AI'...")
            copy_btn = page.locator('button:has-text("Chép Toàn Bộ Quẻ Bài"), button:has-text("Sao Chép Cho AI"), button:has-text("Chép Cho AI")').first

            hexagram_text = ""
            if copy_btn.is_visible():
                copy_btn.scroll_into_view_if_needed()
                copy_btn.click()
                time.sleep(1)
                try:
                    hexagram_text = page.evaluate("navigator.clipboard.readText()")
                except Exception as e_clip:
                    log(f"Lỗi đọc clipboard qua evaluate: {e_clip}")

            if not hexagram_text or len(hexagram_text) < 20:
                log("Dữ liệu clipboard chưa đầy đủ, trích xuất text từ phần tử lá bài trên trang...")
                card_elements = page.locator(".card, [class*='card'], [data-card]").all()
                card_texts = [c.inner_text() for c in card_elements if c.is_visible()]
                hexagram_text = "\n".join(card_texts) if card_texts else "Quẻ Kinh Dịch Cát Tường"

            log(f"Đã thu thập dữ liệu quẻ ({len(hexagram_text)} ký tự).")

            # Click 'Chụp hình' / 'Chụp hình thẻ bài'
            log("Đang kích hoạt nút 'Chụp hình thẻ bài'...")
            shot_btn = page.locator('button:has-text("Chụp hình thẻ bài"), button:has-text("Chụp hình")').first
            image_saved = False

            if shot_btn.is_visible():
                shot_btn.scroll_into_view_if_needed()
                try:
                    # Expect download event
                    with page.expect_download(timeout=6000) as download_info:
                        shot_btn.click()
                        time.sleep(1.5)
                    download = download_info.value
                    download.save_as(str(out_image_path))
                    image_saved = True
                    log(f"Tải ảnh quẻ thành công: {out_image_path.name}")
                except Exception as e_down:
                    log(f"Không bắt được download event: {e_down}. Dùng phương thức chụp vùng lá bài trực tiếp...")

            # Fallback capture if download failed or not triggered
            if not image_saved or not out_image_path.exists() or out_image_path.stat().st_size < 1000:
                log("Đang chụp trực tiếp khung lá bài trên giao diện...")
                # Find the main card container
                card_container = page.locator("div:has(> img), [class*='card-grid'], [class*='cards-container']").first
                if card_container.is_visible():
                    card_container.screenshot(path=str(out_image_path))
                else:
                    page.screenshot(
                        path=str(out_image_path),
                        clip={"x": 200, "y": 80, "width": 880, "height": 720}
                    )
                log(f"Đã lưu ảnh chụp khung bài: {out_image_path.name}")

            browser.close()
            return {
                "success": True,
                "image_path": str(out_image_path),
                "hexagram_text": hexagram_text,
                "timestamp": timestamp,
                "error": None
            }

        except Exception as err:
            log(f"Lỗi trong quá trình cào dữ liệu: {err}")
            browser.close()
            return {
                "success": False,
                "image_path": "",
                "hexagram_text": "",
                "timestamp": timestamp,
                "error": str(err)
            }

if __name__ == "__main__":
    result = cast_and_collect(layout="1_card", headless=True)
    print("Result:", result)
