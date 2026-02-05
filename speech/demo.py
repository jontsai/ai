#!/usr/bin/env python3
"""
Interactive TTS voice demo.

Controls:
  j/n/Space/Enter/→ = Next voice
  k/p/Backspace/←   = Previous voice
  r                 = Replay current voice
  q/Esc             = Quit
  1-9               = Jump to voice by number

Audio auto-advances when finished. Press j/k to skip/go back.
"""
import os
import select
import signal
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

# Voice definitions: (voice_id, name, description, lang)
VOICES = [
    # American English - Female
    ("af_alloy", "Alloy", "American female", "en-us"),
    ("af_aoede", "Aoede", "American female", "en-us"),
    ("af_bella", "Bella", "American female, warm/husky, conversational", "en-us"),
    ("af_heart", "Heart", "American female (default)", "en-us"),
    ("af_jessica", "Jessica", "American female", "en-us"),
    ("af_kore", "Kore", "American female", "en-us"),
    ("af_nicole", "Nicole", "American female, ASMR style", "en-us"),
    ("af_nova", "Nova", "American female", "en-us"),
    ("af_river", "River", "American female", "en-us"),
    ("af_sarah", "Sarah", "American female", "en-us"),
    ("af_sky", "Sky", "American female", "en-us"),
    # American English - Male
    ("am_adam", "Adam", "American male", "en-us"),
    ("am_echo", "Echo", "American male", "en-us"),
    ("am_eric", "Eric", "American male", "en-us"),
    ("am_fenrir", "Fenrir", "American male", "en-us"),
    ("am_liam", "Liam", "American male", "en-us"),
    ("am_michael", "Michael", "American male", "en-us"),
    ("am_onyx", "Onyx", "American male", "en-us"),
    ("am_puck", "Puck", "American male", "en-us"),
    ("am_santa", "Santa", "American male", "en-us"),
    # British English - Female
    ("bf_alice", "Alice", "British female", "en-gb"),
    ("bf_emma", "Emma", "British female", "en-gb"),
    ("bf_isabella", "Isabella", "British female", "en-gb"),
    ("bf_lily", "Lily", "British female", "en-gb"),
    # British English - Male
    ("bm_daniel", "Daniel", "British male", "en-gb"),
    ("bm_fable", "Fable", "British male", "en-gb"),
    ("bm_george", "George", "British male", "en-gb"),
    ("bm_lewis", "Lewis", "British male", "en-gb"),
    # Japanese
    ("jf_alpha", "Alpha", "日本語の女性", "ja"),
    ("jf_gongitsune", "Gongitsune", "日本語の女性", "ja"),
    ("jf_nezumi", "Nezumi", "日本語の女性", "ja"),
    ("jf_tebukuro", "Tebukuro", "日本語の女性", "ja"),
    ("jm_kumo", "Kumo", "日本語の男性", "ja"),
    # Mandarin Chinese
    ("zf_xiaobei", "Xiaobei", "中文女声", "zh"),
    ("zf_xiaoni", "Xiaoni", "中文女声", "zh"),
    ("zf_xiaoxiao", "Xiaoxiao", "中文女声", "zh"),
    ("zf_xiaoyi", "Xiaoyi", "中文女声", "zh"),
    ("zm_yunjian", "Yunjian", "中文男声", "zh"),
    ("zm_yunxi", "Yunxi", "中文男声", "zh"),
    ("zm_yunxia", "Yunxia", "中文男声", "zh"),
    ("zm_yunyang", "Yunyang", "中文男声", "zh"),
    # Spanish
    ("ef_dora", "Dora", "una voz femenina española", "es"),
    ("em_alex", "Alex", "una voz masculina española", "es"),
    ("em_santa", "Santa", "una voz masculina española", "es"),
    # French
    ("ff_siwis", "Siwis", "une voix féminine française", "fr"),
    # Hindi
    ("hf_alpha", "Alpha", "एक हिंदी महिला", "hi"),
    ("hf_beta", "Beta", "एक हिंदी महिला", "hi"),
    ("hm_omega", "Omega", "एक हिंदी पुरुष", "hi"),
    ("hm_psi", "Psi", "एक हिंदी पुरुष", "hi"),
    # Italian
    ("if_sara", "Sara", "una voce femminile italiana", "it"),
    ("im_nicola", "Nicola", "una voce maschile italiana", "it"),
    # Brazilian Portuguese
    ("pf_dora", "Dora", "uma voz feminina brasileira", "pt-br"),
    ("pm_alex", "Alex", "uma voz masculina brasileira", "pt-br"),
    ("pm_santa", "Santa", "uma voz masculina brasileira", "pt-br"),
]

GREETINGS = {
    "en-us": "Hi! I'm {name}, {desc}. How can I help you today?",
    "en-gb": "Hello! I'm {name}, {desc}. How may I assist you today?",
    "ja": "こんにちは！私は{name}です、{desc}です。今日はどうお手伝いしましょうか？",
    "zh": "你好！我是{name}，{desc}。今天我能帮您什么？",
    "es": "¡Hola! Soy {name}, {desc}. ¿En qué puedo ayudarte hoy?",
    "fr": "Bonjour! Je suis {name}, {desc}. Comment puis-je vous aider aujourd'hui?",
    "hi": "नमस्ते! मैं {name} हूं, {desc}। आज मैं आपकी कैसे मदद कर सकती हूं?",
    "it": "Ciao! Sono {name}, {desc}. Come posso aiutarti oggi?",
    "pt-br": "Olá! Eu sou {name}, {desc}. Como posso ajudá-lo hoje?",
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
            # Handle escape sequences (arrow keys, etc.)
            if ch == '\x1b':
                # Check if more chars available
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


def clear_line():
    """Clear the current line."""
    print('\r\033[K', end='', flush=True)


def clear_screen():
    """Clear screen and move cursor to top."""
    print('\033[2J\033[H', end='', flush=True)


def display_voice_list(voices, current_idx, visible=15):
    """Display a scrolling list of voices with current highlighted."""
    total = len(voices)

    # Calculate visible window
    half = visible // 2
    start = max(0, current_idx - half)
    end = min(total, start + visible)
    if end == total:
        start = max(0, end - visible)

    clear_screen()
    print("=" * 65)
    print("  Kokoro TTS Voice Demo")
    print("=" * 65)
    print("  j/→ = Next   k/← = Prev   r = Replay   q = Quit   1-9 = Jump")
    print("-" * 65)

    for i in range(start, end):
        voice_id, name, desc, lang = voices[i]
        marker = "▶" if i == current_idx else " "
        num = f"{i+1:2}"

        # Truncate description if too long
        max_desc = 35
        if len(desc) > max_desc:
            desc = desc[:max_desc-2] + ".."

        # Highlight current voice
        if i == current_idx:
            print(f"\033[1;32m{marker} {num}. {voice_id:<15} {name:<12} {desc}\033[0m")
        else:
            print(f"{marker} {num}. {voice_id:<15} {name:<12} {desc}")

    print("-" * 65)
    print(f"  [{current_idx + 1}/{total}] Auto-advances when audio finishes")
    print("=" * 65, flush=True)


def generate_audio(voice_id: str, name: str, desc: str, lang: str) -> str:
    """Generate TTS audio and return temp file path."""
    import tts

    greeting = GREETINGS.get(lang, GREETINGS["en-us"]).format(name=name, desc=desc)
    samples, sample_rate = tts.synthesize(greeting, voice=voice_id)

    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        tmp_path = f.name
        sf.write(tmp_path, samples, sample_rate)

    return tmp_path


def play_audio(wav_path: str) -> subprocess.Popen:
    """Start playing audio, return process handle."""
    return subprocess.Popen(['afplay', wav_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    idx = 0
    total = len(VOICES)
    audio_proc = None
    tmp_path = None

    def cleanup():
        nonlocal audio_proc, tmp_path
        if audio_proc:
            audio_proc.terminate()
            audio_proc = None
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
            tmp_path = None

    try:
        while True:
            voice_id, name, desc, lang = VOICES[idx]

            # Display voice list with current highlighted
            display_voice_list(VOICES, idx)

            # Generate and play audio
            cleanup()
            stop_audio()
            tmp_path = generate_audio(voice_id, name, desc, lang)
            audio_proc = play_audio(tmp_path)

            # Wait for input or audio to finish
            while True:
                key = get_key_nonblocking(timeout=0.1)

                # Check if audio finished (auto-advance)
                if audio_proc and audio_proc.poll() is not None:
                    idx = (idx + 1) % total
                    break

                if key is None:
                    continue

                if key in ('q', '\x1b', '\x03'):  # q, Esc, Ctrl+C
                    cleanup()
                    stop_audio()
                    print("\n\nDone!")
                    return 0
                elif key in ('j', 'n', ' ', '\r', '\x1b[C'):  # j, n, Space, Enter, Right
                    stop_audio()
                    idx = (idx + 1) % total
                    break
                elif key in ('k', 'p', '\x7f', '\x1b[D'):  # k, p, Backspace, Left
                    stop_audio()
                    idx = (idx - 1) % total
                    break
                elif key == 'r':  # Replay
                    stop_audio()
                    break
                elif key.isdigit() and key != '0':
                    stop_audio()
                    page_start = (idx // 9) * 9
                    new_idx = page_start + int(key) - 1
                    if new_idx < total:
                        idx = new_idx
                    break
    finally:
        cleanup()
        stop_audio()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted!")
        sys.exit(1)
