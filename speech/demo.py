#!/usr/bin/env python3
"""
Interactive TTS voice demo.

Controls:
  j/n/Space/Enter = Next voice
  k/p/Backspace   = Previous voice
  r               = Replay current voice
  q/Esc           = Quit
  1-9             = Jump to voice by number (in current page)
"""
import os
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


def get_key():
    """Read a single keypress."""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        # Handle escape sequences (arrow keys, etc.)
        if ch == '\x1b':
            ch += sys.stdin.read(2)
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def clear_line():
    """Clear the current line."""
    print('\r\033[K', end='', flush=True)


def play_voice(voice_id: str, name: str, desc: str, lang: str):
    """Generate and play TTS for a voice."""
    import tts

    greeting = GREETINGS.get(lang, GREETINGS["en-us"]).format(name=name, desc=desc)

    # Generate audio
    samples, sample_rate = tts.synthesize(greeting, voice=voice_id)

    # Write to temp file and play
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        tmp_path = f.name
        sf.write(tmp_path, samples, sample_rate)

    try:
        os.system(f'afplay "{tmp_path}" &')
    finally:
        # Clean up after a delay (let audio start playing)
        os.system(f'(sleep 10 && rm -f "{tmp_path}") &')


def main():
    print("\033[2J\033[H", end='')  # Clear screen
    print("=" * 60)
    print("  Kokoro TTS Voice Demo")
    print("=" * 60)
    print()
    print("Controls:")
    print("  j/n/→/Space = Next    k/p/← = Previous    r = Replay")
    print("  q/Esc = Quit          1-9 = Jump to voice")
    print()
    print("-" * 60)

    idx = 0
    total = len(VOICES)

    while True:
        voice_id, name, desc, lang = VOICES[idx]

        # Display current voice
        clear_line()
        print(f"\r[{idx + 1}/{total}] {voice_id}: {name} - {desc}", flush=True)

        # Play it
        play_voice(voice_id, name, desc, lang)

        # Wait for input
        while True:
            key = get_key()

            if key in ('q', '\x1b', '\x03'):  # q, Esc, Ctrl+C
                print("\n\nDone!")
                return 0
            elif key in ('j', 'n', ' ', '\r', '\x1b[C'):  # j, n, Space, Enter, Right
                idx = (idx + 1) % total
                break
            elif key in ('k', 'p', '\x7f', '\x1b[D'):  # k, p, Backspace, Left
                idx = (idx - 1) % total
                break
            elif key == 'r':  # Replay
                break
            elif key.isdigit() and key != '0':
                # Jump to voice number (1-indexed, within current "page" of 9)
                page_start = (idx // 9) * 9
                new_idx = page_start + int(key) - 1
                if new_idx < total:
                    idx = new_idx
                break


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted!")
        sys.exit(1)
