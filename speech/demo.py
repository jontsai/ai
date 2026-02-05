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

# =============================================================================
# Constants
# =============================================================================

# ANSI color codes
GREEN = "\033[1;32m"
YELLOW = "\033[1;33m"
DIM = "\033[2m"
RESET = "\033[0m"
CLEAR_SCREEN = "\033[2J\033[H"

# Box drawing
BOX_WIDTH = 63

# Language display names (for greeting template)
LANG_NAMES = {
    "en-us": "an American",
    "en-gb": "a British",
    "ja": "a Japanese",
    "zh": "a Chinese",
    "es": "a Spanish",
    "fr": "a French",
    "hi": "a Hindi",
    "it": "an Italian",
    "pt-br": "a Brazilian Portuguese",
}

# TODO: kokoro-onnx currently only supports en-us/en-gb phonemization.
# To enable native language greetings, need either:
#   1. Switch to full 'kokoro' package (requires spacy, broken on Python 3.13+)
#   2. Wait for kokoro-onnx to add multi-language G2P support
#   3. Use a separate phonemizer like 'misaki' (pip install misaki[ja] misaki[zh])
GREETING_TEMPLATE = "Hi! I'm {name}, {lang_name} {desc}. How can I help you today?"

# Native greetings (for future use when multi-language support is available):
# NATIVE_GREETINGS = {
#     "ja": "こんにちは！私は{name}です、{desc}です。今日はどうお手伝いしましょうか？",
#     "zh": "你好！我是{name}，{desc}。今天我能帮您什么？",
# }

# Voice definitions: (lang_name, lang_code, [(voice_id, name, desc), ...])
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
        ("jf_alpha", "Alpha", "Female"),
        ("jf_gongitsune", "Gongitsune", "Female"),
        ("jf_nezumi", "Nezumi", "Female"),
        ("jf_tebukuro", "Tebukuro", "Female"),
        ("jm_kumo", "Kumo", "Male"),
    ]),
    ("Chinese", "zh", [
        ("zf_xiaobei", "Xiaobei", "Female"),
        ("zf_xiaoni", "Xiaoni", "Female"),
        ("zf_xiaoxiao", "Xiaoxiao", "Female"),
        ("zf_xiaoyi", "Xiaoyi", "Female"),
        ("zm_yunjian", "Yunjian", "Male"),
        ("zm_yunxi", "Yunxi", "Male"),
        ("zm_yunxia", "Yunxia", "Male"),
        ("zm_yunyang", "Yunyang", "Male"),
    ]),
    ("Spanish", "es", [
        ("ef_dora", "Dora", "Female"),
        ("em_alex", "Alex", "Male"),
        ("em_santa", "Santa", "Male"),
    ]),
    ("French", "fr", [
        ("ff_siwis", "Siwis", "Female"),
    ]),
    ("Hindi", "hi", [
        ("hf_alpha", "Alpha", "Female"),
        ("hf_beta", "Beta", "Female"),
        ("hm_omega", "Omega", "Male"),
        ("hm_psi", "Psi", "Male"),
    ]),
    ("Italian", "it", [
        ("if_sara", "Sara", "Female"),
        ("im_nicola", "Nicola", "Male"),
    ]),
    ("Portuguese", "pt-br", [
        ("pf_dora", "Dora", "Female"),
        ("pm_alex", "Alex", "Male"),
        ("pm_santa", "Santa", "Male"),
    ]),
]

# Key bindings: keys -> action name
KEY_BINDINGS = {
    # Quit
    'q': 'quit',
    '\x03': 'quit',  # Ctrl+C
    # Voice navigation
    'j': 'next_voice',
    '\x1b[B': 'next_voice',  # Down arrow
    'k': 'prev_voice',
    '\x1b[A': 'prev_voice',  # Up arrow
    # Language navigation
    'J': 'next_lang',
    '\t': 'next_lang',  # Tab
    'K': 'prev_lang',
    '\x1b[Z': 'prev_lang',  # Shift+Tab
    # Playback
    ' ': 'toggle_pause',
    'r': 'play',
    '\r': 'play',  # Enter
}


# =============================================================================
# Helper Functions
# =============================================================================

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


def play_audio(wav_path: str) -> subprocess.Popen:
    """Start playing audio, return process handle."""
    return subprocess.Popen(['afplay', wav_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def generate_audio(voice_id: str, name: str, desc: str, lang_code: str) -> str:
    """Generate TTS audio and return temp file path."""
    import tts

    lang_name = LANG_NAMES.get(lang_code, "a")
    greeting = GREETING_TEMPLATE.format(name=name, lang_name=lang_name, desc=desc)

    # kokoro-onnx only supports en-us/en-gb phonemization
    tts_lang = "en-gb" if lang_code == "en-gb" else "en-us"
    samples, sample_rate = tts.synthesize(greeting, voice=voice_id, lang=tts_lang)

    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        sf.write(f.name, samples, sample_rate)
        return f.name


def box_line(content="", style="middle"):
    """Create a box line with proper padding."""
    styles = {
        "top": ("╔", "═", "╗"),
        "middle": ("║", " ", "║"),
        "sep": ("╟", "─", "╢"),
        "div": ("╠", "═", "╣"),
        "bottom": ("╚", "═", "╝"),
    }
    left, fill, right = styles[style]
    if style in ("top", "bottom", "sep", "div"):
        return left + fill * BOX_WIDTH + right
    # For content lines, handle ANSI codes in length calculation
    visible_len = len(content.replace(GREEN, "").replace(YELLOW, "").replace(DIM, "").replace(RESET, ""))
    padding = BOX_WIDTH - visible_len - 1
    return f"{left} {content}{' ' * max(0, padding)}{right}"


def display(languages, lang_idx, voice_idx, played, paused=False):
    """Display the voice browser UI."""
    print(CLEAR_SCREEN, end='')

    # Header
    print(box_line(style="top"))
    title = "Kokoro TTS Voice Demo"
    if paused:
        title += f"  {YELLOW}[PAUSED]{RESET}"
    print(box_line(title.center(BOX_WIDTH - 2 + (len(YELLOW) + len(RESET) if paused else 0))))
    print(box_line(style="div"))
    print(box_line("Tab/Shift+Tab to switch languages"))
    print(box_line(style="sep"))

    # Current language info
    lang_name, lang_code, voices = languages[lang_idx]
    print(box_line(f"\033[1m{lang_name}\033[0m ({len(voices)} voices)"))
    print(box_line(style="sep"))

    # Voice list
    for i, (vid, name, desc) in enumerate(voices):
        is_current = (i == voice_idx)
        is_played = (lang_idx, i) in played

        if is_current:
            line = f"{GREEN}▶ {vid:<15} {name:<12} {desc}{RESET}"
        elif is_played:
            line = f"✓ {DIM}{vid:<15} {name:<12} {desc}{RESET}"
        else:
            line = f"  {vid:<15} {name:<12} {desc}"

        print(box_line(line))

    # Pad to fill space
    for _ in range(max(0, 12 - len(voices))):
        print(box_line())

    # Footer
    print(box_line(style="sep"))
    if paused:
        footer = f"{YELLOW}Space resume{RESET}  j/k Nav  J/K or Tab Lang  r Play  q Quit"
    else:
        footer = "Space pause  j/k Nav  J/K or Tab Lang  r Play  q Quit"
    print(box_line(footer))
    print(box_line(style="bottom"))
    sys.stdout.flush()


# =============================================================================
# Main
# =============================================================================

class DemoState:
    """Encapsulate demo state to reduce globals."""

    def __init__(self):
        self.lang_idx = 0
        self.voice_idx = 0
        self.played = set()
        self.audio_proc = None
        self.tmp_path = None
        self.pending_play = False
        self.idle_count = 0
        self.paused = False

    def cleanup(self):
        """Clean up audio process and temp file."""
        if self.audio_proc:
            self.audio_proc.terminate()
            self.audio_proc = None
        if self.tmp_path and os.path.exists(self.tmp_path):
            os.unlink(self.tmp_path)
            self.tmp_path = None

    def get_current_voices(self):
        """Get voices list for current language."""
        return LANGUAGES[self.lang_idx][2]

    def get_current_voice(self):
        """Get current voice tuple (id, name, desc) and lang_code."""
        _, lang_code, voices = LANGUAGES[self.lang_idx]
        return voices[self.voice_idx], lang_code

    def play_current(self):
        """Generate and play audio for current voice."""
        self.cleanup()
        stop_audio()
        self.pending_play = False

        (voice_id, name, desc), lang_code = self.get_current_voice()
        self.played.add((self.lang_idx, self.voice_idx))
        display(LANGUAGES, self.lang_idx, self.voice_idx, self.played, self.paused)

        self.tmp_path = generate_audio(voice_id, name, desc, lang_code)
        self.audio_proc = play_audio(self.tmp_path)

    def navigate(self, new_lang_idx, new_voice_idx):
        """Navigate to a new voice."""
        stop_audio()
        self.cleanup()
        self.lang_idx = new_lang_idx
        self.voice_idx = new_voice_idx
        self.pending_play = not self.paused
        self.idle_count = 0
        display(LANGUAGES, self.lang_idx, self.voice_idx, self.played, self.paused)

    def handle_action(self, action):
        """Handle a named action. Returns False to quit."""
        voices = self.get_current_voices()

        if action == 'quit':
            return False

        elif action == 'next_voice':
            self.navigate(self.lang_idx, (self.voice_idx + 1) % len(voices))

        elif action == 'prev_voice':
            self.navigate(self.lang_idx, (self.voice_idx - 1) % len(voices))

        elif action == 'next_lang':
            self.navigate((self.lang_idx + 1) % len(LANGUAGES), 0)

        elif action == 'prev_lang':
            self.navigate((self.lang_idx - 1) % len(LANGUAGES), 0)

        elif action == 'toggle_pause':
            self.paused = not self.paused
            if self.paused:
                stop_audio()
            display(LANGUAGES, self.lang_idx, self.voice_idx, self.played, self.paused)

        elif action == 'play':
            self.play_current()

        return True


def main():
    state = DemoState()

    try:
        display(LANGUAGES, state.lang_idx, state.voice_idx, state.played, state.paused)
        state.play_current()

        while True:
            key = get_key_nonblocking(timeout=0.05)

            # Check if audio finished (auto-advance if not paused)
            if state.audio_proc and state.audio_proc.poll() is not None:
                if not state.paused:
                    voices = state.get_current_voices()
                    state.navigate(state.lang_idx, (state.voice_idx + 1) % len(voices))
                    state.pending_play = True
                    state.idle_count = 3
                else:
                    state.audio_proc = None

            # If pending play and idle for a bit, start playing
            if state.pending_play and not state.paused:
                state.idle_count += 1
                if state.idle_count > 3:
                    state.play_current()

            if key is None:
                continue

            state.idle_count = 0
            action = KEY_BINDINGS.get(key)

            if action and not state.handle_action(action):
                break

    except KeyboardInterrupt:
        pass
    finally:
        state.cleanup()
        stop_audio()
        print(CLEAR_SCREEN, end='')
        print("Done!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
