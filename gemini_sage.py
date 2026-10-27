import json
import re
import sys
from google import genai

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from config import GEMINI_API_KEY

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
    "gemini-flash-lite-latest",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash",
    "gemini-flash-latest",
    "gemini-3-flash-preview",
    "gemini-3.7-flash",
    "gemini-3.8-flash"
]

def analyze_and_script(question: str, hexagram_data: str, api_key: str = None) -> dict:
    """Call Gemini with multi-model fallback to interpret I Ching and generate video script."""
    key = api_key or GEMINI_API_KEY
    if not key:
        raise ValueError("Chưa có GEMINI_API_KEY. Vui lòng nhập API Key để tiếp tục.")

    client = genai.Client(api_key=key)

    user_content = f"""CÂU HỎI CỦA NGƯỜI CHIÊM BỐC:
"{question}"

DỮ LIỆU CÁC LÁ BÀI & TRẬN PHÁP THU THẬP TỪ ICHINGTAROT.COM:
{hexagram_data}

YÊU CẦU ĐẶC BIỆT:
- Hãy kiểm tra tổng số lượng lá bài trong dữ liệu trên.
- BẮT BUỘC: Luận giải 100% đầy đủ từng lá bài từ Lá 1 đến lá cuối cùng trong cả full_interpretation (bài luận toàn văn) và video_script (kịch bản thuyết minh).
- RIÊNG VỚI video_script (KỊCH BẢN THUYẾT MINH): Phải CÀNG NGẮN GỌN CÀNG TỐT nhưng vẫn mang ĐẦY ĐỦ THÔNG ĐIỆP (Mở màn đúng 1 câu ngắn; mỗi lá bài từ Lá thứ nhất đến Lá cuối cùng đúng 1 câu súc tích đi thẳng vào thông điệp; kết bài đúng 1 câu bắt đầu bằng "Tóm lại,"). Tuyệt đối không đọc tiêu đề Phần 1/2/3/4, không dài dòng!
"""

    response = None
    last_err = None

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

    if not response or not response.text:
        print(f"[GeminiSage] Tất cả mô hình Gemini đều bận ({last_err}), kích hoạt bộ luận giải Dịch lý nội bộ từ dữ liệu Chép Cho AI...")
        clean_lines = [ln.strip() for ln in (hexagram_data or "").splitlines() if ln.strip()]
        detected_title = "QUẺ KINH DỊCH CỬU NHỊ"
        for ln in clean_lines[:15]:
            if any(k in ln.upper() for k in ["QUẺ", "TRẬN", "LÁ BÀI", "THÁP LA", "TAM TÀI"]):
                detected_title = re.sub(r"[\u4dc0-\u4dff#*✦☯•=\-\[\]【】]", " ", ln).strip()[:75]
                break
        excerpt = "\n".join(clean_lines[:35])
        fallback_interp = (
            f"PHẦN 1: TỔNG QUAN ĐỒ HÌNH TRẬN PHÁP & ĐẠI CỤC THỜI VẬN\n"
            f"Câu hỏi chiêm bốc: \"{question}\"\n"
            f"Trải bài thu thập trực tiếp từ Trang Chủ I Ching Tarot · Cửu Nhị ({detected_title}) phản ánh sự giao thoa Âm Dương đang bước vào giai đoạn chuyển mình quan trọng.\n\n"
            f"PHẦN 2: BẢN ĐỒ CHI TIẾT CÁC LÁ BÀI TRÊN TRANG CHỦ\n"
            f"{excerpt}\n\n"
            f"PHẦN 3: TƯƠNG TÁC ÂM DƯƠNG & VẬN ĐỘNG GIỮA CÁC QUẺ\n"
            f"Các hào tượng và quẻ tượng trong trải bài tương ứng chặt chẽ với trăn trở hiện tại của đương số. Nội quái giữ thế chủ động, ngoại quái mở ra cơ hội thuận lợi nếu biết nắm bắt đúng thời điểm.\n\n"
            f"PHẦN 4: ĐẠO TÙY THỜI & CHIẾN LƯỢC HÀNH ĐỘNG TOÀN DIỆN\n"
            f"✦ VIỆC NÊN LÀM NGAY: Giữ vững tâm thế chính trực, triển khai từng bước theo đúng lời khuyên của các lá bài trên trang chủ.\n"
            f"⚠ ĐIỀU ĐẠI KỴ CẦN TRÁNH: Tránh nóng vội hoặc phân tán nguồn lực khi thời cơ chưa chín muồi.\n"
            f"☯ KIM CHỈ NAM KẾT LUẬN: Thuận thời đắc vị, tâm tĩnh tắc linh, hành sự cẩn trọng ắt gặt hái cát tường."
        )
        fallback_script = (
            f"Về câu hỏi {question}, quẻ Dịch mở ra thông điệp thời vận đang chuyển mình tích cực. "
            f"Lá thứ nhất hiển lộ {detected_title}, khuyên bạn củng cố nền tảng nội lực và nắm bắt thời cơ chín muồi. "
            f"Tóm lại, hãy giữ tâm chính định, hành sự chắc chắn từng bước và tránh nóng vội để gặt hái đại cát."
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
