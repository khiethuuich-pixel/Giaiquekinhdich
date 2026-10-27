"""
Module: ai_podcast_debate.py
Chức năng: Đưa dữ liệu Kinh Dịch và Câu Hỏi của đạo hữu cho Gemini và ChatGPT cùng luận giải,
tranh biện qua lại để tạo nên 1 kịch bản Podcast đối thoại 2 nhân vật đỉnh cao:
- Nhân vật 1: ChatGPT (Đạo Trưởng Dịch Học Cổ Truyền - Giọng Nam NamMinh trầm ấm, đạo mạo)
- Nhân vật 2: Gemini (Cố Vấn Chiến Lược Hiện Đại - Giọng Nữ HoaiMy thông tuệ, thực tế)
"""

import os
import json
import re

def generate_podcast_dialogue(hexagram_data_text, user_question="", output_dir="output"):
    os.makedirs(output_dir, exist_ok=True)
    script_path = os.path.join(output_dir, "podcast_script.json")

    print("\n==================================================")
    print("🎙️ [BƯỚC 2] HỘI ĐÀM LUẬN QUẺ: GEMINI & CHATGPT")
    print("==================================================")
    if user_question:
        print(f"🎯 Trọng tâm giải đáp câu hỏi: \"{user_question}\"")

    gemini_key = os.environ.get("GEMINI_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")
    summary_snippet = hexagram_data_text[:3500]

    dialogue = []
    if gemini_key and openai_key:
        print("🔗 Đã phát hiện cả 2 API Key (Gemini & OpenAI)! Đang kết nối trực tiếp...")
        try:
            from openai import OpenAI
            from google import genai

            o_client = OpenAI(api_key=openai_key)
            g_client = genai.Client(api_key=gemini_key)

            # ChatGPT khởi thảo luận
            chatgpt_prompt = f"""Bạn là Đạo Trưởng Dịch Gia thâm trầm, uyên bác về Chu Dịch, Thoán Từ, Tượng Từ, Hào Động.
Đạo hữu vừa gửi câu hỏi trăn trở: '{user_question}'
Dựa vào dữ liệu bách khoa quẻ dịch sau:
{summary_snippet}

Hãy mở đầu buổi Podcast 'Đàm Đạo Kinh Dịch' cùng bạn dẫn Gemini. Trực tiếp nhắc đến câu hỏi của đạo hữu, giới thiệu tên quẻ, khí tượng âm dương và lời răn chính của cổ nhân (khoảng 110-140 từ)."""
            resp1 = o_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": chatgpt_prompt}]
            )
            turn1 = resp1.choices[0].message.content.strip()
            dialogue.append({"speaker": "ChatGPT", "role": "Đạo Trưởng Cổ Truyền", "voice": "vi-VN-NamMinhNeural", "text": turn1})

            # Gemini tiếp lời
            gemini_prompt = f"""Bạn là Gemini - Cố Vấn Chiến Lược và Tâm Lý Học Hiện Đại.
Đạo hữu đang hỏi: '{user_question}'
Đạo trưởng ChatGPT vừa luận: '{turn1}'.
Dựa trên quẻ dịch:
{summary_snippet}

Hãy tiếp lời ChatGPT, phân tích giải pháp cho câu hỏi này dưới góc nhìn thực tiễn đời sống, quản trị rủi ro và đặt câu hỏi đào sâu cho ChatGPT (khoảng 110-140 từ)."""
            resp2 = g_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=gemini_prompt
            )
            turn2 = resp2.text.strip()
            dialogue.append({"speaker": "Gemini", "role": "Chiến Lược Gia Hiện Đại", "voice": "vi-VN-HoaiMyNeural", "text": turn2})

            # ChatGPT giải đáp
            chatgpt_prompt2 = f"""Gemini vừa chia sẻ: '{turn2}'. Hãy đối ẩm trả lời, đi sâu vào lý dịch của hào động và cách hành sự của người quân tử đối với việc mà đạo hữu đang hỏi (khoảng 100-130 từ)."""
            resp3 = o_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": chatgpt_prompt2}]
            )
            turn3 = resp3.choices[0].message.content.strip()
            dialogue.append({"speaker": "ChatGPT", "role": "Đạo Trưởng Cổ Truyền", "voice": "vi-VN-NamMinhNeural", "text": turn3})

            # Gemini kết luận diệu kế
            gemini_prompt2 = f"""ChatGPT vừa nói: '{turn3}'. Hãy tổng kết buổi Podcast bằng 3 lời khuyên hành động cụ thể ('Diệu Kế Thực Tiễn') để trực tiếp giải tỏa trăn trở cho đạo hữu (khoảng 110-130 từ)."""
            resp4 = g_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=gemini_prompt2
            )
            turn4 = resp4.text.strip()
            dialogue.append({"speaker": "Gemini", "role": "Chiến Lược Gia Hiện Đại", "voice": "vi-VN-HoaiMyNeural", "text": turn4})

            print("✅ Đã tạo kịch bản Podcast trực tiếp từ Dual-LLM API thành công!")
        except Exception as e:
            print(f"⚠️ Quá trình gọi API gặp gián đoạn: {e}. Kích hoạt thuật toán tổng hợp Dịch lý thông minh nội suy...")
            dialogue = _synthesize_expert_dialogue(hexagram_data_text, user_question)
    else:
        print("💡 Đang kích hoạt bộ tổng hợp Dịch lý Độc quyền (Dựa trên câu hỏi & toàn thư bách khoa)...")
        dialogue = _synthesize_expert_dialogue(hexagram_data_text, user_question)

    with open(script_path, "w", encoding="utf-8") as f:
        json.dump(dialogue, f, ensure_ascii=False, indent=2)

    print(f"💾 Kịch bản Podcast hoàn chỉnh đã lưu tại: {script_path}")
    for idx, d in enumerate(dialogue, 1):
        print(f"\n[{idx}] {d['speaker']} ({d['role']}):")
        print(f"    \"{d['text'][:160]}...\"")

    return script_path, dialogue


def _synthesize_expert_dialogue(raw_text, user_question=""):
    card_matches = re.findall(r'• Lá bài hào:\s*([^\n]+)', raw_text)
    card_name = card_matches[0] if card_matches else "Quẻ Dịch Khai Mở Tâm Thức"

    hao_matches = re.findall(r'• Hào Từ \(Lời Kinh\):\s*\"([^\"]+)\"', raw_text)
    hao_tu = hao_matches[0] if hao_matches else "khi cùng ắt biến, biến ắt thông suốt."

    core_matches = re.findall(r'• Ý nghĩa cốt lõi:\s*([^\n]+)', raw_text)
    core_meaning = core_matches[0] if core_matches else "Vạn vật vận hành theo lẽ tự nhiên, thuận ứng thời thế để gặt hái cát lành."

    q_context = f"Về trăn trở của bạn: '{user_question}'" if user_question else "Trước tâm niệm của quý thính giả"

    return [
        {
            "speaker": "ChatGPT",
            "role": "Đạo Trưởng Cổ Truyền",
            "voice": "vi-VN-NamMinhNeural",
            "text": f"Kính chào quý vị thính giả và bạn dẫn Gemini. {q_context}, hôm nay trên bàn cờ Dịch lý của chúng ta hiện rõ linh tượng: {card_name}. Cổ nhân để lại lời hào kinh điển: '{hao_tu}'. Lời răn này nhắc nhở chúng ta: Khi đối diện với vận hội mới, vạn sự khởi đầu từ cái tâm ngay chính, không nên nóng vội cưỡng cầu mà chuốc lấy hiểm nguy."
        },
        {
            "speaker": "Gemini",
            "role": "Chiến Lược Gia Hiện Đại",
            "voice": "vi-VN-HoaiMyNeural",
            "text": f"Chào Đạo trưởng ChatGPT và quý thính giả. Soi chiếu vào câu hỏi thực tế của bạn, lời hào mà Đạo trưởng vừa xướng mang lại một thông điệp chiến lược rất rõ nét. {core_meaning} Trong bối cảnh nhiều biến động hiện nay, chìa khóa thành công không nằm ở việc lao theo đám đông, mà là khả năng nhận diện thời điểm thích hợp để hành động dứt khoát."
        },
        {
            "speaker": "ChatGPT",
            "role": "Đạo Trưởng Cổ Truyền",
            "voice": "vi-VN-NamMinhNeural",
            "text": "Gemini nhìn nhận rất sâu sắc. Kinh Dịch có câu: người quân tử luôn giữ vững thế đứng nội tại của mình, trước hết phải làm tròn phận sự, nắm chắc nền móng. Khi việc toan tính gặp thế cản trở, hãy xem đó là cơ hội rèn luyện bản lĩnh, tích lũy nguồn lực thay vì than vãn, ắt chuyển hung thành cát."
        },
        {
            "speaker": "Gemini",
            "role": "Chiến Lược Gia Hiện Đại",
            "voice": "vi-VN-HoaiMyNeural",
            "text": "Hoàn toàn tâm đắc với Đạo trưởng! Để trực tiếp trả lời câu hỏi của bạn, chúng tôi xin gửi gắm ba lời khuyên hành động thiết thực: Thứ nhất, giữ vững tâm thế bình tĩnh, không vội vàng quyết định khi còn hoang mang. Thứ hai, tập trung củng cố thế mạnh cốt lõi và thanh lọc các rủi ro tiềm ẩn. Và thứ ba, chủ động tạo dựng các mối quan hệ hợp tác đáng tin cậy. Chúc bạn vạn sự hanh thông và thuận buồm xuôi gió!"
        }
    ]

if __name__ == "__main__":
    test_text = "• Lá bài hào: Thuần Cấn · Cửu Tam\n• Hào Từ (Lời Kinh): \"Cấn kỳ hạn\"\n• Ý nghĩa cốt lõi: Biết dừng đúng lúc."
    generate_podcast_dialogue(test_text, "Có nên đầu tư mở rộng kinh doanh trong năm nay không?")
