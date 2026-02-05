#!/usr/bin/env python3
"""
Interactive TTS voice demo.

Controls:
  j/↓ = Next voice       k/↑ = Previous voice
  Tab = Next language    Shift+Tab = Previous language
  r = Replay             Space/Enter = Play current
  q/Esc = Quit

Audio auto-advances when finished.
"""
import os
import select
import subprocess
import sys
import tempfile
import termios
import tty
from pathlib import Path

# Add parent dir to path for imports
sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import soundfile as sf

# Voice definitions grouped by language
LANGUAGES = [
    ("American English", "en-us", [
        ("af_alloy", "Alloy", "Female"),
        ("af_aoede", "Aoede", "Female"),
        ("af_bella", "Bella", "Female, warm/husky"),
        ("af_heart", "Heart", "Female (default)"),
        ("af_jessica", "Jessica", "Female"),
        ("af_kore", "Kore", "Female"),
        ("af_nicole", "Nicole", "Female, ASMR"),
        ("af_nova", "Nova", "Female"),
        ("af_river", "River", "Female"),
        ("af_sarah", "Sarah", "Female"),
        ("af_sky", "Sky", "Female"),
        ("am_adam", "Adam", "Male"),
        ("am_echo", "Echo", "Male"),
        ("am_eric", "Eric", "Male"),
        ("am_fenrir", "Fenrir", "Male"),
        ("am_liam", "Liam", "Male"),
        ("am_michael", "Michael", "Male"),
        ("am_onyx", "Onyx", "Male"),
        ("am_puck", "Puck", "Male"),
        ("am_santa", "Santa", "Male"),
    ]),
    ("British English", "en-gb", [
        ("bf_alice", "Alice", "Female"),
        ("bf_emma", "Emma", "Female"),
        ("bf_isabella", "Isabella", "Female"),
        ("bf_lily", "Lily", "Female"),
        ("bm_daniel", "Daniel", "Male"),
        ("bm_fable", "Fable", "Male"),
        ("bm_george", "George", "Male"),
        ("bm_lewis", "Lewis", "Male"),
    ]),
    ("Japanese", "ja", [
        ("jf_alpha", "Alpha", "女性"),
        ("jf_gongitsune", "Gongitsune", "女性"),
        ("jf_nezumi", "Nezumi", "女性"),
        ("jf_tebukuro", "Tebukuro", "女性"),
        ("jm_kumo", "Kumo", "男性"),
    ]),
    ("Chinese", "zh", [
        ("zf_xiaobei", "Xiaobei", "女声"),
        ("zf_xiaoni", "Xiaoni", "女声"),
        ("zf_xiaoxiao", "Xiaoxiao", "女声"),
        ("zf_xiaoyi", "Xiaoyi", "女声"),
        ("zm_yunjian", "Yunjian", "男声"),
        ("zm_yunxi", "Yunxi", "男声"),
        ("zm_yunxia", "Yunxia", "男声"),
        ("zm_yunyang", "Yunyang", "男声"),
    ]),
    ("Spanish", "es", [
        ("ef_dora", "Dora", "Femenina"),
        ("em_alex", "Alex", "Masculina"),
        ("em_santa", "Santa", "Masculina"),
    ]),
    ("French", "fr", [
        ("ff_siwis", "Siwis", "Féminine"),
    ]),
    ("Hindi", "hi", [
        ("hf_alpha", "Alpha", "महिला"),
        ("hf_beta", "Beta", "महिला"),
        ("hm_omega", "Omega", "पुरुष"),
        ("hm_psi", "Psi", "पुरुष"),
    ]),
    ("Italian", "it", [
        ("if_sara", "Sara", "Femminile"),
        ("im_nicola", "Nicola", "Maschile"),
    ]),
    ("Portuguese", "pt-br", [
        ("pf_dora", "Dora", "Feminina"),
        ("pm_alex", "Alex", "Masculina"),
        ("pm_santa", "Santa", "Masculina"),
    ]),
]

# Greetings for each language
# TODO: kokoro-onnx currently only supports en-us/en-gb phonemization.
# To enable native language greetings, need either:
#   1. Switch to full 'kokoro' package (requires spacy, broken on Python 3.13+)
#   2. Wait for kokoro-onnx to add multi-language G2P support
#   3. Use a separate phonemizer like 'misaki' (pip install misaki[ja] misaki[zh])
# For now, non-English voices speak English text.
GREETINGS = {
    "en-us": "Hi! I'm {name}. How can I help you today?",
    "en-gb": "Hello! I'm {name}. How may I assist you today?",
    # Native greetings (uncomment when multi-language support is available):
    # "ja": "こんにちは！私は{name}です。今日はどうお手伝いしましょうか？",
    # "zh": "你好！我是{name}。今天我能帮您什么？",
    # "es": "¡Hola! Soy {name}. ¿En qué puedo ayudarte hoy?",
    # "fr": "Bonjour! Je suis {name}. Comment puis-je vous aider?",
    # "hi": "नमस्ते! मैं {name} हूं। आज मैं आपकी कैसे मदद कर सकती हूं?",
    # "it": "Ciao! Sono {name}. Come posso aiutarti oggi?",
    # "pt-br": "Olá! Eu sou {name}. Como posso ajudá-lo hoje?",
    # Fallback English greetings for non-English voices:
    "ja": "Hi! I'm {name}, a Japanese voice. How can I help you today?",
    "zh": "Hi! I'm {name}, a Chinese voice. How can I help you today?",
    "es": "Hi! I'm {name}, a Spanish voice. How can I help you today?",
    "fr": "Hi! I'm {name}, a French voice. How can I help you today?",
    "hi": "Hi! I'm {name}, a Hindi voice. How can I help you today?",
    "it": "Hi! I'm {name}, an Italian voice. How can I help you today?",
    "pt-br": "Hi! I'm {name}, a Portuguese voice. How can I help you today?",
}


def get_key_nonblocking(timeout=0.1):
    """Read a single keypress with timeout. Returns None if no key pressed."""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        rlist, _, _ = select.select([sys.stdin], [], [], timeout)
        if rlist:
            ch = sys.stdin.read(1)
            if ch == '\x1b':
                rlist2, _, _ = select.select([sys.stdin], [], [], 0.05)
                if rlist2:
                    ch += sys.stdin.read(2)
            return ch
        return None
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def stop_audio():
    """Stop any currently playing audio."""
    subprocess.run(['killall', 'afplay'], stderr=subprocess.DEVNULL)


def generate_audio(voice_id: str, name: str, lang: str) -> str:
    """Generate TTS audio and return temp file path."""
    import tts

    greeting = GREETINGS.get(lang, GREETINGS["en-us"]).format(name=name)
    # kokoro-onnx only supports en-us/en-gb phonemization
    tts_lang = "en-gb" if lang == "en-gb" else "en-us"
    samples, sample_rate = tts.synthesize(greeting, voice=voice_id, lang=tts_lang)

    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        tmp_path = f.name
        sf.write(tmp_path, samples, sample_rate)

    return tmp_path


def play_audio(wav_path: str) -> subprocess.Popen:
    """Start playing audio, return process handle."""
    return subprocess.Popen(['afplay', wav_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def display(languages, lang_idx, voice_idx, played, paused=False):
    """Display the voice browser UI."""
    print('\033[2J\033[H', end='')  # Clear screen

    # Header
    print("╔" + "═" * 63 + "╗")
    title = "  Kokoro TTS Voice Demo"
    if paused:
        title += "  \033[1;33m[PAUSED]\033[0m"
    print("║" + title.center(72) + "║")
    print("╠" + "═" * 63 + "╣")

    # Language tabs
    tabs = []
    for i, (lang_name, _, voices) in enumerate(languages):
        if i == lang_idx:
            tabs.append(f"\033[1;32m[{lang_name}]\033[0m")
        else:
            tabs.append(f" {lang_name} ")

    tab_line = " ".join(tabs)
    # Truncate if too long
    if len(tab_line) > 100:
        tab_line = "  ".join([f"{'>' if i == lang_idx else ' '}{l[0][:3]}" for i, l in enumerate(languages)])

    print("║ " + "Tab/Shift+Tab to switch languages".ljust(62) + "║")
    print("╟" + "─" * 63 + "╢")

    # Current language info
    lang_name, lang_code, voices = languages[lang_idx]
    print(f"║ \033[1m{lang_name}\033[0m ({len(voices)} voices)".ljust(72) + "║")
    print("╟" + "─" * 63 + "╢")

    # Voice list
    for i, (vid, name, desc) in enumerate(voices):
        key = (lang_idx, i)
        if i == voice_idx:
            marker = "\033[1;32m▶\033[0m"
            line = f"\033[1;32m{vid:<15} {name:<12} {desc}\033[0m"
        elif key in played:
            marker = "✓"
            line = f"\033[2m{vid:<15} {name:<12} {desc}\033[0m"
        else:
            marker = " "
            line = f"{vid:<15} {name:<12} {desc}"

        print(f"║ {marker} {line}".ljust(72) + "║")

    # Pad to fill space
    for _ in range(max(0, 12 - len(voices))):
        print("║" + " " * 63 + "║")

    # Footer
    print("╟" + "─" * 63 + "╢")
    if paused:
        print("║  \033[33mSpace resume\033[0m  j/k Nav  J/K or Tab Lang  r Play  q Quit".ljust(73) + "║")
    else:
        print("║  Space pause  j/k Nav  J/K or Tab Lang  r Play  q Quit".ljust(64) + "║")
    print("╚" + "═" * 63 + "╝")
    sys.stdout.flush()


def main():
    lang_idx = 0
    voice_idx = 0
    played = set()  # Track played voices as (lang_idx, voice_idx)
    audio_proc = None
    tmp_path = None
    pending_play = False  # Flag to play after navigation settles
    idle_count = 0  # Count idle cycles to detect settling
    paused = False  # Pause auto-advance

    def cleanup():
        nonlocal audio_proc, tmp_path
        if audio_proc:
            audio_proc.terminate()
            audio_proc = None
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
            tmp_path = None

    def play_current():
        nonlocal audio_proc, tmp_path, pending_play
        cleanup()
        stop_audio()
        pending_play = False

        _, lang_code, voices = LANGUAGES[lang_idx]
        voice_id, name, _ = voices[voice_idx]

        played.add((lang_idx, voice_idx))
        display(LANGUAGES, lang_idx, voice_idx, played, paused)

        tmp_path = generate_audio(voice_id, name, lang_code)
        audio_proc = play_audio(tmp_path)

    def navigate(new_lang_idx, new_voice_idx):
        nonlocal lang_idx, voice_idx, pending_play, idle_count
        stop_audio()
        cleanup()
        lang_idx = new_lang_idx
        voice_idx = new_voice_idx
        pending_play = not paused  # Only auto-play if not paused
        idle_count = 0
        display(LANGUAGES, lang_idx, voice_idx, played, paused)

    try:
        display(LANGUAGES, lang_idx, voice_idx, played, paused)
        play_current()

        while True:
            key = get_key_nonblocking(timeout=0.05)  # Faster polling for responsive navigation

            # Check if audio finished (auto-advance if not paused)
            if audio_proc and audio_proc.poll() is not None:
                if not paused:
                    _, _, voices = LANGUAGES[lang_idx]
                    navigate(lang_idx, (voice_idx + 1) % len(voices))
                    pending_play = True
                    idle_count = 3  # Play immediately after audio ends
                else:
                    audio_proc = None  # Clear finished process

            # If pending play and idle for a bit, start playing
            if pending_play and not paused:
                idle_count += 1
                if idle_count > 3:  # ~150ms of no input
                    play_current()

            if key is None:
                continue

            idle_count = 0  # Reset on any key
            _, _, voices = LANGUAGES[lang_idx]

            if key in ('q', '\x03'):  # q, Ctrl+C
                cleanup()
                stop_audio()
                print("\033[2J\033[H", end='')  # Clear screen
                print("Done!")
                return 0

            elif key == '\x1b':  # Plain Escape
                pass

            elif key == '\x1b[A' or key == 'k':  # Up, k
                navigate(lang_idx, (voice_idx - 1) % len(voices))

            elif key == '\x1b[B' or key == 'j':  # Down, j
                navigate(lang_idx, (voice_idx + 1) % len(voices))

            elif key == '\x1b[Z' or key == 'K':  # Shift+Tab or K
                new_lang = (lang_idx - 1) % len(LANGUAGES)
                navigate(new_lang, 0)

            elif key == '\t' or key == 'J':  # Tab or J
                new_lang = (lang_idx + 1) % len(LANGUAGES)
                navigate(new_lang, 0)

            elif key == ' ':  # Space - toggle pause
                paused = not paused
                if paused:
                    stop_audio()
                display(LANGUAGES, lang_idx, voice_idx, played, paused)

            elif key == 'r' or key == '\r':  # r or Enter - play current
                play_current()

    except KeyboardInterrupt:
        pass
    finally:
        cleanup()
        stop_audio()
        print("\033[2J\033[H", end='')


if __name__ == "__main__":
    sys.exit(main() or 0)
