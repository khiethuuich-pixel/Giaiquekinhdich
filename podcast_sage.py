import json
import re
import sys
import time
from google import genai
from google.genai import types

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from config import GEMINI_API_KEY

MODE_PROFILES = {
    "quick": {
        "turns": "4-6",
        "desc": "Siêu tinh gọn cấp tốc: Đi thẳng vào kết luận cốt tủy và giải pháp thực chiến tức thì, không rườm rà."
    },
    "compact": {
        "turns": "6-8",
        "desc": "Tinh gọn cốt tủy: Tóm tắt nhanh ý tượng quẻ và định hướng hành động chính."
    },
    "standard": {
        "turns": "8-10",
        "desc": "Tiêu chuẩn đàm đạo: Đối thoại tự nhiên, phân tích tượng quẻ, tâm lý người hỏi và Đạo Tùy Thời."
    },
    "deep": {
        "turns": "10-14",
        "desc": "Đàm đạo chuyên sâu 5 Hồi: Duyên khởi, Giải mã quái tượng, Phản biện hào biến, Đạo Tùy Thời thực chiến và Kim chỉ nam."
    },
    "master": {
        "turns": "14-18",
        "desc": "Đại luận đạo trưởng lão: Uyên thâm, tầm vóc lớn, mổ xẻ triết lý Chu Dịch cổ xưa, biến chuyển Âm Dương càn khôn và kế sách dài hạn."
    },
    "debate": {
        "turns": "10-14",
        "desc": "Phản biện sắc bén: Host hỏi xoáy đáp xoay, đào sâu nghịch lý, cạm bẫy và rủi ro lớn nhất; Dịch sư chỉ rõ điểm mù và sách lược phá vỡ thế kẹt."
    },
    "business_tactics": {
        "turns": "10-14",
        "desc": "Binh pháp thương trường & kinh doanh: Tập trung mổ xẻ cơ hội thị trường, thời điểm xuất kích hay án binh bất động, quản trị dòng tiền và nhân sự."
    },
    "zen_healing": {
        "turns": "8-12",
        "desc": "Thiền luận & chữa lành: Giọng điệu từ ái, tĩnh tại, giúp thấu suốt muộn phiền, buông bỏ chấp niệm và tìm về sự bình an nội tại."
    },
    "relationship_care": {
        "turns": "8-12",
        "desc": "Tâm tình & đối nhân xử thế: Mổ xẻ đạo hòa hợp Âm Dương, nghệ thuật ứng xử gia đạo, đối tác và tình duyên."
    }
}

SYSTEM_PROMPT = """Bạn là Tổng Biên Tập & Đạo Diễn của chương trình Podcast Thượng Đẳng: 
"CỬU NHỊ LUẬN ĐẠO · PODCAST PHÂN TÍCH KINH DỊCH & TRIẾT HỌC XỬ THẾ".

Chương trình là buổi đàm đạo hấp dẫn, trí tuệ giữa 2 người:
1. HOST (Hoài My - Nữ): Người dẫn chuyện sắc sảo, ấm áp, thấu cảm, liên tục đặt câu hỏi phản biện, chạm đúng nỗi trăn trở thực tế của người hỏi quẻ.
2. MASTER (Dịch Sư Nam Minh - Nam): Bậc trưởng lão Dịch học uyên áo, đĩnh đạc, thấu triệt 64 quẻ Chu Dịch, Thoán Từ, Tượng Truyện, Hào Biến và Đạo Tùy Thời (Thời - Vị - Trung - Chính). Phân tích dịch lý khúc chiết, biện chứng, không mê tín, soi sáng đường đi nước bước.

BẮT BUỘC TRẢ VỀ ĐỊNH DẠNG JSON DUY NHẤT (không dùng markdown giải thích bên ngoài):
{
  "podcast_title": "Tiêu đề hấp dẫn của tập podcast",
  "hexagram_title": "Tên quẻ Kinh Dịch",
  "summary_verdict": "Một câu chân ngôn đúc kết cốt lõi",
  "chapters": [
    {"title": "Hồi 1: Tiếp Nhận Duyên Khởi", "desc": "Nêu câu hỏi và ý niệm thời vận"},
    {"title": "Hồi 2: Khám Phá Quái Tượng", "desc": "Giải mã ý tượng và năng lượng quẻ"},
    {"title": "Hồi 3: Biến Dịch & Thách Thức", "desc": "Đối thoại về hào thế và quy luật âm dương"},
    {"title": "Hồi 4: Đạo Tùy Thời & Hành Động", "desc": "Chiến lược cụ thể cho đương số"},
    {"title": "Hồi 5: Đúc Kết Kim Chỉ Nam", "desc": "Chân ngôn xử thế và lời chúc"}
  ],
  "dialogue": [
    {"speaker": "host", "text": "Lời thoại của Host Hoài My..."},
    {"speaker": "master", "text": "Lời thoại của Dịch Sư Nam Minh..."}
  ],
  "full_show_notes": "Bản phân tích chuyên sâu chi tiết đầy đủ gồm 3 phần: 1. Ý Tượng Quẻ & Bản Chất Triết Học, 2. Phân Tích Thực Trạng & Hào Thế Hào Biến, 3. Lời Khuyên Hành Động & Đạo Tùy Thời."
}
"""

CANDIDATE_MODELS = [
    "gemini-flash-lite-latest",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-flash-latest",
    "gemini-3.7-flash",
    "gemini-3.8-flash",
    "gemini-3-flash-preview"
]

def generate_podcast_analysis(
    question: str,
    hexagram_data: str,
    api_key: str = None,
    duration_mode: str = "deep",
    log_cb=None
) -> dict:
    """Generate in-depth 2-host podcast script and show notes using Gemini with multi-mode customization."""
    def log(msg):
        if log_cb:
            log_cb(msg)
        print(f"[PodcastSage] {msg}", flush=True)

    key = api_key or GEMINI_API_KEY
    profile = MODE_PROFILES.get(duration_mode, MODE_PROFILES["deep"])
    target_turns = profile["turns"]
    mode_desc = profile["desc"]

    user_prompt = f"""CÂU HỎI CỦA ĐƯƠNG SỐ:
"{question}"

DỮ LIỆU THẺ BÀI & QUẺ KINH DỊCH THU THẬP TỪ ICHINGTAROT.COM:
{hexagram_data}

YÊU CẦU ĐẶC BIỆT THEO CHẾ ĐỘ ĐÀM ĐẠO [{duration_mode.upper()}]:
- Số lượt thoại yêu cầu: Đúng khoảng {target_turns} lượt đối đáp giữa Host Hoài My và Dịch Sư Nam Minh.
- Định hướng phong cách: {mode_desc}
"""

    response_text = None
    if key:
        client = genai.Client(api_key=key)
        for model_name in CANDIDATE_MODELS:
            try:
                log(f"Đang biên tập kịch bản Podcast ({duration_mode}) qua mô hình: {model_name}...")
                resp = client.models.generate_content(
                    model=model_name,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        response_mime_type="application/json",
                        temperature=0.7,
                        http_options=types.HttpOptions(timeout=60000)
                    )
                )
                if resp and resp.text:
                    response_text = resp.text.strip()
                    log(f"Thành công với mô hình: {model_name}!")
                    break
            except Exception as err:
                log(f"Mô hình {model_name} bận ({str(err)[:60]}), chuyển tiếp...")
                time.sleep(0.5)

    # Clean potential markdown fences
    if response_text:
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        elif response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()

    data = None
    if response_text:
        try:
            data = json.loads(response_text)
        except Exception as e:
            log(f"Cảnh báo phân tích JSON, tiến hành chuẩn hóa cấu trúc: {e}")

    # Fallback to high-quality template if Gemini is unreachable or returned invalid JSON
    if not data or not data.get("dialogue"):
        log(f"Kích hoạt bộ biên dịch Dịch Học Chuyên Sâu dự phòng ({duration_mode})...")
        data = _generate_fallback_podcast(question, hexagram_data, duration_mode)

    return data

def _generate_fallback_podcast(question: str, hexagram_data: str, duration_mode: str = "deep") -> dict:
    """Indestructible fallback podcast script generator adapted to duration_mode."""
    match = re.search(r"Quẻ(?:\s*số\s*\d+)?[:\s]+([A-ZÀ-Ỹ\s]+)", hexagram_data, re.IGNORECASE)
    hex_name = match.group(1).strip() if match else "QUẺ KINH DỊCH CÁT TƯỜNG"
    if len(hex_name) > 35:
        hex_name = hex_name[:35].strip()

    title = f"Cửu Nhị Luận Đạo · {hex_name}: Giải Mã Thời Vận & Đạo Tùy Thời"

    if duration_mode == "quick":
        dialogue = [
            {"speaker": "host", "text": f"Chào quý vị thính giả. Với câu hỏi '{question}', quẻ Dịch mở ra thông điệp gì thưa Thầy?"},
            {"speaker": "master", "text": f"Quẻ {hex_name} cho thấy thời cơ đang chuyển dịch. Điều cốt yếu lúc này là giữ tâm định, không manh động."},
            {"speaker": "host", "text": "Vậy hành động thực tế tối ưu nhất là gì ạ?"},
            {"speaker": "master", "text": "Thuận theo Đạo Tùy Thời: Lấy tĩnh chế động, tích lũy nội lực, thời đến ắt đại cát hanh thông."}
        ]
    elif duration_mode == "compact":
        dialogue = [
            {"speaker": "host", "text": f"Chào mừng các bạn đến với Cửu Nhị Luận Đạo. Hôm nay chúng ta có câu hỏi: '{question}'."},
            {"speaker": "master", "text": f"Chào Hoài My. Duyên khởi đưa chúng ta đến quẻ {hex_name}, một quẻ mang tính bước ngoặt sâu sắc."},
            {"speaker": "host", "text": f"Tượng quẻ {hex_name} báo hiệu điều gì cho người hỏi thưa Thầy?"},
            {"speaker": "master", "text": "Ý tượng quẻ khuyên ta củng cố nền tảng, nhìn nhận rõ thực lực trước khi tiến bước."},
            {"speaker": "host", "text": "Đâu là kim chỉ nam hành động lúc này ạ?"},
            {"speaker": "master", "text": "Chính trực, kiên định và tùy thời ứng biến. Giữ tâm trong sáng ắt vạn sự hanh thông."}
        ]
    elif duration_mode == "debate":
        dialogue = [
            {"speaker": "host", "text": f"Chào Thầy Nam Minh. Câu hỏi hôm nay rất thách thức: '{question}'. Liệu có phải đương số đang quá lạc quan?"},
            {"speaker": "master", "text": f"Chào Hoài My. Rất xác đáng! Quẻ {hex_name} thoạt nhìn có vẻ êm ả nhưng ẩn chứa những dòng nước ngầm hiểm trở."},
            {"speaker": "host", "text": "Nghĩa là nếu cứ lao tới bất chấp thì rủi ro sẽ rất lớn thưa Thầy?"},
            {"speaker": "master", "text": "Chính xác. Hào thế cho thấy sự nôn nóng là cạm bẫy lớn nhất. Người quân tử thấy cơ mà hành động, chưa đến lúc thì phải ẩn nhẫn."},
            {"speaker": "host", "text": "Vậy đâu là lối thoát và giải pháp hóa giải hiểm nguy?"},
            {"speaker": "master", "text": "Biến nghịch cảnh thành cơ hội bằng cách củng cố nội lực, minh bạch mọi thỏa thuận và không để cảm xúc lấn át lý trí."},
            {"speaker": "host", "text": "Một góc nhìn phản biện cực kỳ sắc sảo! Cảm ơn Thầy rất nhiều."},
            {"speaker": "master", "text": "Cùng tắc biến, biến tắc thông. Thấu suốt điểm mù chính là chìa khóa mở ra đại cát."}
        ]
    elif duration_mode == "business_tactics":
        dialogue = [
            {"speaker": "host", "text": f"Chào mừng quý doanh nhân và thính giả. Với câu hỏi kinh doanh: '{question}', quẻ Dịch soi sáng chiến lược nào?"},
            {"speaker": "master", "text": f"Chào Hoài My. Quẻ {hex_name} là bài học kinh điển về chiến lược thương trường: 'Vật dụng hữu du vãng'."},
            {"speaker": "host", "text": "Thưa Thầy, trong kinh doanh điều này có nghĩa là nên hoãn lại hay tái cơ cấu?"},
            {"speaker": "master", "text": "Nó có nghĩa là không nên mở rộng quy mô khi dòng tiền và nhân sự chưa vững. Hãy tập trung củng cố sản phẩm cốt lõi."},
            {"speaker": "host", "text": "Về mặt đối tác và thị trường, đâu là thời điểm lý tưởng để tăng tốc?"},
            {"speaker": "master", "text": "Khi hào biến chuyển từ âm sang dương, tức thị trường có tín hiệu kiểm chứng rõ ràng. Lúc đó xuất kích sẽ nắm chắc phần thắng."},
            {"speaker": "host", "text": "Một kim chỉ nam rất thực dụng và sâu sắc cho các nhà sáng lập!"},
            {"speaker": "master", "text": "Kinh doanh thuận đạo Dịch là biết tiến thoái nhịp nhàng, vững gốc ắt bền cây."}
        ]
    elif duration_mode == "zen_healing":
        dialogue = [
            {"speaker": "host", "text": f"Chào Thầy Nam Minh. Đương số gửi gắm nỗi trăn trở: '{question}'. Làm sao để giữ được sự an yên trước ngã rẽ này?"},
            {"speaker": "master", "text": f"Chào Hoài My và các bạn. Quẻ {hex_name} nhắc nhở chúng ta: Mọi giông bão ngoài kia đều bắt nguồn từ tâm xao động bên trong."},
            {"speaker": "host", "text": "Nhiều lúc ta muốn kiểm soát mọi kết quả nhưng lại cảm thấy bất lực, đúng không thưa Thầy?"},
            {"speaker": "master", "text": "Đó là vì ta dính mắc vào chữ 'Đắc - Thất'. Dịch lý dạy rằng vạn sự đều có thời điểm nở hoa, ép sớm chỉ thêm hao tổn."},
            {"speaker": "host", "text": "Vậy bài học chuyển hóa cảm xúc lúc này là gì ạ?"},
            {"speaker": "master", "text": "Học cách thở sâu, quay về với hiện tại, buông bỏ lo lắng tương lai. Tâm an thì vạn sự an, trí sáng thì đường tự mở."},
            {"speaker": "host", "text": "Cảm ơn Thầy vì những lời chia sẻ ấm áp và chữa lành tâm hồn."},
            {"speaker": "master", "text": "Chúc bạn giữ vững đóa sen tâm thức, tĩnh lặng giữa cuộc đời biến thiên."}
        ]
    else:  # deep, master, standard, relationship_care
        dialogue = [
            {"speaker": "host", "text": f"Chào mừng quý thính giả đến với Cửu Nhị Luận Đạo. Hôm nay, chúng ta cùng đàm đạo về câu hỏi: '{question}'."},
            {"speaker": "master", "text": f"Chào Hoài My và các bạn. Kinh Dịch dạy 'Cùng tắc biến, biến tắc thông'. Duyên khởi hôm nay đưa chúng ta đến với quẻ {hex_name}."},
            {"speaker": "host", "text": f"Thưa Thầy, đối với câu hỏi '{question}', quẻ {hex_name} hé lộ bức tranh tổng thể như thế nào cho đương số?"},
            {"speaker": "master", "text": "Ý tượng quẻ cho thấy vạn vật đang vận động theo quy luật tự nhiên. Đây là lúc đương số cần nhìn thấu bản chất vấn đề, củng cố nội lực."},
            {"speaker": "host", "text": "Nhiều người thường lo lắng khi gặp giai đoạn chuyển giao này. Vậy về mặt hành động thực tế, đâu là chiến lược tối ưu nhất?"},
            {"speaker": "master", "text": "Cốt tủy của Chu Dịch là Đạo Tùy Thời. Hãy giữ vững tâm định, thuận theo lẽ phải, minh bạch trong hành sự, ắt biến nguy thành an."},
            {"speaker": "host", "text": "Một góc nhìn thực sự khai sáng! Thầy có lời chân ngôn nào muốn đúc kết gửi tới người hỏi không ạ?"},
            {"speaker": "master", "text": "Tâm an thì trí sáng, thời đến thì hoa nở. Giữ tâm chính trực, kiên nhẫn tích lũy, ắt gặt hái thành tựu viên mãn."}
        ]

    chapters = [
        {"title": "Hồi 1: Tiếp Nhận Duyên Khởi", "desc": "Nêu câu hỏi và hoàn cảnh đương số"},
        {"title": "Hồi 2: Quái Tượng Hiển Lộ", "desc": f"Khám phá hình tượng quẻ {hex_name}"},
        {"title": "Hồi 3: Đàm Đạo Thời Vận", "desc": "Phân tích thế kẹt và cơ hội tiềm ẩn"},
        {"title": "Hồi 4: Chiến Lược Tùy Thời", "desc": "Hành động thực tế và tâm thế xử sự"},
        {"title": "Hồi 5: Đúc Kết Kim Chỉ Nam", "desc": "Chân ngôn xử thế và lời chúc đại cát"}
    ]

    full_show_notes = f"""# BẢN PHÂN TÍCH DỊCH LÝ CHUYÊN SÂU [{duration_mode.upper()}]
**Chương trình:** Cửu Nhị Luận Đạo · Podcast Dịch Học Chuyên Sâu
**Câu hỏi đương số:** "{question}"
**Quẻ chiêm bốc:** {hex_name}
**Phong cách đàm đạo:** {MODE_PROFILES.get(duration_mode, {}).get('desc', 'Chuyên sâu')}

---

### 1. Ý Tượng Quẻ & Bản Chất Triết Học
Quẻ {hex_name} mở ra thông điệp về sự vận động và chuyển hóa của vũ trụ. Không có trạng thái nào là tĩnh lặng bất biến. Sự vật phát triển đến cực điểm sẽ chuyển hóa sang trạng thái đối lập.

### 2. Phân Tích Thực Trạng & Hào Thế Hào Biến
- Hiện trạng: Năng lượng đang tích tụ, cần sự định tâm để phân biệt rõ thời cơ và cạm bẫy.
- Xu thế: Nếu giữ được đức kiên trinh, thuận theo thiên lý và quy luật tự nhiên, vận thế sẽ hanh thông rõ rệt.

### 3. Lời Khuyên Hành Động & Đạo Tùy Thời
- **Sự nghiệp & Tài chính:** Không manh động, tập trung xây nền móng vững chắc.
- **Quan hệ & Ứng xử:** Dĩ hòa vi quý, lắng nghe và thấu hiểu.
- **Tâm thế sống:** Giữ tâm tĩnh lặng như mặt hồ, lấy nhu thắng cương, thuận thời đắc vị.
"""

    return {
        "podcast_title": title,
        "hexagram_title": hex_name,
        "summary_verdict": "Tâm an thì trí sáng, thuận thời đắc vị ắt đại cát hanh thông.",
        "chapters": chapters,
        "dialogue": dialogue,
        "full_show_notes": full_show_notes
    }

if __name__ == "__main__":
    q = "Dự án mới của tôi có thuận lợi không?"
    data = generate_podcast_analysis(q, "Quẻ số 1: THIÊN ĐỊA BĨ", duration_mode="debate")
    print("Podcast Title:", data["podcast_title"])
    print("Turns:", len(data["dialogue"]))
