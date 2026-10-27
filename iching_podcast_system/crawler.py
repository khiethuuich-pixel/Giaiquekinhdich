"""
Module: crawler.py
Chức năng:
1. Nhập câu hỏi / tâm niệm của đạo hữu vào trang ichingtarot.com
2. Thực hiện Tam Kính: Đè giữ >3.5 giây x 3 lần (Kính Thiên, Kính Địa, Kính Nhân)
3. Nhấn 'Chụp hình thẻ bài' và trích xuất nguyên bản bức ảnh chụp thẻ bài (Blob 2.3K) làm ảnh video
4. Đóng modal ảnh chụp và nhấn 'Chép Toàn Thư Bách Khoa Cho AI (Đắc Pháp)'
"""

import os
import sys
import time
import base64
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def crawl_iching_reading(output_dir="output", user_question="Định hướng phát triển sự nghiệp và cuộc sống trong giai đoạn tới nên đi theo hướng nào?", headless=True):
    os.makedirs(output_dir, exist_ok=True)
    image_path = os.path.join(output_dir, "hexagram_card.png")
    text_path = os.path.join(output_dir, "hexagram_encyclopedia.txt")

    print("\n==================================================")
    print("🔮 [BƯỚC 1] BỐC QUẺ TAM KÍNH & CHỤP ẢNH THẺ BÀI THẬT")
    print("==================================================")
    print(f"📝 Tâm niệm / Câu hỏi: \"{user_question}\"")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chrome",
            headless=headless,
            args=["--start-maximized", "--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(
            viewport={"width": 1400, "height": 900},
            permissions=["clipboard-read", "clipboard-write"]
        )

        # Hook clipboard để thu thập toàn bộ dữ liệu quẻ khi bấm chép
        context.add_init_script("""
            window._copiedIchingText = '';
            const origWriteText = navigator.clipboard ? navigator.clipboard.writeText : null;
            if (navigator.clipboard) {
                navigator.clipboard.writeText = async function(val) {
                    window._copiedIchingText = val;
                    if (origWriteText) {
                        try { await origWriteText.apply(this, arguments); } catch(e){}
                    }
                    return Promise.resolve();
                };
            }
            const origExec = document.execCommand;
            document.execCommand = function(cmd) {
                if (cmd === 'copy') {
                    const active = document.activeElement;
                    if (active && (active.value || active.innerText)) {
                        window._copiedIchingText = active.value || active.innerText;
                    }
                }
                return origExec.apply(this, arguments);
            };
        """)

        page = context.new_page()
        print("🌐 Đang kết nối tới ichingtarot.com...")
        try:
            page.goto("https://ichingtarot.com", wait_until="commit", timeout=45000)
        except Exception:
            pass

        page.wait_for_selector("button:has-text('Bắt Đầu Bốc Quẻ')", timeout=30000)
        time.sleep(1.5)

        # 1. Điền câu hỏi vào textarea trước khi bốc quẻ
        textarea = page.locator("textarea[placeholder*='Tĩnh tâm nhập câu hỏi']").first
        if textarea.is_visible():
            print("✍️ Đang truyền tâm niệm & câu hỏi vào bàn chiêm bốc...")
            textarea.fill(user_question)
            time.sleep(1)

        # 2. Định vị nút bốc quẻ và thực hiện Tam Kính (3 lần x 3.6s)
        boc_que_btn = page.locator("button:has-text('Bắt Đầu Bốc Quẻ')").first
        rituals = [
            ("Lần 1: Kính Thiên (Thiên Thời - 敬天)", 3.6),
            ("Lần 2: Kính Địa (Địa Lợi - 敬地)", 3.6),
            ("Lần 3: Kính Nhân & Bốc Quẻ (Nhân Hòa - 敬人)", 3.8)
        ]

        for desc, hold_sec in rituals:
            print(f"👉 Đang thực hiện: {desc}...")
            box = boc_que_btn.bounding_box()
            if box:
                page.mouse.move(box["x"] + box["width"]/2, box["y"] + box["height"]/2)
                page.mouse.down()
                time.sleep(hold_sec)
                page.mouse.up()
                print(f"   ✓ Hoàn tất ({hold_sec}s). Nghỉ cảm ứng 1.5s...")
                time.sleep(1.5)

        time.sleep(2)

        # 3. Bấm nút 'Chụp hình thẻ bài' và lấy CHÍNH XÁC ảnh chụp thẻ bài (Blob 2.3K)
        print("📸 Nhấn nút 'Chụp hình thẻ bài' để lấy hình chụp thật...")
        snap_btn = page.locator("button:has-text('Chụp hình thẻ bài')").first
        if snap_btn.is_visible():
            snap_btn.click(force=True)
            time.sleep(2.5)

            # Lấy ảnh chụp thực tế từ thẻ img của modal
            modal_img = page.locator("img[alt*='Ảnh trận pháp'], img[alt*='Ảnh Toàn Bộ Thẻ Bài']").first
            if modal_img.is_visible():
                img_src = modal_img.get_attribute("src")
                if img_src and img_src.startswith("blob:"):
                    print("🖼️ Đang chuyển đổi ảnh chụp thẻ bài độ phân giải cao...")
                    base64_data = page.evaluate("""async (src) => {
                        const response = await fetch(src);
                        const blob = await response.blob();
                        return new Promise((resolve) => {
                            const reader = new FileReader();
                            reader.onloadend = () => resolve(reader.result);
                            reader.readAsDataURL(blob);
                        });
                    }""", img_src)
                    if "," in base64_data:
                        encoded = base64_data.split(",", 1)[1]
                        with open(image_path, "wb") as f:
                            f.write(base64.b64decode(encoded))
                        print(f"✅ ĐÃ LƯU ẢNH CHỤP THẺ BÀI THỰC TẾ (2.3K) TẠI: {image_path}")

            # Đóng modal ảnh chụp bằng cách click ra ngoài vùng nền mờ (10, 10)
            page.mouse.click(10, 10)
            time.sleep(1)

        # Nếu chưa lưu được ảnh blob, fallback chụp lại khu vực bài
        if not os.path.exists(image_path) or os.path.getsize(image_path) < 1000:
            print("⚠️ Fallback chụp ảnh màn hình trải bài...")
            page.screenshot(path=image_path)

        # 4. Bấm nút 'Chép Toàn Thư Bách Khoa Cho AI (Đắc Pháp)'
        print("📜 Đang nhấn 'Chép Toàn Thư Bách Khoa Cho AI'...")
        copy_btn = page.locator("button:has-text('Chép Toàn Thư Bách Khoa')").first
        if not copy_btn.is_visible():
            copy_btn = page.locator("button:has-text('Chép Toàn Bộ Quẻ')").first

        if copy_btn.is_visible():
            try:
                copy_btn.click(force=True, timeout=5000)
            except Exception:
                copy_btn.dispatch_event("click")
            time.sleep(1.5)
            print("⚡ Đã sao chép toàn thư bách khoa kèm câu hỏi!")

        copied_text = page.evaluate("window._copiedIchingText")
        if not copied_text or len(copied_text.strip()) == 0:
            copied_text = page.locator("body").inner_text()

        print(f"📖 Đã thu thập {len(copied_text):,} ký tự tri thức Dịch lý!")
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(copied_text)

        browser.close()

    return image_path, text_path, copied_text, user_question

if __name__ == "__main__":
    img, txt, data, q = crawl_iching_reading(output_dir="output", headless=True)
    print("Hoàn tất quy trình crawl thành công!")
