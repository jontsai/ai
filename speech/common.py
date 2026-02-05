#!/usr/bin/env python3
"""
Common utilities shared between TTS and STT demos.
"""
import os
import subprocess
import tempfile
from typing import Optional

import numpy as np
import soundfile as sf
from textual.binding import Binding
from textual.widgets import Input


# =============================================================================
# Audio Constants
# =============================================================================

SAMPLE_RATE = 16000  # 16kHz for speech
CHANNELS = 1  # Mono


# =============================================================================
# Time Formatting
# =============================================================================

def format_time(seconds: float) -> str:
    """Format seconds as MM:SS.s"""
    mins = int(seconds // 60)
    secs = seconds % 60
    return f"{mins:02d}:{secs:04.1f}"


# =============================================================================
# Audio Playback (uses afplay to avoid sounddevice conflicts with Textual)
# =============================================================================

def stop_audio():
    """Stop any currently playing audio."""
    subprocess.run(['killall', 'afplay'], stderr=subprocess.DEVNULL)


def play_audio_file(wav_path: str) -> subprocess.Popen:
    """Start playing audio file, return process handle."""
    return subprocess.Popen(
        ['afplay', wav_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )


def play_samples(samples: np.ndarray, sample_rate: int = SAMPLE_RATE) -> tuple[subprocess.Popen, str]:
    """
    Play audio samples via afplay. Returns (process, temp_file_path).
    Caller is responsible for cleaning up temp file after playback.
    """
    fd, tmp_path = tempfile.mkstemp(suffix='.wav')
    os.close(fd)
    sf.write(tmp_path, samples, sample_rate)
    proc = play_audio_file(tmp_path)
    return proc, tmp_path


# =============================================================================
# Audio File I/O
# =============================================================================

def save_audio(samples: np.ndarray, path: str, sample_rate: int = SAMPLE_RATE) -> None:
    """Save audio samples to WAV file."""
    sf.write(path, samples, sample_rate)


def load_audio(path: str) -> tuple[np.ndarray, int]:
    """Load audio from WAV file. Returns (samples, sample_rate)."""
    samples, sr = sf.read(path, dtype=np.float32)
    return samples, sr


# =============================================================================
# Textual Widgets
# =============================================================================

class ReadlineInput(Input):
    """Input widget with readline-style keybindings (Ctrl+b/f for cursor movement)."""

    BINDINGS = [
        Binding("ctrl+b", "cursor_left", "Cursor left", show=False),
        Binding("ctrl+f", "cursor_right", "Cursor right", show=False),
        # ctrl+a and ctrl+e already work in Textual Input
    ]


# =============================================================================
# Audio Device Utilities
# =============================================================================

def get_input_devices() -> list:
    """
    Get list of available audio input devices.
    Returns list of (device_idx, name, is_default) tuples.

    NOTE: This imports sounddevice and should be called BEFORE starting
    the Textual app to avoid event loop conflicts.
    """
    import sounddevice as sd
    devices = []
    try:
        all_devices = sd.query_devices()
        default_input = sd.default.device[0]
        for i, d in enumerate(all_devices):
            if d['max_input_channels'] > 0:
                is_default = (i == default_input)
                devices.append((i, d['name'], is_default))
    except Exception:
        pass
    return devices
