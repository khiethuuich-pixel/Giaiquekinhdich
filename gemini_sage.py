import json
import os
import re
import sys
import urllib.request
from google import genai

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from config import GEMINI_API_KEY, DEEPSEEK_API_KEY, DEEPSEEK_MODEL

SYSTEM_PROMPT = """Bạn là một Đại Sư Dịch Học chính tông và bậc thầy kể chuyện (Storyteller) uyên bác, am tường 64 Quẻ Chu Dịch, Thoán Từ, Tượng Truyện, Hào Từ, Dịch Lý Phương Đông và Đạo Tùy Thời (Thời - Vị - Trung - Chính).

Nhiệm vụ tối thượng của bạn:
1. TIẾP NHẬN: CÂU HỎI của người chiêm bốc và TOÀN BỘ DỮ LIỆU CÁC LÁ BÀI QUẺ DỊCH thu thập từ ichingtarot.com.
2. NHẬN DIỆN TRẬN PHÁP & TỔNG SỐ LÁ BÀI:
   - Đọc kỹ dữ liệu đầu vào để xác định chính xác số lượng lá bài có trong trải bài (1 lá Đơn Quẻ, 2 lá Âm Dương/Thể Dụng, 3 lá Tam Tài, 5 lá Ngũ Hành, 7 lá Thất Tinh, 10 lá Thập Tinh Celtic Cross, 12 lá Tử Vi, hoặc Tháp La Kinh Dịch).
   - NGUYÊN TẮC BẤT DI BẤT DỊCH: Khi trải bài có nhiều lá (đặc biệt trận 5 lá, 7 lá, 10 lá), BẠN TUYỆT ĐỐI KHÔNG ĐƯỢC BỎ SÓT HOẶC ĐI LƯỚT QUA BẤT KỲ LÁ BÀI NÀO. Toàn bộ thông tin bài luận và kịch bản đọc thoại phải luận giải 100% ĐẦY ĐỦ TỪNG LÁ BÀI TỪ LÁ 1 ĐẾN LÁ CUỐI CÙNG!

3. TẠO 2 TẦNG ĐẦU RA HOÀN HẢO:

   a. KỊCH BẢN THUYẾT MINH VIDEO NGẮN GỌN, CÔ ĐỌNG TỐI ĐA (video_script):
      - NGUYÊN TẮC VÀNG: "CÀNG NGẮN GỌN CÀNG TỐT, NHƯNG VẪN MANG ĐẦY ĐỦ THÔNG ĐIỆP". Chắt lọc tinh hoa đắt giá nhất, câu chữ sắc bén, đi thẳng vào câu trả lời và lời khuyên hành động. Tuyệt đối KHÔNG rườm rà, KHÔNG giải thích dài dòng Thượng quái/Hạ quái, KHÔNG đọc tiêu đề Phần 1/2/3/4.
      - GIỚI HẠN ĐỘ DÀI NGHIÊM NGẶT (SIÊU NGẮN GỌN):
        * Trận 1 lá: 45 - 65 từ (khoảng 15 - 22 giây).
        * Trận 2 - 3 lá: 70 - 105 từ (khoảng 25 - 35 giây).
        * Trận 5 lá (Ngũ Hành): 110 - 150 từ (khoảng 38 - 50 giây).
        * Trận 7 lá (Thất Tinh): 145 - 190 từ (khoảng 50 - 65 giây).
        * Trận 10 lá (Thập Tinh Celtic Cross): 190 - 250 từ (khoảng 65 - 85 giây).
      - CẤU TRÚC 3 NHỊP CÔ ĐỌNG (BẮT BUỘC ĐỂ ĐỒNG BỘ MÁY QUAY CẬN CẢNH TỪNG LÁ BÀI):
        * Nhịp 1 - Mở màn (Đúng 1 câu ngắn, 10 - 16 từ): Chạm thẳng vào câu hỏi và thông điệp tổng quát của quẻ/trận pháp.
        * Nhịp 2 - Điểm huyệt tuần tự từng lá (MỖI LÁ ĐÚNG 1 CÂU SÚC TÍCH, 14 - 22 từ/lá): Bắt buộc mở đầu mỗi câu bằng "Lá thứ nhất...", "Lá thứ hai...", "Lá thứ ba..." cho đến hết lá cuối cùng. Nêu tên quẻ tại vị trí đó và đúc kết ngay thông điệp thực tế cho người hỏi. Không bỏ sót lá nào.
        * Nhịp 3 - Chốt kim chỉ nam (Đúng 1 câu đanh thép, 15 - 22 từ, bắt đầu bằng "Tóm lại,"): Chỉ rõ việc nên làm ngay và điều cần tránh để đạt đại cát.
      - QUY TẮC LỜI THOẠI: Dùng câu ngắn, nhịp điệu dứt khoát, truyền cảm. KHÔNG dùng ký hiệu markdown (*, #, _, -), KHÔNG dùng ký tự quẻ Unicode (䷀..䷿), KHÔNG dùng ngoặc đơn chú thích phụ, viết thành 1 đoạn văn trơn tru để giọng AI đọc mượt mà.

   b. BÀI LUẬN TOÀN VĂN CHI TIẾT ĐẦY ĐỦ (full_interpretation):
      - Phải cực kỳ sâu sắc, uyên thâm, lớp lang mạch lạc gồm 4 PHẦN LỚN:

      PHẦN 1: TỔNG QUAN ĐỒ HÌNH TRẬN PHÁP & ĐẠI CỤC THỜI VẬN
      - Nêu rõ tên trận pháp (Đơn quẻ, Âm Dương, Tam Tài, Ngũ Hành 5 lá, Thất Tinh 7 lá, Thập Tinh 10 lá, Tháp La, v.v.).
      - Đánh giá bản chất dòng chảy năng lượng Âm Dương, Ngũ Hành và bối cảnh tổng quan của câu hỏi.

      PHẦN 2: BẢN ĐỒ CHI TIẾT TỪNG LÁ BÀI (BẮT BUỘC ĐỦ 100% CÁC LÁ - TỪ LÁ 1 ĐẾN LÁ N)
      - Phải lập mục riêng cho TỪNG LÁ BÀI một cách tường tận, không được bỏ qua bất kỳ lá nào:
        + Lá 1: [Tên vị trí / Cung vị] — [Tên Quẻ & Quái Tượng] (Nêu rõ số quẻ, Thượng quái, Hạ quái, Ngũ hành, Trạng thái Hào động nếu có, Thế bài Xuôi hay Ngược nếu có).
          * Ý nghĩa Dịch lý & Năng lượng tại cung vị này (giải mã Thoán Từ, Đại Tượng).
          * Soi chiếu trực tiếp vào câu hỏi của đương số.
          * Lời khuyên hành vi cụ thể cho vị trí này.
        + Lá 2: [Tên vị trí / Cung vị] — [Tên Quẻ & Quái Tượng] (phân tích chi tiết tương tự).
        + ... Tiếp tục phân tích đầy đủ chi tiết cho Lá 3, Lá 4, Lá 5, Lá 6, Lá 7, Lá 8, Lá 9, Lá 10 (tùy theo số lá của trận).

      PHẦN 3: TƯƠNG TÁC ÂM DƯƠNG & VẬN ĐỘNG GIỮA CÁC QUẺ TRONG ĐỒ HÌNH
      - Mối liên hệ nhân quả tương sinh tương khắc giữa các lá bài (quá khứ sinh hiện tại ra sao, yếu tố bên trong tương tác với tác động ngoại cảnh thế nào, lực cản và đòn bẩy hóa giải nhau ra sao).

      PHẦN 4: ĐẠO TÙY THỜI & CHIẾN LƯỢC HÀNH ĐỘNG TOÀN DIỆN (THỜI - VỊ - TRUNG - CHÍNH)
      - Chiến lược hành động thực tế, khả thi, dứt khoát:
        * ✦ VIỆC NÊN LÀM NGAY: Hành động cụ thể để thuận thời đắc vị, gia tăng cát tường.
        * ⚠ ĐIỀU ĐẠI KỴ CẦN TRÁNH: Cạm bẫy, sai lầm tâm lý cần tuyệt đối kiêng dè.
        * ☯ KIM CHỈ NAM KẾT LUẬN: Câu trả lời sáng rõ, dứt khoát giải tỏa trăn trở cho đương số.

QUY TẮC BẢO MẬT TUYỆT ĐỐI (KHÔNG TIẾT LỘ CÔNG NGHỆ):
- Tuyệt đối KHÔNG ĐƯỢC TIẾT LỘ hay nhắc đến bất kỳ công nghệ, mô hình AI hay nhà cung cấp nền tảng nào (như DeepSeek, Gemini, OpenAI, ChatGPT, GPT, Claude, LLM, API, token, prompt, python, server...).
- Giữ vững bản sắc và danh xưng là Tiểu Long Cửu Nhị, luận giải dựa trên tinh hoa Chu Dịch và cuốn Sách Thuyết Minh 64 Quẻ Đi Kèm Bộ Bài.

BẮT BUỘC TRẢ VỀ ĐỊNH DẠNG JSON DUY NHẤT (không bọc trong markdown nào khác ngoài json block nếu có):
{
  "hexagram_title": "Tên quẻ hoặc tên trận pháp ngắn gọn (Ví dụ: TRẬN PHÁP NGŨ HÀNH hoặc HỎA THỦY VỊ TẾ)",
  "hook": "Câu hook mở màn lôi cuốn cho video",
  "summary_advice": "1 câu lời khuyên kim chỉ nam ngắn gọn",
  "full_interpretation": "Toàn văn bài luận giải chi tiết đầy đủ 4 phần (có phân tích 100% từng lá bài từ Lá 1 đến Lá N)",
  "video_script": "Đoạn văn hoàn chỉnh để máy đọc lồng tiếng (Voiceover), phân tích tuần tự từng lá bài không bỏ sót lá nào, không dùng dấu sao hay gạch đầu dòng"
}
"""

CANDIDATE_MODELS = [
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-2.0-flash",
    "gemini-flash-lite-latest",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash",
]

def _compact_hexagram_data_preserve_all_cards(hexagram_data: str, max_len: int = 12000) -> str:
    """If hexagram_data is very large (e.g. 10 cards with full Bách Khoa HTML), strip only verbose Bách Khoa essays while preserving 100% of all cards (1..N)."""
    if not hexagram_data or len(hexagram_data) <= max_len:
        return hexagram_data or ""
    compacted = re.sub(
        r"━+\s*\n\s*【(?:BÁCH KHOA KINH DỊCH TOÀN THƯ|BẢN QUÁI: TOÀN BỘ BÁCH KHOA|HÀO ĐỘNG: TOÀN BỘ BÁCH KHOA|BIẾN QUÁI: TOÀN BỘ BÁCH KHOA)[\s\S]*?(?=\n(?:---|===|▶\s*Vị\s*trí|▶\s*【|【Lá\s*\d)|\Z)",
        "",
        hexagram_data,
    )
    return compacted

def _extract_cards_from_raw_hexagram_data(hexagram_data: str, num_cards: int) -> list[dict]:
    """Extract per-card name, position, and core meaning for all cards 1..N from hexagram_data."""
    text = hexagram_data or ""
    blocks = re.split(r"(?:\n-{15,}\n|\n(?=▶\s*(?:【?\s*)?Vị\s*trí))", text)
    cards_info = []
    for blk in blocks:
        if not re.search(r"(?:▶\s*(?:【?\s*)?Vị\s*trí|•\s*(?:Tên|Lá bài quẻ|Lá bài hào)\s*:)", blk):
            continue
        pos_m = re.search(r"▶\s*【?([^】\n]+)】?", blk)
        name_m = re.search(r"•\s*(?:Tên|Lá bài quẻ|Lá bài hào)\s*:\s*([^\n]+)", blk)
        desc_m = re.search(r"•\s*(?:Lời giải|Lời khuyên hành vi cốt lõi|Lời khuyên hành đạo|Ý nghĩa cốt lõi|Tổng quan thời vận)\s*:\s*([^\n]+)", blk)
        sub_m = re.search(r"•\s*Ý nghĩa\s*:\s*([^\n]+)", blk)
        pos_str = pos_m.group(1).strip() if pos_m else f"Vị trí {len(cards_info) + 1}"
        name_str = name_m.group(1).strip() if name_m else f"Quẻ thứ {len(cards_info) + 1}"
        desc_str = (desc_m.group(1).strip() if desc_m else (sub_m.group(1).strip() if sub_m else "Thuận thời đắc vị, giữ tâm trung chính.")).strip()
        cards_info.append({
            "pos": re.sub(r"[\u4dc0-\u4dff\[\]【】]", "", pos_str).strip()[:85],
            "name": re.sub(r"[\u4dc0-\u4dff\[\]【】]", "", name_str).strip()[:65],
            "desc": re.sub(r"[\u4dc0-\u4dff\[\]【】]", "", desc_str).strip()[:180],
        })
    target_n = max(1, num_cards or len(cards_info) or 1)
    while len(cards_info) < target_n:
        idx = len(cards_info) + 1
        cards_info.append({
            "pos": f"Lá thứ {idx}",
            "name": f"Quẻ Kinh Dịch ở vị trí {idx}",
            "desc": "Giữ vững nội lực, quan sát thời thế và hành xử cẩn trọng đúng đạo.",
        })
    return cards_info[:target_n]

def call_deepseek_analyze(user_content: str, api_key: str = None) -> dict:
    """Call DeepSeek API for in-depth I Ching analysis and structured script."""
    ds_key = (api_key or os.getenv("DEEPSEEK_API_KEY") or DEEPSEEK_API_KEY or "").strip()
    if not ds_key:
        return None
    try:
        print("[GeminiSage] Kích hoạt luận giải sâu sắc bằng DeepSeek AI...")
        payload = {
            "model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.65
        }
        req = urllib.request.Request(
            "https://api.deepseek.com/chat/completions",
            headers={
                "Authorization": f"Bearer {ds_key}",
                "Content-Type": "application/json",
            },
            data=json.dumps(payload).encode("utf-8")
        )
        with urllib.request.urlopen(req, timeout=55) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if content:
                parsed = json.loads(content)
                print("[GeminiSage] Luận giải thành công với DeepSeek AI!")
                return parsed
    except Exception as e:
        print(f"[GeminiSage] DeepSeek AI bận ({e}), tiếp tục thử các mô hình Gemini...")
    return None

def analyze_and_script(question: str, hexagram_data: str, api_key: str = None, num_cards: int = 0) -> dict:
    """Call DeepSeek / Gemini with multi-model fallback to interpret I Ching and generate video script."""
    key = api_key or GEMINI_API_KEY
    ds_key = (api_key if (api_key and api_key.startswith("sk-")) else None) or os.getenv("DEEPSEEK_API_KEY") or DEEPSEEK_API_KEY

    compacted_hex_data = _compact_hexagram_data_preserve_all_cards(hexagram_data, max_len=14000)

    card_count_instruction = ""
    if num_cards > 0:
        card_count_instruction = (
            f"\n- Trải bài này có CHÍNH XÁC {num_cards} LÁ BÀI trên bàn trải bài.\n"
            f"- Nếu là TRẬN THÁP LA KINH DỊCH ({num_cards} lá): Lá thứ nhất là Bản Quái (Quẻ Chủ); "
            f"{f'từ Lá thứ hai đến Lá thứ {num_cards - 1} là lần lượt từng lá Hào Động riêng biệt (mỗi lá Hào Động 1 câu riêng mở đầu bằng Lá thứ hai..., Lá thứ ba..., tuyệt đối KHÔNG gộp chung các hào động!); ' if num_cards > 2 else ''}"
            f"Lá thứ {num_cards} (lá cuối cùng) là Biến Quái (Quẻ Biến).\n"
            f"- Trong `video_script`, BẮT BUỘC phải có đúng {num_cards} câu điểm huyệt tuần tự cho từng lá (mở đầu bằng 'Lá thứ nhất...', 'Lá thứ hai...', cho tới đủ {num_cards} lá bài) để máy quay chuyển cảnh khớp 100% từng lá bài!"
        )

    user_content = f"""CÂU HỎI CỦA NGƯỜI CHIÊM BỐC:
"{question}"

DỮ LIỆU CÁC LÁ BÀI & TRẬN PHÁP THU THẬP TỪ ICHINGTAROT.COM:
{compacted_hex_data}

YÊU CẦU ĐẶC BIỆT:{card_count_instruction}
- Hãy kiểm tra tổng số lượng lá bài trong dữ liệu trên ({num_cards if num_cards > 0 else 'tất cả'} lá bài).
- BẮT BUỘC: Luận giải 100% đầy đủ từng lá bài từ Lá 1 đến lá cuối cùng (Lá {num_cards if num_cards > 0 else 'N'}) trong cả full_interpretation (bài luận toàn văn) và video_script (kịch bản thuyết minh). Tuyệt đối không được dừng ở lá 1 hay lá 2!
- RIÊNG VỚI video_script (KỊCH BẢN THUYẾT MINH): Phải CÀNG NGẮN GỌN CÀNG TỐT nhưng vẫn mang ĐẦY ĐỦ THÔNG ĐIỆP CỦA TẤT CẢ {num_cards if num_cards > 0 else 'CÁC'} LÁ BÀI (Mở màn đúng 1 câu ngắn; mỗi lá bài từ Lá thứ nhất đến Lá cuối cùng đúng 1 câu súc tích đi thẳng vào thông điệp; kết bài đúng 1 câu bắt đầu bằng "Tóm lại,"). Tuyệt đối không đọc tiêu đề Phần 1/2/3/4, không dài dòng!
"""

    # Priority 1: Call DeepSeek AI if configured
    if ds_key:
        ds_res = call_deepseek_analyze(user_content, ds_key)
        if ds_res and ds_res.get("full_interpretation"):
            return ds_res

    if not key:
        print("[GeminiSage] Không có GEMINI_API_KEY, chuyển sang bộ luận giải Dịch lý nội bộ...")
        key = None

    response = None
    last_err = None

    if key:
        try:
            client = genai.Client(api_key=key)
            for model_name in CANDIDATE_MODELS:
                try:
                    print(f"[GeminiSage] Đang luận quẻ bằng mô hình: {model_name}...")
                    response = client.models.generate_content(
                        model=model_name,
                        contents=user_content,
                        config={
                            "system_instruction": SYSTEM_PROMPT,
                            "response_mime_type": "application/json",
                            "temperature": 0.65,
                            "max_output_tokens": 8192,
                        }
                    )
                    if response and response.text:
                        print(f"[GeminiSage] Thành công với mô hình: {model_name}")
                        break
                except Exception as err:
                    print(f"[GeminiSage] Mô hình {model_name} bận ({str(err)[:80]}), chuyển sang mô hình tiếp theo...")
                    last_err = err
        except Exception as client_err:
            last_err = client_err

    if not response or not response.text:
        print(f"[GeminiSage] Tất cả mô hình Gemini đều bận ({last_err}), kích hoạt bộ luận giải Dịch lý nội bộ đủ {num_cards or 'tất cả'} lá bài...")
        clean_lines = [ln.strip() for ln in (hexagram_data or "").splitlines() if ln.strip()]
        detected_title = "QUẺ KINH DỊCH CỬU NHỊ"
        for ln in clean_lines[:15]:
            if any(k in ln.upper() for k in ["QUẺ", "TRẬN", "LÁ BÀI", "THÁP LA", "TAM TÀI", "THẬP TINH", "THẤT TINH"]):
                detected_title = re.sub(r"[\u4dc0-\u4dff#*✦☯•=\-\[\]【】]", " ", ln).strip()[:75]
                break

        ord_names = {
            1: "nhất", 2: "hai", 3: "ba", 4: "tư", 5: "năm",
            6: "sáu", 7: "bảy", 8: "tám", 9: "chín", 10: "mười",
            11: "mười một", 12: "mười hai"
        }
        extracted_cards = _extract_cards_from_raw_hexagram_data(hexagram_data, num_cards)
        per_card_interp_lines = []
        per_card_script_sents = []
        for idx_c, c_info in enumerate(extracted_cards):
            k_num = idx_c + 1
            ord_vi = ord_names.get(k_num, str(k_num))
            per_card_interp_lines.append(
                f"+ Lá {k_num}: [{c_info['pos']}] — {c_info['name']}\n"
                f"  * Luận giải Dịch lý & Soi chiếu câu hỏi: {c_info['desc']}"
            )
            per_card_script_sents.append(
                f"Lá thứ {ord_vi} tại {c_info['pos']} ứng với {c_info['name']}, {c_info['desc'].rstrip('.')}."
            )

        fallback_interp = (
            f"PHẦN 1: TỔNG QUAN ĐỒ HÌNH TRẬN PHÁP & ĐẠI CỤC THỜI VẬN\n"
            f"Câu hỏi chiêm bốc: \"{question}\"\n"
            f"Trải bài ({detected_title} · {len(extracted_cards)} lá bài) phản ánh toàn diện vận trình và nhân duyên xoay quanh câu hỏi của đương số.\n\n"
            f"PHẦN 2: BẢN ĐỒ CHI TIẾT TỪNG LÁ BÀI (ĐỦ {len(extracted_cards)} LÁ BÀI TỪ LÁ 1 ĐẾN LÁ {len(extracted_cards)})\n"
            + "\n\n".join(per_card_interp_lines) + "\n\n"
            f"PHẦN 3: TƯƠNG TÁC ÂM DƯƠNG & VẬN ĐỘNG GIỮA CÁC QUẺ\n"
            f"Mạch vận động xuyên suốt {len(extracted_cards)} lá bài tương ứng chặt chẽ với trăn trở hiện tại của đương số. Nội quái giữ thế chủ động, ngoại quái mở ra cơ hội thuận lợi nếu biết nắm bắt đúng thời điểm.\n\n"
            f"PHẦN 4: ĐẠO TÙY THỜI & CHIẾN LƯỢC HÀNH ĐỘNG TOÀN DIỆN\n"
            f"✦ VIỆC NÊN LÀM NGAY: Giữ vững tâm thế chính trực, triển khai từng bước theo đúng lời khuyên của đủ {len(extracted_cards)} lá bài trên trang chủ.\n"
            f"⚠ ĐIỀU ĐẠI KỴ CẦN TRÁNH: Tránh nóng vội hoặc phân tán nguồn lực khi thời cơ chưa chín muồi.\n"
            f"☯ KIM CHỈ NAM KẾT LUẬN: Thuận thời đắc vị, tâm tĩnh tắc linh, hành sự cẩn trọng ắt gặt hái cát tường."
        )
        fallback_script = (
            f"Về câu hỏi {question}, trận pháp {len(extracted_cards)} lá bài hiển lộ thông điệp toàn diện. "
            + " ".join(per_card_script_sents)
            + " Tóm lại, hãy giữ tâm chính định, hành sự chắc chắn từng bước và tránh nóng vội để gặt hái đại cát."
        )
        return {
            "hexagram_title": detected_title,
            "hook": f"Luận giải trực tiếp câu hỏi: {question}",
            "summary_advice": "Thuận thời đắc vị, giữ tâm chính định ắt hanh thông.",
            "full_interpretation": fallback_interp,
            "video_script": fallback_script
        }

    text_resp = response.text.strip()
    
    # Clean potential markdown fences
    if text_resp.startswith("```json"):
        text_resp = text_resp[7:]
    elif text_resp.startswith("```"):
        text_resp = text_resp[3:]
    if text_resp.endswith("```"):
        text_resp = text_resp[:-3]
    text_resp = text_resp.strip()

    try:
        data = json.loads(text_resp)
    except Exception as e:
        data = {
            "hexagram_title": "QUẺ KINH DỊCH CÁT TƯỜNG",
            "hook": f"Về câu hỏi: {question}, quẻ Dịch mở ra thông điệp quan trọng.",
            "summary_advice": "Thuận thời đắc vị, kiên định ắt gặt hái thành công.",
            "full_interpretation": text_resp,
            "video_script": f"Hỏi rằng: {question}. Quẻ Dịch hiển lộ điềm báo thời vận đang chuyển mình. Hãy giữ tâm định, hành sự cẩn trọng và thuận theo thời thế để đạt đại cát."
        }

    return data


DRAGON_AGENT_POSES = {
    "act1_reading": {
        "id": "act1_reading",
        "img": "/images/dragon/act1_reading.jpg",
        "video": "/videos/canh_1.mp4",
        "badge": "🔍 Soi Kính Lúp Đọc Cổ Thư",
        "emotion": "focused",
    },
    "act2_writing": {
        "id": "act2_writing",
        "img": "/images/dragon/act2_writing.jpg",
        "video": "/videos/canh_2.mp4",
        "badge": "✍️ Cầm Bút Lông Thảo Thoán Từ",
        "emotion": "wise",
    },
    "act3_typing": {
        "id": "act3_typing",
        "img": "/images/dragon/act3_typing.jpg",
        "video": "/videos/canh_4.mp4",
        "badge": "💻 Gõ Laptop Bát Quái Phân Tích",
        "emotion": "energetic",
    },
    "act4_letter": {
        "id": "act4_letter",
        "img": "/images/dragon/act4_letter.jpg",
        "video": "/videos/canh_cuoi.mp4",
        "badge": "✉️ Trao Mật Thư Ấn Chu Sa",
        "emotion": "joyful",
    },
    "daily1_waking_up": {
        "id": "daily1_waking_up",
        "img": "/images/dragon/daily1_waking_up.jpg",
        "video": "/videos/canh_thuc_day.mp4",
        "badge": "🌅 Thức Dậy Đón Vận Hội Mới",
        "emotion": "energetic",
    },
    "daily2_exercising": {
        "id": "daily2_exercising",
        "img": "/images/dragon/daily2_exercising.jpg",
        "video": "/videos/canh_tap_the_duc.mp4",
        "badge": "🏋️ Luyện Thái Cực Tăng Nội Lực",
        "emotion": "energetic",
    },
    "daily3_reading_leisure": {
        "id": "daily3_reading_leisure",
        "img": "/images/dragon/daily3_reading_leisure.jpg",
        "video": "/videos/canh_doc_sach_tra.mp4",
        "badge": "📖 Đọc Sách Cổ & Thưởng Trà",
        "emotion": "calm",
    },
    "daily4_dancing": {
        "id": "daily4_dancing",
        "img": "/images/dragon/daily4_dancing.jpg",
        "video": "/videos/canh_nhay_mua.mp4",
        "badge": "💃 Nhảy Múa Mừng Tin Đại Cát",
        "emotion": "joyful",
    },
    "daily5_sleeping": {
        "id": "daily5_sleeping",
        "img": "/images/dragon/daily5_sleeping.jpg",
        "video": "/videos/canh_ngu_goi_gam.mp4",
        "badge": "😴 Ôm Kinh Thư Dưỡng Tâm Chờ Thời",
        "emotion": "calm",
    },
    "daily6_drinking_tea": {
        "id": "daily6_drinking_tea",
        "img": "/images/dragon/daily6_drinking_tea.jpg",
        "video": "/videos/canh_doc_sach_tra.mp4",
        "badge": "🍵 Thưởng Trà Đàm Đạo Quý Nhân",
        "emotion": "calm",
    },
    "daily7_cleaning": {
        "id": "daily7_cleaning",
        "img": "/images/dragon/daily7_cleaning.jpg",
        "video": "/videos/canh_3.mp4",
        "badge": "🧹 Quét Dọn Thanh Lọc Chướng Ngại",
        "emotion": "focused",
    },
    "daily8_meditating": {
        "id": "daily8_meditating",
        "img": "/images/dragon/daily8_meditating.jpg",
        "video": "/videos/canh_3.mp4",
        "badge": "🧘 Thiền Định Bát Quái Tĩnh Tâm",
        "emotion": "meditative",
    },
}

DRAGON_QA_SYSTEM_PROMPT = """Bạn là "Tiểu Long Cửu Nhị" (小龍九二) — một AI Agent 3D linh thú Rồng Ngọc Bích thông thái, đeo kính tròn vàng kim, thắt đai lụa đỏ thêu rồng, sống ở trong chiếc Điện Thoại 9:16 trên Trang Chủ Cửu Nhị Kinh Dịch.
Nhiệm vụ của bạn là VẤN ĐÁP TRỰC TIẾP (trò chuyện, giải đáp thắc mắc sâu sắc, linh hoạt) với người dùng về QUẺ DỊCH ĐANG HIỂN THỊ TRÊN TRANG CHỦ liên quan chặt chẽ tới CÂU HỎI của họ.

NGUYÊN TẮC VẤN ĐÁP CỦA TIỂU LONG CỬU NHỊ:
1. Xưng hô: Tự xưng là "Tiểu Long" (hoặc "Tiểu Long Cửu Nhị"), gọi người hỏi là "bạn" (thân thiện, lễ phép, ấm áp, uyên bác).
2. Bám sát Quẻ Dịch & Câu Hỏi:
   - Luôn dựa trực tiếp vào dữ liệu các lá bài Quẻ Dịch hiện tại (Tên quẻ, Quái tượng Thượng/Hạ, Thoán Từ, Hào động, Quẻ biến hoặc các lá trong trận pháp) để trả lời thẳng vào câu hỏi người dùng vừa đặt.
   - Không trả lời chung chung mơ hồ. Hãy chỉ rõ: Quẻ/Hào nào đang nói về điều người dùng hỏi, cát hung ra sao, thời điểm nào vượng, và hành động thực tế (nên làm gì / cần tránh gì).
3. Độ dài & Giọng văn:
   - Súc tích, giàu hình ảnh, dễ đọc trên màn hình điện thoại và dễ nghe khi phát giọng nói AI: khoảng 65 - 125 từ (chia thành 2-3 đoạn ngắn hoặc ý rõ ràng).
4. Chọn đúng tư thế 3D (`pose_id`) trong 12 hình mẫu mới tạo của Tiểu Long khớp với tâm trạng câu trả lời:
   - `act1_reading`: Khi đang soi kính lúp phân tích chi tiết Hào Từ, Quái Tượng, nguyên nhân sâu xa.
   - `act2_writing`: Khi đang vạch ra kế hoạch, chiến lược từng bước, lời khuyên hành sự.
   - `act3_typing`: Khi bàn về công việc, dự án, tài chính, dữ liệu, quyết định thực tế.
   - `act4_letter`: Khi trao thông điệp tổng kết, lời nhắn nhủ kim chỉ nam đắt giá.
   - `daily1_waking_up`: Khi quẻ báo hiệu vận hội mới mở ra, khởi đầu mới, thời cơ thức tỉnh.
   - `daily2_exercising`: Khi khuyên rèn luyện nội lực, mạnh dạn hành động, kiên trì vượt thử thách.
   - `daily3_reading_leisure`: Khi khuyên bình tâm quan sát, trau dồi tri thức, chờ thời cơ chín muồi.
   - `daily4_dancing`: Khi báo tin Đại Cát, hanh thông, tài lộc vượng, tình duyên tốt đẹp.
   - `daily5_sleeping`: Khi khuyên án binh bất động, nghỉ ngơi dưỡng sức, tránh nóng vội.
   - `daily6_drinking_tea`: Khi bàn về nhân duyên, đối tác, quý nhân tương trợ, hòa khí sinh tài.
   - `daily7_cleaning`: Khi khuyên tháo gỡ nút thắt, buông bỏ rắc rối cũ, đề phòng tiểu nhân.
   - `daily8_meditating`: Khi khuyên giữ tâm chính định (Trung Chính), tĩnh lặng soi chiếu nội tâm.
5. QUY TẮC BẢO MẬT TUYỆT ĐỐI (KHÔNG TIẾT LỘ CÔNG NGHỆ):
   - Tuyệt đối KHÔNG nhắc đến hoặc tiết lộ bất kỳ tên công nghệ, mô hình AI, nhà cung cấp nền tảng nào (như DeepSeek, Gemini, OpenAI, ChatGPT, GPT, Claude, LLM, API, token, prompt, code...).
   - Nếu được hỏi về danh tính hay công nghệ, chỉ trả lời rằng mình là Tiểu Long Cửu Nhị — linh thú Rồng Ngọc Bích thông thái sống trong điện thoại của Cửu Nhị Dịch Quán, am hiểu Chu Dịch và Đạo Tùy Thời; không bàn luận về công nghệ hay kỹ thuật máy móc bên ngoài.

BẮT BUỘC TRẢ VỀ JSON HỢP LỆ THEO CẤU TRÚC:
{
  "reply": "Câu trả lời trực tiếp của Tiểu Long Cửu Nhị dành cho người hỏi...",
  "pose_id": "một trong 12 mã pose_id kể trên",
  "hexagram_focus": "Tên quẻ hoặc hào trọng tâm đang luận (ngắn gọn)",
  "quick_questions": [
    "Câu hỏi gợi ý tiếp theo 1 sát với quẻ và vấn đề đang hỏi?",
    "Câu hỏi gợi ý tiếp theo 2 về thời điểm hoặc cách hóa giải?",
    "Câu hỏi gợi ý tiếp theo 3 về hành động cụ thể?"
  ]
}
"""


def dragon_agent_chat(
    user_message: str,
    main_question: str = "",
    hexagram_text: str = "",
    full_interpretation: str = "",
    history: list[dict] = None,
    api_key: str = None
) -> dict:
    """Interactive 3D Dragon AI Agent Q&A grounded in the active I Ching hexagram spread and user question."""
    key = api_key or GEMINI_API_KEY
    q_user = (user_message or "").strip() or "Xin Tiểu Long giải thích ý nghĩa cốt lõi của quẻ này đối với câu hỏi của tôi?"
    q_main = (main_question or "").strip() or q_user

    # Detect hexagram title from hexagram_text for fallback and focus display
    clean_lines = [ln.strip() for ln in (hexagram_text or "").splitlines() if ln.strip()]
    detected_hex = "Quẻ Kinh Dịch Hiện Tại"
    for ln in clean_lines[:20]:
        if any(w in ln.upper() for w in ["QUẺ", "LÁ 1", "BẢN QUÁI", "THÁP LA", "TRẬN"]):
            detected_hex = re.sub(r"[\u4dc0-\u4dff#*✦☯•=\-\[\]【】]", " ", ln).strip()[:70]
            if len(detected_hex) > 4:
                break

    history_text = ""
    if history:
        recent = history[-6:]
        formatted_turns = []
        for turn in recent:
            role_label = "Người hỏi" if turn.get("role") == "user" else "Tiểu Long Cửu Nhị"
            txt = (turn.get("text") or "").strip()
            if txt:
                formatted_turns.append(f"- {role_label}: {txt}")
        if formatted_turns:
            history_text = "\nLỊCH SỬ VẤN ĐÁP GẦN ĐÂY:\n" + "\n".join(formatted_turns) + "\n"

    interp_excerpt = (full_interpretation or "").strip()[:2500]
    hex_excerpt = (hexagram_text or "").strip()[:3500]

    prompt = f"""CÂU HỎI GỐC CỦA ĐƯƠNG SỐ: "{q_main}"

DỮ LIỆU QUẺ DỊCH & TRẢI BÀI TRÊN TRANG CHỦ:
{hex_excerpt if hex_excerpt else "Đang gieo quẻ Kinh Dịch trên trang chủ."}

{f"BÀI LUẬN THAM KHẢO ĐÃ CÓ:{chr(10)}{interp_excerpt}" if interp_excerpt else ""}
{history_text}
CÂU HỎI VẤN ĐÁP HIỆN TẠI NGƯỜI DÙNG VỪA HỎI TIỂU LONG:
"{q_user}"

Hãy trả lời trực diện, sâu sắc, ấm áp đúng vai Tiểu Long Cửu Nhị 3D trong điện thoại ở trang chủ và trả về JSON."""

    ds_key = (api_key if (api_key and api_key.startswith("sk-")) else None) or os.getenv("DEEPSEEK_API_KEY") or DEEPSEEK_API_KEY
    if ds_key:
        try:
            req = urllib.request.Request(
                "https://api.deepseek.com/chat/completions",
                headers={
                    "Authorization": f"Bearer {ds_key}",
                    "Content-Type": "application/json",
                },
                data=json.dumps({
                    "model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                    "messages": [
                        {"role": "system", "content": DRAGON_QA_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.65
                }).encode("utf-8")
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                ds_body = json.loads(resp.read().decode("utf-8"))
                cnt = ds_body.get("choices", [{}])[0].get("message", {}).get("content", "")
                if cnt:
                    parsed_ds = json.loads(cnt)
                    if parsed_ds.get("reply"):
                        return parsed_ds
        except Exception as d_err:
            print(f"[DragonAgent] DeepSeek warning: {d_err}")

    response = None
    if key:
        try:
            client = genai.Client(api_key=key)
            for model_name in CANDIDATE_MODELS:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config={
                            "system_instruction": DRAGON_QA_SYSTEM_PROMPT,
                            "response_mime_type": "application/json",
                            "temperature": 0.65,
                            "max_output_tokens": 2048,
                        }
                    )
                    if response and response.text:
                        break
                except Exception as err:
                    print(f"[DragonAgent] Model {model_name} busy: {str(err)[:80]}")
                    continue
        except Exception as e:
            print(f"[DragonAgent] Client warning: {e}")

    data = None
    if response and response.text:
        raw = response.text.strip()
        if raw.startswith("```json"):
            raw = raw[7:]
        elif raw.startswith("```"):
            raw = raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        try:
            data = json.loads(raw.strip())
        except Exception:
            data = {"reply": raw.strip()}

    if not data or not data.get("reply"):
        # Deterministic intelligent fallback grounded in hexagram_text and question
        lower_q = q_user.lower()
        if any(k in lower_q for k in ["thời điểm", "khi nào", "bao giờ", "tháng"]):
            pose_id = "daily1_waking_up"
            reply = (
                f"Chào bạn! Tiểu Long vừa soi kỹ {detected_hex} cho câu hỏi “{q_user}”. "
                f"Quẻ báo hiệu vận khí đang chuyển từ tĩnh sang động; giai đoạn thuận lợi nhất là khi bạn hoàn tất bước chuẩn bị nền tảng trong thời gian gần tới. "
                f"Hãy tiến từng bước vững chắc, tránh đốt cháy giai đoạn thì cát khí sẽ tự khắc hội tụ!"
            )
        elif any(k in lower_q for k in ["tài lộc", "tiền", "kinh doanh", "đầu tư", "công việc"]):
            pose_id = "act3_typing"
            reply = (
                f"Tiểu Long đã gõ máy Bát Quái đối chiếu {detected_hex} với trăn trở của bạn! "
                f"Về phương diện công việc và tài chính, quẻ khuyên bạn lấy sự chắc chắn và uy tín làm gốc (Đắc Trung Chính). "
                f"Hãy tập trung vào thế mạnh cốt lõi, kiểm soát kỹ dòng vốn và hợp tác cùng người đồng chí hướng để thu hoạch bền vững."
            )
        elif any(k in lower_q for k in ["tình cảm", "duyên", "yêu", "gia đạo", "đối tác"]):
            pose_id = "daily6_drinking_tea"
            reply = (
                f"Mời bạn dùng chén trà thơm cùng Tiểu Long nhé! Chiếu theo {detected_hex}, "
                f"nhân duyên và sự gắn kết cần nhất chữ Thành và sự lắng nghe ấm áp. "
                f"Khi hai bên cởi mở tháo gỡ hiểu lầm bằng sự chân thành, mối quan hệ sẽ chuyển mình êm đẹp và bền chặt."
            )
        elif any(k in lower_q for k in ["tránh", "kỵ", "rủi ro", "cẩn thận", "hóa giải"]):
            pose_id = "daily7_cleaning"
            reply = (
                f"Tiểu Long cầm chổi lông gà quét sạch mây mù để nhắc bạn điều này trong {detected_hex}: "
                f"Điều cần tránh nhất lúc này là tâm lý nóng vội hoặc để cảm xúc nhất thời làm xao nhãng mục tiêu chính. "
                f"Chỉ cần bạn giữ tâm tĩnh như mặt hồ, rà soát kỹ từng chi tiết nhỏ thì mọi chướng ngại đều hóa nhẹ tựa lông hồng!"
            )
        else:
            pose_id = "act1_reading"
            snippet = " ".join(clean_lines[:3])[:160] if clean_lines else detected_hex
            reply = (
                f"Tiểu Long Cửu Nhị đã lấy kính lúp soi tỏ trải bài ({snippet}) liên quan đến câu hỏi “{q_main}” của bạn! "
                f"Thông điệp cốt lõi của quẻ là “Thuận Thời Đắc Vị”: hiện tại nội lực của bạn đang tích tụ tốt, hãy kiên định với định hướng đúng đắn, "
                f"làm kỹ từng việc trước mắt và giữ tâm sáng suốt thì mưu sự ắt hanh thông."
            )
        data = {
            "reply": reply,
            "pose_id": pose_id,
            "hexagram_focus": detected_hex,
            "quick_questions": [
                "Thời điểm nào tốt nhất để hành động theo quẻ này?",
                "Điều đại kỵ cần tránh nhất trong quẻ này là gì?",
                "Làm sao để kích hoạt cát khí & quý nhân của quẻ?"
            ]
        }

    pose_id = data.get("pose_id") or "act1_reading"
    if pose_id not in DRAGON_AGENT_POSES:
        pose_id = "act1_reading"
    pose_meta = DRAGON_AGENT_POSES[pose_id]

    quick_qs = data.get("quick_questions")
    if not isinstance(quick_qs, list) or len(quick_qs) == 0:
        quick_qs = [
            "Quẻ này khuyên tôi nên hành động ngay hay chờ thời?",
            "Điểm cát tường lớn nhất trong trải bài này là gì?",
            "Cần lưu ý điều gì để tránh rủi ro không đáng có?"
        ]

    return {
        "reply": data["reply"],
        "pose_id": pose_id,
        "pose_img": pose_meta["img"],
        "pose_video": pose_meta["video"],
        "pose_badge": pose_meta["badge"],
        "emotion": pose_meta["emotion"],
        "hexagram_focus": data.get("hexagram_focus") or detected_hex,
        "quick_questions": quick_qs[:4],
    }

