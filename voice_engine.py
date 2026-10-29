import asyncio
import re
import subprocess
from pathlib import Path
import edge_tts
from config import AUDIO_DIR, DEFAULT_VOICE

def get_audio_duration(audio_path: str) -> float:
    """Get exact duration of audio file in seconds using ffprobe."""
    try:
        res = subprocess.run([
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(audio_path)
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return float(res.stdout.strip())
    except Exception:
        return 30.0

def format_ass_time(seconds: float) -> str:
    """Format seconds into ASS timestamp: H:MM:SS.cs"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs >= 100:
        cs = 99
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

def sanitize_script_for_tts(text: str) -> str:
    """Sanitize video script for clean, concise TTS narration."""
    if not text:
        return ""
    t = text
    # Strip I Ching hexagram Unicode symbols (䷀..䷿) and decorative icons
    t = re.sub(r'[\u4dc0-\u4dff✦⚠☯🃏•▪►◆◇★☆✓✕⚡🎙🎬📖📋🔮]', ' ', t)
    # Strip any accidental PHẦN 1/2/3/4 section header lines
    t = re.sub(r'(?:^|\n)\s*[#*✦☯\-\s]*PHẦN\s*[1-4][^\n.]*[.:\n]?', ' ', t, flags=re.IGNORECASE)
    t = re.sub(r'[*_#`~>]', '', t)
    # Remove short parenthetical technical notes unless they contain card ordinal info
    t = re.sub(r'\((?![^)]*(?:Lá|Vị\s*trí))[^)]{1,60}\)', ' ', t, flags=re.IGNORECASE)
    t = t.replace('[', ' ').replace(']', ' ').replace('(', ', ').replace(')', ', ')
    t = t.replace('"', '').replace("'", "").replace('—', ', ').replace('–', ', ')
    t = re.sub(r'\s*:\s*', ', ', t)
    t = re.sub(r'\s*,\s*,\s*', ', ', t)
    t = re.sub(r'\s*,\s*\.', '.', t)
    t = re.sub(r'\.{2,}', '.', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def sanitize_full_analysis_for_tts(text: str) -> str:
    """
    Sanitize full analysis text for TTS narration, removing section headers (PHẦN 1..4),
    hexagram Unicode symbols (䷀..䷿), and formatting markers so spoken audio is clean and natural.
    """
    if not text:
        return ""
    t = re.sub(r'[\u4dc0-\u4dff✦⚠☯🃏•▪►◆◇★☆✓✕⚡🎙🎬📖📋🔮]', ' ', text)
    t = re.sub(r'(?:^|\n)\s*[#*✦☯\-\s]*PHẦN\s*[1-4][^\n]*', ' ', t, flags=re.IGNORECASE)
    t = re.sub(r'[-=_]{3,}', '. ', t)
    t = re.sub(r'[*_#`~>]', '', t)
    t = t.replace('[', ', ').replace(']', ', ').replace('(', ', ').replace(')', ', ')
    t = t.replace('/', ', ').replace('—', ', ').replace('–', ', ')
    t = t.replace('"', '').replace("'", "")

    cleaned_lines = []
    for raw_line in t.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r'^[+\-•]\s*', '', line).strip()
        if not line:
            continue
        line = line.replace(':', ',')
        if not line.endswith(('.', '!', '?', '…')):
            line += '.'
        cleaned_lines.append(line)

    full_text = ' '.join(cleaned_lines)
    full_text = re.sub(r'\s*,\s*,\s*', ', ', full_text)
    full_text = re.sub(r'\s*,\s*\.', '.', full_text)
    full_text = re.sub(r'\.{2,}', '.', full_text)
    full_text = re.sub(r'^\s*,\s*', '', full_text)
    full_text = re.sub(r'\s+', ' ', full_text).strip()
    return full_text


ORDINAL_WORDS = {
    1: r"(?:nhất|một|1)",
    2: r"(?:hai|nhì|2)",
    3: r"(?:ba|3)",
    4: r"(?:tư|bốn|4)",
    5: r"(?:năm|5)",
    6: r"(?:sáu|6)",
    7: r"(?:bảy|bẩy|7)",
    8: r"(?:tám|8)",
    9: r"(?:chín|9)",
    10: r"(?:mười|10)",
    11: r"(?:mười\s*một|11)",
    12: r"(?:mười\s*hai|12)",
}

ORDINAL_LABELS_VI = {
    1: "nhất", 2: "hai", 3: "ba", 4: "tư", 5: "năm",
    6: "sáu", 7: "bảy", 8: "tám", 9: "chín", 10: "mười",
    11: "mười một", 12: "mười hai"
}


def condense_analysis_to_concise_script(raw_text: str, question: str = "", num_cards: int = 1) -> str:
    """
    Ensure any narration script is ultra-concise while preserving 100% of the core message:
    - If `raw_text` is already a concise script (no PHẦN 1..4 headers and reasonable length), cleans and returns it.
    - If `raw_text` is a multi-part essay (PHẦN 1..4), distills it into:
      1 opening sentence + 1 core message sentence per card (Lá thứ nhất..N) + 1 concluding advice sentence ("Tóm lại, ...").
    """
    if not raw_text or not raw_text.strip():
        return ""
    txt = raw_text.strip()
    has_section_headers = bool(re.search(r"PHẦN\s*[1-4]", txt, flags=re.IGNORECASE))
    words = txt.split()
    max_words_allowed = 85 + max(1, num_cards) * 32

    if not has_section_headers and len(words) <= max_words_allowed:
        cleaned_direct = sanitize_script_for_tts(txt)
        if num_cards <= 1 or split_analysis_into_card_sections(cleaned_direct, num_cards).get("matched"):
            return cleaned_direct

    # Extract concise intro from PHẦN 1 or beginning
    parsed = split_analysis_into_card_sections(txt, max(1, num_cards))
    intro_raw = parsed.get("intro") or ""
    intro_raw = re.sub(r'(?:^|\n)\s*[#*✦☯\-\s]*PHẦN\s*[12][^\n]*', ' ', intro_raw, flags=re.IGNORECASE)
    intro_clean = sanitize_script_for_tts(intro_raw)
    intro_sents = [s.strip() for s in re.split(r'(?<=[.!?…])\s+', intro_clean) if len(s.strip()) > 12]
    if intro_sents:
        # Pick the most informative sentence in Intro
        intro_line = intro_sents[-1] if len(intro_sents) > 1 and "trận pháp" in intro_sents[0].lower() else intro_sents[0]
    else:
        intro_line = f"Về câu hỏi {question}, quẻ Dịch hiển lộ thông điệp rõ ràng." if question else "Quẻ Kinh Dịch hiển lộ thông điệp thời vận quan trọng."

    # Extract 1 concise sentence per card
    card_lines = []
    cards_raw_list = parsed.get("cards") if parsed.get("matched") else []
    for idx in range(max(1, num_cards)):
        ord_vi = ORDINAL_LABELS_VI.get(idx + 1, str(idx + 1))
        if idx < len(cards_raw_list) and cards_raw_list[idx].strip():
            c_clean = sanitize_script_for_tts(cards_raw_list[idx])
            c_sents = [s.strip() for s in re.split(r'(?<=[.!?…])\s+', c_clean) if len(s.strip()) > 8]
            if c_sents:
                first_s = c_sents[0]
                if not re.search(rf"^\s*Lá\s*(?:bài\s*)?(?:thứ\s*{ORDINAL_WORDS.get(idx+1, str(idx+1))}|số\s*{idx+1}|{idx+1})\b", first_s, flags=re.IGNORECASE):
                    first_s = f"Lá thứ {ord_vi}, {first_s}"
                # Also grab the direct application / advice sentence if first sentence was only the card title
                if len(first_s.split()) < 14 and len(c_sents) > 1:
                    best_detail = next((s for s in c_sents[1:] if any(k in s.lower() for k in ["soi chiếu", "khuyên", "báo hiệu", "cho thấy", "nên", "cần"])), c_sents[-1])
                    first_s = f"{first_s.rstrip('.')} {best_detail}"
                card_lines.append(first_s)
            else:
                card_lines.append(f"Lá thứ {ord_vi} khuyên bạn giữ vững nội lực và thuận theo thời thế.")
        else:
            card_lines.append(f"Lá thứ {ord_vi} báo hiệu vận trình đang chuyển mình, cần hành sự cẩn trọng.")

    # Extract 1 concise concluding sentence from Outro / KIM CHỈ NAM KẾT LUẬN
    outro_raw = parsed.get("outro") or txt
    m_kcn = re.search(r"(?:KIM\s*CHỈ\s*NAM\s*KẾT\s*LUẬN|VIỆC\s*NÊN\s*LÀM\s*NGAY)\s*[:—\-]?\s*([^\n]+)", outro_raw, flags=re.IGNORECASE)
    if m_kcn:
        outro_clean = sanitize_script_for_tts(m_kcn.group(1))
    else:
        outro_stripped = re.sub(r'(?:^|\n)\s*[#*✦☯\-\s]*PHẦN\s*[34][^\n]*', ' ', outro_raw, flags=re.IGNORECASE)
        outro_sents = [s.strip() for s in re.split(r'(?<=[.!?…])\s+', sanitize_script_for_tts(outro_stripped)) if len(s.strip()) > 12]
        outro_clean = outro_sents[-1] if outro_sents else "Hãy giữ tâm chính định, hành sự chắc chắn để đón nhận cát tường."

    if not re.match(r"^(?:Tóm\s*lại|Tổng\s*kết|Kim\s*chỉ\s*nam|Lời\s*khuyên)", outro_clean, flags=re.IGNORECASE):
        outro_clean = f"Tóm lại, {outro_clean[0].lower() + outro_clean[1:] if len(outro_clean) > 1 else outro_clean}"

    combined = " ".join([intro_line] + card_lines + [outro_clean])
    return sanitize_script_for_tts(combined)


def split_analysis_into_card_sections(raw_text: str, num_cards: int) -> dict:
    """
    Split the video script (or full interpretation) into exact sections:
    - intro_text: Opening hook before Card 1
    - card_texts: list of `num_cards` strings corresponding to Card 1 .. Card N in exact order
    - outro_text: Concluding advice after Card N
    Returns {"matched": bool, "intro": str, "cards": list[str], "outro": str}
    """
    if not raw_text or num_cards <= 0:
        return {"matched": False, "intro": "", "cards": [raw_text or ""], "outro": ""}

    # Find PHẦN 2 boundary if present so we don't accidentally match numbers inside PHẦN 1
    m_p2 = re.search(r"(?:PHẦN\s*2|PHẦN\s*HAI|BẢN\s*ĐỒ\s*CHI\s*TIẾT)", raw_text, flags=re.IGNORECASE)
    search_start = m_p2.start() if m_p2 else 0

    # Find PHẦN 3 boundary if present (marks start of outro in 4-part analysis)
    m_p3 = re.search(
        r"(?:^|\n)\s*[#*✦☯\-\s]*(?:PHẦN\s*3|PHẦN\s*BA|TƯƠNG\s*TÁC\s*ÂM\s*DƯƠNG)",
        raw_text[search_start:],
        flags=re.IGNORECASE
    )
    outro_start = (search_start + m_p3.start()) if m_p3 else len(raw_text)

    body_for_cards = raw_text[:outro_start]
    card_starts = []
    cur_pos = search_start

    for k in range(1, num_cards + 1):
        ord_pat = ORDINAL_WORDS.get(k, str(k))
        patterns = [
            rf"(?:^|\n)\s*[+\-*•✦#]*\s*(?:\[?\s*Lá\s*(?:bài\s*)?(?:thứ\s*{ord_pat}|số\s*{k}|{k})|Vị\s*trí\s*(?:thứ\s*{ord_pat}|số\s*{k}|{k})|▶\s*Vị\s*trí\s*{k}|{k}\.\s+(?:Quẻ|Hào|Thể|Dụng|Thiên|Địa|Nhân|Kim|Mộc|Thủy|Hỏa|Thổ|Quá\s*Khứ|Bản\s*Thân|Diễn\s*Biến|Lá\s*Bài|Kết\s*Quả|Môi\s*Trường|Thiếu\s*Sót|Tình\s*Huống))",
            rf"\b(?:Lá\s*(?:bài\s*)?thứ\s*{ord_pat}|Lá\s*(?:bài\s*)?số\s*{k}|Ở\s*vị\s*trí\s*(?:thứ\s*{ord_pat}|số\s*{k}|{k}))\b",
        ]
        found_idx = None
        for pat in patterns:
            m = re.search(pat, body_for_cards[cur_pos:], flags=re.IGNORECASE)
            if m:
                found_idx = cur_pos + m.start()
                while found_idx < outro_start and body_for_cards[found_idx] in "\r\n":
                    found_idx += 1
                break
        if found_idx is None:
            break
        card_starts.append(found_idx)
        cur_pos = found_idx + 12

    # Fallback matcher specifically for Tháp La Kinh Dịch if written as [Bản Quái / Quẻ Chủ] -> [Hào 1..K] -> [Biến Quái / Quẻ Biến]
    if len(card_starts) != num_cards and num_cards >= 2:
        tl_starts = []
        tl_cur = search_start
        for k in range(1, num_cards + 1):
            ord_pat = ORDINAL_WORDS.get(k, str(k))
            if k == 1:
                tl_pats = [
                    rf"(?:^|\n)\s*[+\-*•✦#\d\.]*\s*(?:【?\s*(?:1\.\s*)?(?:BẢN\s*QUÁI|QUẺ\s*CHỦ)|Lá\s*(?:bài\s*)?(?:thứ\s*{ord_pat}|1)\b)",
                    r"\b(?:Bản\s*quái|Quẻ\s*chủ)\b",
                ]
            elif k == num_cards:
                tl_pats = [
                    rf"(?:^|\n)\s*[+\-*•✦#\d\.]*\s*(?:【?\s*(?:[23]\.\s*)?(?:BIẾN\s*QUÁI|QUẺ\s*BIẾN)|Lá\s*(?:bài\s*)?(?:thứ\s*{ord_pat}|{k})\b)",
                    r"\b(?:Biến\s*quái|Quẻ\s*biến)\b",
                ]
            else:
                yao_ord = k - 1
                yao_ord_pat = ORDINAL_WORDS.get(yao_ord, str(yao_ord))
                tl_pats = [
                    rf"(?:^|\n)\s*[+\-*•✦#▶]*\s*(?:Hào\s*Động\s*(?:thứ\s*{yao_ord_pat}|số\s*{yao_ord}|{yao_ord})|Lá\s*(?:bài\s*)?(?:thứ\s*{ord_pat}|{k})|Hào\s*(?:số\s*)?[1-6]|(?:Hào\s*)?(?:Sơ|Nhị|Tam|Tứ|Ngũ|Thượng)\s*(?:Cửu|Lục)|(?:Hào\s*)?(?:Cửu|Lục)\s*(?:Sơ|Nhị|Tam|Tứ|Ngũ|Thượng))\b",
                    rf"\b(?:Hào\s*động\s*thứ\s*{yao_ord_pat}|Hào\s*(?:thứ\s*)?(?:nhất|một|hai|nhì|ba|tư|bốn|năm|sáu|[1-6])|(?:Sơ|Nhị|Tam|Tứ|Ngũ|Thượng)\s*(?:Cửu|Lục)|(?:Cửu|Lục)\s*(?:Sơ|Nhị|Tam|Tứ|Ngũ|Thượng))\b",
                ]
            f_idx = None
            for pat in tl_pats:
                m = re.search(pat, body_for_cards[tl_cur:], flags=re.IGNORECASE)
                if m:
                    f_idx = tl_cur + m.start()
                    while f_idx < outro_start and body_for_cards[f_idx] in "\r\n":
                        f_idx += 1
                    break
            if f_idx is None:
                break
            tl_starts.append(f_idx)
            tl_cur = f_idx + 12
        if len(tl_starts) == num_cards:
            card_starts = tl_starts

    if len(card_starts) == num_cards:
        # In concise scripts without PHẦN 3, detect the concluding sentence marker after the last card
        if not m_p3:
            last_card_pos = card_starts[-1]
            tail_text = raw_text[last_card_pos:]
            m_conc = re.search(
                r"(?:(?:^|\n)\s*|(?:(?<=[.!?…])\s+))(?:Tóm\s*lại|Tổng\s*kết\s*lại|Kim\s*chỉ\s*nam|Lời\s*khuyên\s*cốt\s*lõi|Thông\s*điệp\s*cốt\s*lõi|Kết\s*luận\s*lại|Đạo\s*tùy\s*thời\s*khuyên)\b",
                tail_text,
                flags=re.IGNORECASE
            )
            if m_conc and m_conc.start() > 15:
                outro_start = last_card_pos + m_conc.start()
            else:
                # If last card block has multiple sentences, separate the final sentence as outro
                sents_matches = list(re.finditer(r'(?<=[.!?…])\s+', tail_text.strip()))
                if len(sents_matches) >= 1:
                    last_split = sents_matches[-1].end()
                    if 15 < last_split < len(tail_text) - 12:
                        outro_start = last_card_pos + last_split

        intro_text = raw_text[:card_starts[0]].strip()
        card_texts = []
        for idx in range(num_cards):
            s_pos = card_starts[idx]
            e_pos = card_starts[idx + 1] if idx + 1 < num_cards else outro_start
            card_texts.append(raw_text[s_pos:e_pos].strip())
        outro_text = raw_text[outro_start:].strip()
        return {
            "matched": True,
            "intro": intro_text,
            "cards": card_texts,
            "outro": outro_text
        }

    return {"matched": False, "intro": "", "cards": [raw_text], "outro": ""}


def apply_voice_filter(input_mp3: Path, output_mp3: Path, persona: str) -> Path:
    """Apply FFmpeg audio DSP filter for voice personas."""
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

def _split_text_into_chunks(text: str, max_chars: int = 1600) -> list[str]:
    """Split long text into sentence-aligned chunks for reliable TTS synthesis."""
    if len(text) <= max_chars:
        return [text]
    sentences = re.split(r'(?<=[.!?…])\s+', text)
    chunks = []
    current = ""
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        if len(current) + len(s) + 1 <= max_chars:
            current = f"{current} {s}".strip() if current else s
        else:
            if current:
                chunks.append(current)
            if len(s) <= max_chars:
                current = s
            else:
                words = s.split()
                temp = ""
                for w in words:
                    if len(temp) + len(w) + 1 <= max_chars:
                        temp = f"{temp} {w}".strip() if temp else w
                    else:
                        if temp:
                            chunks.append(temp)
                        temp = w
                current = temp
    if current:
        chunks.append(current)
    return chunks if chunks else [text]

_VOXCPM_SPACE_CLIENT = None
_VOXCPM_CONTROLS = {
    "voxcpm-namminh": ("male", "Deep, calm, resonant Vietnamese male narrator voice, authoritative and philosophical, clear articulation"),
    "voxcpm-hoaimy": ("female", "Vietnamese female narrator, gentle, clear, warm and expressive voice, natural storytelling pace"),
    "voxcpm-elder": ("male", "Wise elderly Vietnamese I Ching master, deep resonant baritone voice, slow, solemn, authoritative tone"),
}

def _synth_voxcpm_to_mp3(chunk_text: str, vox_voice: str, out_chunk_mp3: Path) -> bool:
    """Synthesize a single text chunk to MP3 using OpenBMB VoxCPM2 (with reference audio anchoring)."""
    global _VOXCPM_SPACE_CLIENT
    out_chunk_mp3 = Path(out_chunk_mp3)
    try:
        from tts_voxcpm import SpaceClient
        if _VOXCPM_SPACE_CLIENT is None:
            _VOXCPM_SPACE_CLIENT = SpaceClient()
        gender, control = _VOXCPM_CONTROLS.get(vox_voice, _VOXCPM_CONTROLS["voxcpm-namminh"])
        base_dir = Path(__file__).resolve().parent
        ref_wav = base_dir / "assets" / f"voxcpm_ref_{gender}.wav"
        ref_path = str(ref_wav) if ref_wav.exists() and ref_wav.stat().st_size > 5000 else None
        synth_txt = chunk_text.strip()
        if not synth_txt.startswith("..."):
            synth_txt = "... " + synth_txt
        audio_bytes = _VOXCPM_SPACE_CLIENT.generate(
            text=synth_txt,
            control=control,
            ref_wav=ref_path,
            cfg=2.0,
            normalize=False,
            denoise=bool(ref_path),
        )
        if not audio_bytes or len(audio_bytes) < 800:
            return False
        tmp_in = out_chunk_mp3.with_suffix(".vox_raw.mp3")
        tmp_in.write_bytes(audio_bytes)
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(tmp_in),
            "-af", "silenceremove=start_periods=1:start_duration=0.03:start_threshold=-40dB",
            "-acodec", "libmp3lame", "-ar", "48000", "-ac", "1", "-b:a", "192k",
            str(out_chunk_mp3)
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            tmp_in.unlink()
        except Exception:
            pass
        return out_chunk_mp3.exists() and out_chunk_mp3.stat().st_size > 800
    except Exception as ve:
        print(f"[VoiceEngine] VoxCPM2 ({vox_voice}) fallback sang Edge-TTS: {ve}")
        return False

async def _synth_single_chunk(chunk_text: str, actual_voice: str, out_chunk_mp3: Path):
    """Synthesize a single text chunk to MP3 with OpenBMB VoxCPM2 primary, Edge-TTS and gTTS fallback."""
    out_chunk_mp3 = Path(out_chunk_mp3)
    success = False
    edge_fallback_voice = "vi-VN-NamMinhNeural"
    if str(actual_voice).startswith("voxcpm"):
        if "hoaimy" in actual_voice.lower() or "female" in actual_voice.lower():
            edge_fallback_voice = "vi-VN-HoaiMyNeural"
        loop = asyncio.get_running_loop()
        success = await loop.run_in_executor(None, _synth_voxcpm_to_mp3, chunk_text, actual_voice, out_chunk_mp3)
        if success:
            return
        actual_voice = edge_fallback_voice

    if actual_voice == "gtts":
        try:
            from gtts import gTTS
            tts = gTTS(text=chunk_text, lang='vi', slow=False)
            tts.save(str(out_chunk_mp3))
            if out_chunk_mp3.exists() and out_chunk_mp3.stat().st_size > 500:
                success = True
        except Exception as eg:
            print(f"[VoiceEngine] gTTS lỗi: {eg}")

    if not success:
        for attempt in range(1, 4):
            try:
                communicate = edge_tts.Communicate(
                    chunk_text,
                    voice=actual_voice,
                    rate="+0%",
                    volume="+0%",
                    pitch="+0Hz"
                )
                await communicate.save(str(out_chunk_mp3))
                if out_chunk_mp3.exists() and out_chunk_mp3.stat().st_size > 800:
                    success = True
                    break
            except Exception as e:
                print(f"[VoiceEngine] Edge-TTS lần {attempt} ({actual_voice}) thất bại: {e}")
                await asyncio.sleep(0.6 * attempt)

    if not success:
        try:
            print(f"[VoiceEngine] Kích hoạt Google TTS cứu cánh dự phòng cho [{actual_voice}]...")
            from gtts import gTTS
            tts = gTTS(text=chunk_text, lang='vi', slow=False)
            tts.save(str(out_chunk_mp3))
            if out_chunk_mp3.exists() and out_chunk_mp3.stat().st_size > 500:
                success = True
        except Exception as e3:
            raise RuntimeError(f"Tất cả các nguồn tạo giọng nói đều thất bại: {e3}")

def _resolve_persona_and_voice(voice: str):
    persona = "standard"
    actual_voice = voice or DEFAULT_VOICE
    low = actual_voice.lower()
    if low.startswith("voxcpm"):
        if "elder" in low:
            return "elder", "voxcpm-elder"
        if "hoaimy" in low or "female" in low:
            return "standard", "voxcpm-hoaimy"
        return "standard", "voxcpm-namminh"
    if "Elder" in actual_voice or actual_voice == "namminh_elder":
        persona = "elder"
        actual_voice = "voxcpm-elder"
    elif "Zen" in actual_voice or actual_voice == "hoaimy_zen":
        persona = "zen"
        actual_voice = "voxcpm-hoaimy"
    elif "HoaiMy" in actual_voice or actual_voice == "hoaimy_solo":
        actual_voice = "vi-VN-HoaiMyNeural"
    elif "NamMinh" in actual_voice or actual_voice == "namminh_solo":
        actual_voice = "vi-VN-NamMinhNeural"
    elif "gtts" in actual_voice:
        actual_voice = "gtts"
    return persona, actual_voice

async def _synthesize_text_to_mp3(text: str, voice: str, out_audio: Path, is_full_analysis: bool = False):
    """Synthesize a text string into `out_audio` MP3."""
    import unicodedata
    clean_text = sanitize_full_analysis_for_tts(text) if is_full_analysis else sanitize_script_for_tts(text)
    clean_text = unicodedata.normalize('NFC', clean_text).strip()
    if not clean_text:
        clean_text = "Quẻ Kinh Dịch hiển lộ thông điệp cát tường."
    if not clean_text.endswith(('.', '!', '?')):
        clean_text += '.'

    persona, actual_voice = _resolve_persona_and_voice(voice)
    raw_mp3 = out_audio.parent / f"raw_{out_audio.name}"
    chunks = _split_text_into_chunks(clean_text, max_chars=1600)

    if len(chunks) == 1:
        await _synth_single_chunk(chunks[0], actual_voice, raw_mp3)
    else:
        chunk_files = []
        for idx, ch in enumerate(chunks):
            c_path = out_audio.parent / f"chunk_{out_audio.stem}_{idx}.mp3"
            await _synth_single_chunk(ch, actual_voice, c_path)
            chunk_files.append(c_path)
        concat_list = out_audio.parent / f"concat_{out_audio.stem}.txt"
        with open(concat_list, "w", encoding="utf-8") as f:
            for cf in chunk_files:
                f.write(f"file '{cf.resolve().as_posix()}'\n")
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-acodec", "libmp3lame", "-ar", "24000",
            str(raw_mp3)
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for cf in chunk_files:
            try:
                cf.unlink()
            except Exception:
                pass
        try:
            concat_list.unlink()
        except Exception:
            pass

    if persona and persona != "standard":
        apply_voice_filter(raw_mp3, out_audio, persona)
        if raw_mp3.exists():
            try:
                raw_mp3.unlink()
            except Exception:
                pass
    else:
        if raw_mp3.exists():
            if out_audio.exists():
                out_audio.unlink()
            raw_mp3.rename(out_audio)
    return clean_text


def _build_dialogue_events_for_window(clean_seg_text: str, start_time: float, window_duration: float) -> list[str]:
    """Generate ASS Dialogue lines for `clean_seg_text` strictly inside `[start_time, start_time + window_duration]`."""
    raw_segments = re.split(r'(?<=[.!?…]) +', clean_seg_text.replace("\n", " ").strip())
    segments = []
    for seg in raw_segments:
        words = seg.split()
        if len(words) <= 10:
            segments.append(seg)
        else:
            chunk_size = 7
            for i in range(0, len(words), chunk_size):
                chunk = " ".join(words[i:i + chunk_size])
                segments.append(chunk)

    segments = [s.strip() for s in segments if s.strip()]
    if not segments:
        return []

    total_chars = sum(len(s) for s in segments)
    cur_t = start_time
    lines = []
    for idx, seg in enumerate(segments):
        weight = len(seg) / total_chars if total_chars > 0 else 1.0 / len(segments)
        seg_dur = window_duration * weight
        end_t = (start_time + window_duration) if idx == len(segments) - 1 else (cur_t + seg_dur)
        start_str = format_ass_time(cur_t)
        end_str = format_ass_time(end_t)
        safe_seg = seg.replace("{", "").replace("}", "")
        styled_text = f"{{\\c&H0027E8FF&}}✦ {safe_seg} ✦"
        lines.append(f"Dialogue: 0,{start_str},{end_str},MainSub,,0,0,0,,{styled_text}")
        cur_t = end_t
    return lines


def build_ass_subtitles(text: str, total_duration: float, out_ass: Path, section_windows: list[tuple[str, float, float]] = None):
    """Build high-aesthetic ASS subtitles for vertical video (1080x1920), locked to exact section windows when available."""
    ass_header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: MainSub,Segoe UI,52,&H00FFFFFF,&H000000FF,&H00000000,&H90000000,-1,0,0,0,100,100,0,0,1,3.8,2,2,70,70,250,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    dialogue_lines = []
    if section_windows:
        for seg_text, st, dur in section_windows:
            if dur > 0.05 and seg_text.strip():
                dialogue_lines.extend(_build_dialogue_events_for_window(seg_text, st, dur))
    else:
        avail = max(1.0, total_duration - 0.3)
        dialogue_lines.extend(_build_dialogue_events_for_window(text, 0.2, avail))

    with open(out_ass, "w", encoding="utf-8") as f:
        f.write(ass_header + "\n".join(dialogue_lines) + "\n")


def generate_voice_and_subtitles(
    text: str,
    output_audio_path: str,
    output_ass_path: str,
    voice: str = None,
    is_full_analysis: bool = False,
    num_cards: int = 0
) -> dict:
    """
    Generate voiceover audio and aligned ASS subtitles.
    When `num_cards > 0` and `text` contains per-card sections (Lá 1..N), synthesizes each section
    separately to measure exact millisecond audio durations `section_timings` (`t_intro`, `t_cards`, `t_outro`)
    so the video switches to Card k at the EXACT moment the voice starts reading Card k!
    """
    v = voice or DEFAULT_VOICE
    out_audio = Path(output_audio_path)
    out_ass = Path(output_ass_path)

    out_audio.parent.mkdir(parents=True, exist_ok=True)
    out_ass.parent.mkdir(parents=True, exist_ok=True)

    clean_for_sub = sanitize_full_analysis_for_tts(text) if is_full_analysis else sanitize_script_for_tts(text)
    parsed = split_analysis_into_card_sections(text, num_cards) if num_cards > 0 else {"matched": False}

    section_timings = None
    section_windows = None

    if parsed.get("matched"):
        print(f"[VoiceEngine] Đã tách chính xác {num_cards} phân đoạn Lá Bài (1 -> {num_cards}) để đồng bộ Video-Audio 100%!")
        sec_items = []
        if parsed["intro"].strip():
            sec_items.append(("intro", parsed["intro"].strip()))
        for idx, c_txt in enumerate(parsed["cards"]):
            sec_items.append((f"card_{idx+1}", c_txt.strip()))
        if parsed["outro"].strip():
            sec_items.append(("outro", parsed["outro"].strip()))

        async def _synth_all_sections():
            results = []
            for idx_s, (tag, raw_s) in enumerate(sec_items):
                if idx_s > 0:
                    await asyncio.sleep(0.22)
                s_mp3 = out_audio.parent / f"sec_{out_audio.stem}_{tag}.mp3"
                clean_s = await _synthesize_text_to_mp3(raw_s, v, s_mp3, is_full_analysis=is_full_analysis)
                results.append((tag, s_mp3, clean_s))
            return results

        synth_results = asyncio.run(_synth_all_sections())

        # Concatenate all section MP3s into out_audio and measure exact duration of each section
        concat_list = out_audio.parent / f"concat_secs_{out_audio.stem}.txt"
        t_intro = 0.0
        t_cards = []
        t_outro = 0.0
        section_windows = []
        cur_start = 0.0

        with open(concat_list, "w", encoding="utf-8") as f:
            for tag, s_mp3, clean_s in synth_results:
                f.write(f"file '{s_mp3.resolve().as_posix()}'\n")
                d = get_audio_duration(str(s_mp3))
                section_windows.append((clean_s, cur_start, d))
                cur_start += d
                if tag == "intro":
                    t_intro = d
                elif tag.startswith("card_"):
                    t_cards.append(d)
                elif tag == "outro":
                    t_outro = d

        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-acodec", "libmp3lame", "-ar", "24000",
            str(out_audio)
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        for _, s_mp3, _ in synth_results:
            try:
                s_mp3.unlink()
            except Exception:
                pass
        try:
            concat_list.unlink()
        except Exception:
            pass

        duration = get_audio_duration(str(out_audio))
        # Normalize minor concat rounding difference onto the last section
        total_measured = t_intro + sum(t_cards) + t_outro
        if total_measured > 0 and abs(duration - total_measured) > 0.05:
            diff = duration - total_measured
            if t_outro > 0:
                t_outro = max(0.5, t_outro + diff)
            elif t_cards:
                t_cards[-1] = max(0.5, t_cards[-1] + diff)

        section_timings = {
            "t_intro": t_intro,
            "t_cards": t_cards,
            "t_outro": t_outro
        }
        print(f"[VoiceEngine] Thời lượng từng phần: Intro={t_intro:.2f}s | Cards={[round(x, 2) for x in t_cards]} | Outro={t_outro:.2f}s")
    else:
        asyncio.run(_synthesize_text_to_mp3(text, v, out_audio, is_full_analysis=is_full_analysis))
        duration = get_audio_duration(str(out_audio))

    build_ass_subtitles(clean_for_sub, duration, out_ass, section_windows=section_windows)

    return {
        "audio_path": str(out_audio),
        "ass_path": str(out_ass),
        "duration": duration,
        "voice": v,
        "spoken_text": clean_for_sub,
        "section_timings": section_timings
    }

if __name__ == "__main__":
    t = "Hỏi rằng: Dự án kinh doanh sắp tới có thuận lợi không? Quẻ Hỏa Thủy Vị Tế hiển lộ. Thời vận đang chuyển động mạnh mẽ, giữ vững tâm định ắt gặt hái đại cát."
    res = generate_voice_and_subtitles(t, "output/audio/test_voice.mp3", "output/audio/test_sub.ass")
    print("Voice & Subtitles success! Duration:", res["duration"], "seconds")
