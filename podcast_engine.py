import asyncio
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import edge_tts
from config import (
    AUDIO_DIR, PODCASTS_DIR, PODCAST_HOST_NAME, PODCAST_HOST_VOICE,
    PODCAST_MASTER_NAME, PODCAST_MASTER_VOICE
)
from sound_fx import ensure_singing_bowl, ensure_ambient_zen_pad

def sanitize_text_for_tts(text: str) -> str:
    """Clean text for natural speech synthesis without confusing symbols."""
    t = re.sub(r'[*_#`~]', '', text)
    t = re.sub(r'\([^)]*\)', '', t)
    t = re.sub(r'\[[^\]]*\]', '', t)
    t = t.replace('"', '').replace("'", "").replace(":", " - ")
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def get_audio_duration(audio_path: str) -> float:
    """Get precise duration of audio file in seconds via ffprobe."""
    try:
        res = subprocess.run([
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(audio_path)
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return float(res.stdout.strip())
    except Exception:
        # Fallback estimation
        if Path(audio_path).exists():
            size = Path(audio_path).stat().st_size
            return max(2.0, size / 8000.0)
        return 5.0

def format_ass_time(seconds: float) -> str:
    """Format seconds into ASS timestamp: H:MM:SS.cs"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs >= 100:
        cs = 99
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

# Voice Persona Presets
VOICE_PRESETS = {
    "duet_standard": {
        "name": "Song Ca: Hoài My (Chủ Tọa) & Dịch Sư Nam Minh (Mặc định)",
        "host_voice": "vi-VN-HoaiMyNeural",
        "host_persona": "standard",
        "host_label": "🎙 HOÀI MY (CHỦ TỌA)",
        "master_voice": "vi-VN-NamMinhNeural",
        "master_persona": "standard",
        "master_label": "☯ DỊCH SƯ NAM MINH"
    },
    "duet_elder": {
        "name": "Song Ca: Hoài My & Trưởng Lão Nam Minh (Chậm rãi, tôn nghiêm)",
        "host_voice": "vi-VN-HoaiMyNeural",
        "host_persona": "standard",
        "host_label": "🎙 HOÀI MY (CHỦ TỌA)",
        "master_voice": "vi-VN-NamMinhNeural",
        "master_persona": "elder",
        "master_label": "🧙‍♂️ TRƯỞNG LÃO NAM MINH"
    },
    "duet_zen": {
        "name": "Thiền Trà: Hoài My Thiền Định & Nam Minh Trầm Lắng",
        "host_voice": "vi-VN-HoaiMyNeural",
        "host_persona": "zen",
        "host_label": "🧘‍♀️ HOÀI MY THIỀN TRÀ",
        "master_voice": "vi-VN-NamMinhNeural",
        "master_persona": "elder",
        "master_label": "☯ DỊCH SƯ NAM MINH"
    },
    "namminh_solo": {
        "name": "Độc thoại: Dịch Sư Nam Minh (Trầm ấm, uyên bác)",
        "host_voice": "vi-VN-NamMinhNeural",
        "host_persona": "standard",
        "host_label": "☯ DỊCH SƯ NAM MINH",
        "master_voice": "vi-VN-NamMinhNeural",
        "master_persona": "standard",
        "master_label": "☯ DỊCH SƯ NAM MINH"
    },
    "namminh_elder": {
        "name": "Độc thoại: Trưởng Lão Nam Minh (Cổ kính, thâm thúy)",
        "host_voice": "vi-VN-NamMinhNeural",
        "host_persona": "elder",
        "host_label": "🧙‍♂️ TRƯỞNG LÃO NAM MINH",
        "master_voice": "vi-VN-NamMinhNeural",
        "master_persona": "elder",
        "master_label": "🧙‍♂️ TRƯỞNG LÃO NAM MINH"
    },
    "hoaimy_solo": {
        "name": "Độc thoại: Chủ Tọa Hoài My (Dịu dàng, truyền cảm)",
        "host_voice": "vi-VN-HoaiMyNeural",
        "host_persona": "standard",
        "host_label": "🌸 CHỦ TỌA HOÀI MY",
        "master_voice": "vi-VN-HoaiMyNeural",
        "master_persona": "standard",
        "master_label": "🌸 CHỦ TỌA HOÀI MY"
    },
    "hoaimy_zen": {
        "name": "Độc thoại: Hoài My Thiền Định (Thanh tịnh, chữa lành)",
        "host_voice": "vi-VN-HoaiMyNeural",
        "host_persona": "zen",
        "host_label": "🪷 HOÀI MY THIỀN SƯ",
        "master_voice": "vi-VN-HoaiMyNeural",
        "master_persona": "zen",
        "master_label": "🪷 HOÀI MY THIỀN SƯ"
    },
    "gtts_standard": {
        "name": "Độc thoại: Google AI Voice (Điềm đạm, rõ ràng)",
        "host_voice": "gtts",
        "host_persona": "standard",
        "host_label": "🤖 GOOGLE AI VOICE",
        "master_voice": "gtts",
        "master_persona": "standard",
        "master_label": "🤖 GOOGLE AI VOICE"
    }
}

def apply_audio_persona(input_mp3: Path, output_mp3: Path, persona: str) -> Path:
    """Apply FFmpeg audio DSP filter for distinct vocal personas."""
    filters = {
        "elder": "asetrate=24000*0.96,atempo=0.94,bass=g=3:f=150",
        "zen": "atempo=0.93,treble=g=1.5:f=3000",
    }
    vf = filters.get(persona)
    if not vf:
        if input_mp3 != output_mp3:
            import shutil
            shutil.copy2(input_mp3, output_mp3)
        return output_mp3

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(input_mp3),
        "-filter_complex", vf,
        "-acodec", "libmp3lame", "-ar", "24000",
        str(output_mp3)
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return output_mp3

async def _synth_single_turn(text: str, voice: str, persona: str, out_file: Path) -> Path:
    """
    Synthesize a single dialogue turn with retries, persona filter and fallback.
    CRITICAL: Never swap male/female voices on transient network errors.
    """
    import unicodedata
    clean_text = sanitize_text_for_tts(text)
    clean_text = unicodedata.normalize('NFC', clean_text).strip()
    if not clean_text:
        clean_text = "Dịch lý hanh thông, vạn sự cát tường."
    if not clean_text.endswith(('.', '!', '?')):
        clean_text += '.'

    raw_mp3 = out_file.parent / f"raw_{out_file.name}"
    success = False

    # 1. If explicit gTTS requested
    if voice == "gtts":
        try:
            from gtts import gTTS
            tts = gTTS(text=clean_text, lang='vi', slow=False)
            tts.save(str(raw_mp3))
            if raw_mp3.exists() and raw_mp3.stat().st_size > 500:
                success = True
        except Exception as eg:
            print(f"[PodcastEngine] gTTS lỗi: {eg}")

    # 2. Edge-TTS with multi-retry on requested voice
    if not success:
        for attempt in range(1, 4):
            try:
                comm = edge_tts.Communicate(
                    clean_text,
                    voice=voice,
                    rate="+0%",
                    volume="+0%",
                    pitch="+0Hz"
                )
                await comm.save(str(raw_mp3))
                if raw_mp3.exists() and raw_mp3.stat().st_size > 1000:
                    success = True
                    break
            except Exception as e:
                print(f"[PodcastEngine] Thử lần {attempt} ({voice}) thất bại: {e}")
                await asyncio.sleep(0.5 * attempt)

    # 3. Safe fallback to gTTS (same persona, never swap genders!)
    if not success:
        try:
            print(f"[PodcastEngine] Kích hoạt Google TTS dự phòng cho [{voice}]...")
            from gtts import gTTS
            tts = gTTS(text=clean_text, lang='vi', slow=False)
            tts.save(str(raw_mp3))
            if raw_mp3.exists() and raw_mp3.stat().st_size > 500:
                success = True
        except Exception as e3:
            raise RuntimeError(f"Không thể tạo âm thanh cho lượt thoại ({voice}): {e3}")

    # 4. Apply persona DSP filter (e.g. elder, zen)
    if persona and persona != "standard":
        apply_audio_persona(raw_mp3, out_file, persona)
        if raw_mp3.exists():
            try:
                raw_mp3.unlink()
            except Exception:
                pass
    else:
        if raw_mp3.exists():
            if out_file.exists():
                out_file.unlink()
            raw_mp3.rename(out_file)

    return out_file

def generate_podcast_audio(
    dialogue: list[dict],
    output_audio_path: str,
    output_timeline_path: str = None,
    output_ass_path: str = None,
    include_ambient: bool = True,
    voice_preset: str = "duet_standard",
    log_cb=None
) -> dict:
    """
    Synthesize complete multi-speaker podcast audio with customizable voice personas:
    1. Sequentially synthesizes each dialogue turn with chosen voice persona.
    2. Measures individual durations.
    3. Builds precise timestamp timeline metadata.
    4. Concatenates speech with initial Singing Bowl chime and Zen meditation background.
    5. Exports ASS subtitle file with speaker colors and custom labels.
    """
    def log(msg):
        if log_cb:
            log_cb(msg)
        print(f"[PodcastEngine] {msg}")

    out_audio = Path(output_audio_path).resolve()
    out_audio.parent.mkdir(parents=True, exist_ok=True)
    stem = out_audio.stem

    timeline_path = Path(output_timeline_path) if output_timeline_path else out_audio.parent / f"{stem}_timeline.json"
    ass_path = Path(output_ass_path) if output_ass_path else out_audio.parent / f"{stem}.ass"

    temp_dir = out_audio.parent / f"temp_{stem}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    preset_config = VOICE_PRESETS.get(voice_preset, VOICE_PRESETS["duet_standard"])
    preset_name = preset_config["name"]
    host_voice = preset_config["host_voice"]
    host_persona = preset_config["host_persona"]
    host_label = preset_config["host_label"]
    master_voice = preset_config["master_voice"]
    master_persona = preset_config["master_persona"]
    master_label = preset_config["master_label"]

    log(f"Bắt đầu tổng hợp âm thanh Podcast theo cấu hình: [{preset_name}]...")

    # Step 1: Synthesize all turns
    turn_files = []
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        for idx, turn in enumerate(dialogue):
            speaker = turn.get("speaker", "host").lower()
            text = turn.get("text", "")
            if speaker == "host":
                curr_voice = host_voice
                curr_persona = host_persona
                curr_label = host_label
            else:
                curr_voice = master_voice
                curr_persona = master_persona
                curr_label = master_label

            turn_file = temp_dir / f"turn_{idx:02d}_{speaker}.mp3"

            log(f"Đang thu âm lượt {idx+1}/{len(dialogue)}: [{curr_label}]...")
            loop.run_until_complete(_synth_single_turn(text, curr_voice, curr_persona, turn_file))
            turn_files.append((turn, turn_file, curr_label))
            time.sleep(0.08)
    finally:
        loop.close()

    # Step 2: Measure durations & construct timeline
    # We start conversation after intro singing bowl begins settling down (at ~3.2s)
    current_time = 3.2
    pause_between_turns = 0.35
    timeline = []

    for idx, (turn, turn_file, label) in enumerate(turn_files):
        dur = get_audio_duration(str(turn_file))
        speaker = turn.get("speaker", "host").lower()
        speaker_name = label
        start_time = current_time
        end_time = current_time + dur

        timeline.append({
            "turn_index": idx,
            "speaker": speaker,
            "speaker_name": speaker_name,
            "speaker_label": label,
            "start_time": round(start_time, 2),
            "end_time": round(end_time, 2),
            "duration": round(dur, 2),
            "text": turn.get("text", "")
        })

        current_time = end_time + pause_between_turns

    total_speech_duration = current_time + 1.5  # Tail buffer

    # Save timeline metadata JSON
    with open(timeline_path, "w", encoding="utf-8") as f:
        json.dump(timeline, f, ensure_ascii=False, indent=2)

    # Step 3: Build concat list of turns with short silence between them
    log("Tiến hành ghép nối âm thanh đối thoại & phối âm chuông xoay...")
    speech_concat_txt = temp_dir / "speech_concat.txt"
    silence_file = temp_dir / "silence.mp3"

    # Generate 0.35s silence
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
        "-t", str(pause_between_turns), "-q:a", "9", "-acodec", "libmp3lame",
        str(silence_file)
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    with open(speech_concat_txt, "w", encoding="utf-8") as f:
        for idx, (turn, t_file, *_) in enumerate(turn_files):
            f.write(f"file '{t_file.resolve().as_posix()}'\n")
            if idx < len(turn_files) - 1:
                f.write(f"file '{silence_file.resolve().as_posix()}'\n")

    raw_speech_mp3 = temp_dir / "raw_speech.mp3"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(speech_concat_txt),
        "-acodec", "libmp3lame", "-ar", "44100", "-ab", "192k",
        str(raw_speech_mp3)
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    # Step 4: Mix Singing Bowl (Intro) + Ambient Zen Pad (Background) + Speech
    bowl_path = ensure_singing_bowl()
    pad_path = ensure_ambient_zen_pad(total_speech_duration + 5.0)

    log("Hòa trộn âm thanh nền thiền định 432Hz & chuông xoay Tây Tạng...")

    # Audio Mixing Graph in FFmpeg:
    # 0: speech (delayed by 3.2s)
    # 1: singing bowl (plays at 0.0s, volume 0.85)
    # 2: ambient zen pad (looping background, volume 0.16)
    filter_complex = (
        "[0:a]adelay=3200|3200,volume=1.05[v_speech];"
        "[1:a]volume=0.85[v_bowl];"
        "[2:a]volume=0.15,afade=t=in:ss=0:d=2,afade=t=out:st={}:d=3[v_pad];"
        "[v_speech][v_bowl][v_pad]amix=inputs=3:duration=first:dropout_transition=2[aout]"
    ).format(max(1.0, total_speech_duration - 3.0))

    mix_cmd = [
        "ffmpeg", "-y",
        "-i", str(raw_speech_mp3),
        "-i", str(bowl_path),
        "-i", str(pad_path),
        "-filter_complex", filter_complex,
        "-map", "[aout]",
        "-t", str(total_speech_duration),
        "-acodec", "libmp3lame", "-ar", "44100", "-ab", "192k",
        str(out_audio)
    ]
    subprocess.run(mix_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    # Step 5: Generate ASS Subtitles
    _build_podcast_ass_subtitles(timeline, ass_path)

    # Clean up temp files safely
    try:
        for f in temp_dir.glob("*"):
            f.unlink()
        temp_dir.rmdir()
    except Exception:
        pass

    log(f"Xuất bản Podcast thành công! Thời lượng: {total_speech_duration:.1f}s, File: {out_audio.name}")

    return {
        "success": True,
        "audio_path": str(out_audio),
        "timeline_path": str(timeline_path),
        "ass_path": str(ass_path),
        "duration": total_speech_duration,
        "timeline": timeline
    }

def _build_podcast_ass_subtitles(timeline: list[dict], out_ass: Path):
    """Generate high-aesthetic dual-speaker ASS subtitles for Video Podcast."""
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: HostSub,Segoe UI,46,&H00FFFFFF,&H000000FF,&H00000000,&HA0000000,-1,0,0,0,100,100,0,0,1,3.5,2,2,100,100,70,1
Style: MasterSub,Segoe UI,46,&H0027E8FF,&H000000FF,&H00000000,&HA0000000,-1,0,0,0,100,100,0,0,1,3.5,2,2,100,100,70,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    dialogue_lines = []

    for item in timeline:
        speaker = item["speaker"]
        style = "HostSub" if speaker == "host" else "MasterSub"
        speaker_tag = item.get("speaker_label", "🎙 HOÀI MY" if speaker == "host" else "☯ DỊCH SƯ NAM MINH")
        tag_color = "{\\c&H00D4AF37&}" if speaker == "host" else "{\\c&H0027E8FF&}"

        text = item["text"]
        start_t = item["start_time"]
        end_t = item["end_time"]

        # Chunk longer sentences for smooth reading
        words = text.split()
        if len(words) <= 14:
            s_str = format_ass_time(start_t)
            e_str = format_ass_time(end_t)
            line = f"{tag_color}[{speaker_tag}]:{{\\r}} {text}"
            dialogue_lines.append(f"Dialogue: 0,{s_str},{e_str},{style},,0,0,0,,{line}")
        else:
            # Split into 2 chunks
            mid = len(words) // 2
            dur = end_t - start_t
            t_mid = start_t + dur * (mid / len(words))

            c1 = " ".join(words[:mid])
            c2 = " ".join(words[mid:])

            s1 = format_ass_time(start_t)
            e1 = format_ass_time(t_mid)
            dialogue_lines.append(f"Dialogue: 0,{s1},{e1},{style},,0,0,0,,{tag_color}[{speaker_tag}]:{{\\r}} {c1}")

            s2 = format_ass_time(t_mid)
            e2 = format_ass_time(end_t)
            dialogue_lines.append(f"Dialogue: 0,{s2},{e2},{style},,0,0,0,,{tag_color}[{speaker_tag}]:{{\\r}} {c2}")

    with open(out_ass, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(dialogue_lines) + "\n")

if __name__ == "__main__":
    sample = [
        {"speaker": "host", "text": "Chào mừng các bạn đến với Cửu Nhị Luận Đạo. Hôm nay chúng ta cùng đàm đạo về khởi sự kinh doanh."},
        {"speaker": "master", "text": "Chào Hoài My. Quẻ Thủy Lôi Truân dạy chúng ta rằng mầm cây vươn lên cần sự nhẫn nại và tích lũy nội lực."}
    ]
    res = generate_podcast_audio(sample, "output/audio/test_podcast_engine.mp3")
    print("Success:", res)
