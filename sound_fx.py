import wave
import math
import struct
from pathlib import Path
from config import ASSETS_DIR

BELL_PATH = ASSETS_DIR / "singing_bowl.wav"
AMBIENT_PAD_PATH = ASSETS_DIR / "ambient_zen_pad.wav"

def ensure_singing_bowl() -> Path:
    """Generate or verify the presence of the authentic Tibetan singing bowl sound (4.5s)."""
    if BELL_PATH.exists() and BELL_PATH.stat().st_size > 1000:
        return BELL_PATH

    sample_rate = 44100
    duration = 4.5
    freq = 432.0  # Harmonic meditative frequency

    frames = bytearray()
    num_samples = int(sample_rate * duration)
    for i in range(num_samples):
        t = float(i) / sample_rate
        env = math.exp(-1.1 * t)
        s = (
            0.55 * math.sin(2 * math.pi * freq * t) +
            0.28 * math.sin(2 * math.pi * freq * 2.02 * t) +
            0.17 * math.sin(2 * math.pi * freq * 3.01 * t)
        ) * env
        val = int(s * 32767.0 * 0.75)
        val = max(-32768, min(32767, val))
        frames.extend(struct.pack('<h', val))

    with wave.open(str(BELL_PATH), 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(frames)

    return BELL_PATH

def ensure_ambient_zen_pad(duration: float = 60.0) -> Path:
    """
    Generate a serene, looped 432Hz ambient meditation drone pad for podcast background.
    Warm sine + gentle octave beating + slow breathing LFO modulation.
    """
    pad_file = ASSETS_DIR / f"ambient_zen_{int(duration)}s.wav"
    if pad_file.exists() and pad_file.stat().st_size > 10000:
        return pad_file

    sample_rate = 22050  # 22.05 kHz is plenty for soft ambient pad and fast generation
    num_samples = int(sample_rate * duration)
    f0 = 216.0  # Sub-harmonic of 432Hz
    frames = bytearray()

    for i in range(num_samples):
        t = float(i) / sample_rate
        # Slow breathing envelope (0.1 Hz = 10s per breath)
        breath = 0.7 + 0.3 * math.sin(2 * math.pi * 0.1 * t)
        # Gentle fade-in (first 2s) and fade-out (last 2s)
        fade = min(1.0, t / 2.0) * min(1.0, (duration - t) / 2.0) if duration > 4 else 1.0

        # Layered meditative chords: root (216Hz), perfect fifth (324Hz), octave (432Hz)
        s = (
            0.45 * math.sin(2 * math.pi * f0 * t) +
            0.30 * math.sin(2 * math.pi * (f0 * 1.5) * t + 0.5) +
            0.25 * math.sin(2 * math.pi * (f0 * 2.0) * t + 1.0)
        ) * breath * fade * 0.18  # Soft master volume

        val = int(s * 32767.0)
        val = max(-32768, min(32767, val))
        frames.extend(struct.pack('<h', val))

    with wave.open(str(pad_file), 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(frames)

    return pad_file

if __name__ == "__main__":
    b = ensure_singing_bowl()
    print("Bowl:", b)
    p = ensure_ambient_zen_pad(15.0)
    print("Pad:", p)
