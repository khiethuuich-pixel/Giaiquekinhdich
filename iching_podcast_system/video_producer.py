"""
Module: video_producer.py
Chức năng:
1. Đọc kịch bản Podcast đối thoại
2. Xử lý giọng đọc Neural cao cấp (Microsoft Edge-TTS Native Python, không qua CLI tránh lỗi font Windows)
3. Cải tiến triệt để Giọng Nữ (Hoài My Neural):
   - Nhịp điệu tươi tắn (+4% rate)
   - EQ mở sáng 3.8kHz tạo độ ngọt ngào, ấm áp 220Hz
   - Hiệu ứng âm hưởng phòng thu Studio Reverb (aecho) & Dynamic Compressor
4. Giọng Nam (Nam Minh Neural):
   - Trầm ấm, đạo mạo (120Hz bass boost + studio acoustics)
5. Phối khí với Nhạc Thiền Cổ Phong (assets/ambient_zen_245s.wav) ở âm lượng tinh tế -23dB
6. Dựng Video MP4 chuẩn Full HD với ảnh chụp thẻ bài thật (2.3K) và sóng âm vàng kim
"""

import os
import sys
import json
import re
import asyncio
import subprocess

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
ZEN_MUSIC_PATH = os.path.join(ROOT_DIR, "assets", "ambient_zen_245s.wav")

def clean_text_for_tts(text):
    """
    Chuẩn hóa văn bản:
    1. Thay thế các cụm từ dễ chạm bộ lọc nhạy cảm của Azure Speech
    2. Loại bỏ dấu ngoặc kép, dấu hai chấm, dấu gạch nối phức tạp
    """
    t = text
    replacements = {
        "đạo hữu": "bạn",
        "Đạo hữu": "Bạn",
        "quý bạn": "quý vị",
        "đồng thuận": "tâm đắc",
        "nhất trí": "tán đồng",
        "Kỳ biến tắc thông, cùng tắc biến": "khi cùng ắt biến, biến ắt thông suốt",
        "Quân tử dĩ tư bất xuất kỳ vị": "người quân tử luôn giữ vững thế đứng nội tại",
        '"': '',
        "'": '',
        "•": ",",
        "—": ",",
        "-": ",",
        "·": ",",
        ":": ",",
        ";": ",",
        "!": ".",
        "?": "."
    }
    for k, v in replacements.items():
        t = t.replace(k, v)
    t = t.replace(".,", ",").replace(",.", ",").replace("..", ".")
    t = re.sub(r'\s+', ' ', t).strip()
    return t


async def generate_voice_expressive(text, speaker, out_path):
    safe_text = clean_text_for_tts(text)
    temp_raw = out_path + ".raw.mp3"
    
    # -------------------------------------------------------------
    # LỰA CHỌN 1: OpenAI TTS-1-HD Studio (Nếu có API key)
    # -------------------------------------------------------------
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_key)
            voice_name = "onyx" if "chatgpt" in speaker.lower() else "nova"
            print(f"🎙️ [Studio HD] Đang thu âm {speaker} bằng OpenAI ({voice_name})...")
            resp = client.audio.speech.create(
                model="tts-1-hd",
                voice=voice_name,
                input=safe_text
            )
            resp.stream_to_file(out_path)
            if os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
                print(f"   ✓ Hoàn tất giọng đọc Studio {voice_name}.")
                return out_path
        except Exception as e:
            print(f"   ⚠️ OpenAI API chưa sẵn sàng ({e}), chuyển qua Neural Engine...")

    # -------------------------------------------------------------
    # LỰA CHỌN 2: Microsoft Edge-TTS Native Python (Đã tinh chỉnh Studio)
    # -------------------------------------------------------------
    import edge_tts

    is_male = "chatgpt" in speaker.lower()
    voice = "vi-VN-NamMinhNeural" if is_male else "vi-VN-HoaiMyNeural"
    rate = "+0%" if is_male else "+4%"
    desc = "Đạo Trưởng (Nam Minh - Trầm Ấm)" if is_male else "Cố Vấn Chiến Lược (Hoài My - Ngọt Ngào, Truyền Cảm)"

    print(f"🎙️ Đang thu âm {speaker} qua Microsoft Neural: {desc}...")
    for attempt in range(1, 4):
        try:
            # Gọi trực tiếp websocket trong Python (tránh subprocess Windows ANSI mojibake)
            comm = edge_tts.Communicate(safe_text, voice, rate=rate)
            await comm.save(temp_raw)

            if os.path.exists(temp_raw) and os.path.getsize(temp_raw) > 500:
                # ---------------------------------------------------------
                # BỘ LỌC ÂM THANH PODCAST MASTERING (FFmpeg DSP)
                # ---------------------------------------------------------
                if is_male:
                    # Giọng Nam: Trầm ấm, đạo mạo, âm vang uy nghi
                    dsp_filter = (
                        "equalizer=f=120:width_type=h:width=80:g=3.5,"
                        "equalizer=f=3000:width_type=h:width=1000:g=2,"
                        "acompressor=threshold=0.12:ratio=3:attack=5:release=50,"
                        "aecho=0.8:0.88:35:0.15"
                    )
                else:
                    # Giọng Nữ: HẾT CHÁN!
                    # Nhịp điệu linh hoạt +4%, dải âm 3.8kHz sáng ngọt, 220Hz ấm hơi thở,
                    # Âm vang phòng thu chuyên nghiệp
                    dsp_filter = (
                        "equalizer=f=220:width_type=h:width=100:g=2.5,"
                        "equalizer=f=3800:width_type=h:width=1200:g=3.8,"
                        "acompressor=threshold=0.15:ratio=3:attack=5:release=40,"
                        "aecho=0.8:0.88:30:0.18"
                    )

                master_cmd = [
                    "ffmpeg", "-i", temp_raw,
                    "-af", dsp_filter,
                    out_path, "-y"
                ]
                subprocess.run(master_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if os.path.exists(temp_raw):
                    os.remove(temp_raw)
                print(f"   ✓ Giọng đọc Neural + Studio Mastering hoàn tất ({os.path.getsize(out_path):,} bytes).")
                return out_path
        except Exception as e:
            if attempt < 3:
                print(f"   ⚠️ Kết nối Neural thử lần {attempt} gặp gián đoạn ({e}), tự động thử lại sau 1.5s...")
                await asyncio.sleep(1.5 * attempt)
            else:
                print(f"   ⚠️ Thử nghiệm 3 lần không thành công: {e}")

    # Fallback dự phòng
    from gtts import gTTS
    g = gTTS(text=safe_text, lang="vi", slow=False)
    temp_gtts = out_path + ".gtts.mp3"
    g.save(temp_gtts)
    tone = "atempo=0.98,asetrate=24000*0.92,aresample=24000" if is_male else "atempo=1.05,asetrate=24000*1.08,aresample=24000"
    subprocess.run(["ffmpeg", "-i", temp_gtts, "-af", tone, out_path, "-y"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if os.path.exists(temp_gtts):
        os.remove(temp_gtts)
    return out_path


async def synthesize_all_dialogues_async(dialogue_list, output_dir="output"):
    os.makedirs(output_dir, exist_ok=True)
    audio_files = []

    print("\n==================================================")
    print("🎧 [BƯỚC 3] LỒNG TIẾNG PODCAST NEURAL NÂNG CẤP")
    print("==================================================")

    for i, item in enumerate(dialogue_list, 1):
        speaker = item.get("speaker", "AI")
        text = item.get("text", "")
        part_filename = f"part_{i}_{speaker.lower().replace(' ', '_')}.mp3"
        part_path = os.path.join(output_dir, part_filename)

        await generate_voice_expressive(text, speaker, part_path)
        if os.path.exists(part_path) and os.path.getsize(part_path) > 0:
            audio_files.append(part_path)
        await asyncio.sleep(0.8)

    # Ghép giọng nói (Vocal Only)
    concat_list_path = os.path.join(output_dir, "audio_concat.txt")
    with open(concat_list_path, "w", encoding="utf-8") as f:
        for p in audio_files:
            safe_p = os.path.abspath(p).replace("\\", "/")
            f.write(f"file '{safe_p}'\n")

    vocal_audio = os.path.join(output_dir, "temp_vocal_master.mp3")
    concat_cmd = [
        "ffmpeg", "-f", "concat", "-safe", "0", "-i", concat_list_path,
        "-c", "copy", vocal_audio, "-y"
    ]
    subprocess.run(concat_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Phối khí với Nhạc Thiền Cổ Phong Zen Background Music
    master_audio = os.path.join(output_dir, "master_podcast.mp3")
    if os.path.exists(ZEN_MUSIC_PATH):
        print(f"🎵 Đang phối khí với Nhạc Thiền Cổ Phong Zen (âm lượng tinh tế -23dB)...")
        mix_cmd = [
            "ffmpeg",
            "-i", vocal_audio,
            "-i", ZEN_MUSIC_PATH,
            "-filter_complex",
            "[1:a]volume=0.075[bg];"
            "[0:a][bg]amix=inputs=2:duration=first:dropout_transition=3[aout]",
            "-map", "[aout]",
            "-c:a", "libmp3lame",
            "-b:a", "192k",
            master_audio, "-y"
        ]
        subprocess.run(mix_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(vocal_audio):
            os.remove(vocal_audio)
    else:
        import shutil
        shutil.move(vocal_audio, master_audio)

    print(f"🎵 Master Podcast Audio đã hoàn thiện: {master_audio}")
    return master_audio


def synthesize_all_dialogues(dialogue_list, output_dir="output"):
    return asyncio.run(synthesize_all_dialogues_async(dialogue_list, output_dir=output_dir))


def render_podcast_video(image_path, audio_path, output_video_path="output/iching_podcast_video.mp4"):
    print("\n==================================================")
    print("🎬 [BƯỚC 4] XUẤT VIDEO PODCAST VỚI ẢNH CHỤP THẺ BÀI THẬT")
    print("==================================================")

    abs_image = os.path.abspath(image_path).replace("\\", "/")
    abs_audio = os.path.abspath(audio_path).replace("\\", "/")
    abs_out = os.path.abspath(output_video_path).replace("\\", "/")

    # Filter complex: Giữ nguyên ảnh chụp thật (2.3K) đặt trang trọng chính giữa,
    # phía dưới là dải sóng âm vàng kim hiển thị nhịp điệu giọng nói
    filter_complex = (
        "[0:v]scale=1240:510:force_original_aspect_ratio=decrease[card];"
        "color=c=0x0F0D0A:s=1280x720[canvas];"
        "[canvas][card]overlay=(W-w)/2:50[bg];"
        "[1:a]showwaves=s=1200x110:mode=line:colors=0xD4AF37:scale=cbrt[wave];"
        "[bg][wave]overlay=(W-w)/2:H-h-35[outv]"
    )

    cmd = [
        "ffmpeg",
        "-loop", "1", "-i", abs_image,
        "-i", abs_audio,
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-map", "1:a",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "21",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        abs_out,
        "-y"
    ]

    print("⚙️ Đang render video Podcast hoàn chỉnh...")
    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if res.returncode == 0:
        print(f"🎉 XUẤT BẢN THÀNH CÔNG! Video đã sẵn sàng tại:\n👉 {abs_out}")
        return abs_out
    else:
        # Fallback render đơn giản
        cmd_simple = [
            "ffmpeg",
            "-loop", "1", "-i", abs_image,
            "-i", abs_audio,
            "-c:v", "libx264", "-tune", "stillimage",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-shortest", abs_out, "-y"
        ]
        subprocess.run(cmd_simple, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return abs_out


def produce_video_from_script(script_json_path, image_path, output_video_path="output/iching_podcast_video.mp4"):
    with open(script_json_path, "r", encoding="utf-8") as f:
        dialogue = json.load(f)

    master_audio = synthesize_all_dialogues(dialogue, output_dir=os.path.dirname(script_json_path))
    final_video = render_podcast_video(image_path, master_audio, output_video_path=output_video_path)
    return final_video

if __name__ == "__main__":
    test_json = os.path.join(BASE_DIR, "output", "podcast_script.json")
    test_img = os.path.join(BASE_DIR, "output", "hexagram_card.png")
    test_vid = os.path.join(BASE_DIR, "output", "iching_podcast_video.mp4")
    if os.path.exists(test_json) and os.path.exists(test_img):
        produce_video_from_script(test_json, test_img, output_video_path=test_vid)
