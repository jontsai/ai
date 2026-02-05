#!/usr/bin/env python3
"""
Simple CLI audio recorder with transcription.

Usage:
  python record_cli.py              # Record until Enter, then transcribe
  python record_cli.py --list       # List audio devices
  python record_cli.py --device 2   # Use specific device
"""
import argparse
import os
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import sounddevice as sd
import soundfile as sf

SAMPLE_RATE = 16000
CHANNELS = 1


def list_devices():
    """List available audio input devices."""
    print("Available input devices:")
    devices = sd.query_devices()
    default = sd.default.device[0]
    for i, d in enumerate(devices):
        if d['max_input_channels'] > 0:
            marker = "* " if i == default else "  "
            print(f"{marker}[{i}] {d['name']} ({d['max_input_channels']} ch)")


def record_audio(device=None):
    """Record audio until user presses Enter. Returns numpy array."""
    print(f"\n{'='*50}")
    print("Recording... Press ENTER to stop.")
    print(f"{'='*50}\n")

    audio_chunks = []
    is_recording = True

    def callback(indata, frames, time_info, status):
        if is_recording:
            audio_chunks.append(indata.copy())

    # Start recording stream
    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        device=device,
        dtype=np.float32,
        callback=callback
    )

    with stream:
        input()  # Wait for Enter
        is_recording = False

    # Combine chunks
    if audio_chunks:
        audio = np.concatenate(audio_chunks)
        duration = len(audio) / SAMPLE_RATE
        print(f"\nRecorded {duration:.1f} seconds ({len(audio)} samples)")
        return audio
    return np.array([])


def transcribe_audio(audio: np.ndarray) -> str:
    """Transcribe audio using faster-whisper."""
    if len(audio) == 0:
        return ""

    print("\nTranscribing...")

    # Save to temp file
    fd, tmp_path = tempfile.mkstemp(suffix='.wav')
    os.close(fd)

    try:
        sf.write(tmp_path, audio, SAMPLE_RATE)

        from faster_whisper import WhisperModel
        model = WhisperModel("large-v3", device="auto", compute_type="int8")
        segments, info = model.transcribe(tmp_path, vad_filter=True)

        texts = []
        for seg in segments:
            text = (seg.text or "").strip()
            if text:
                texts.append(text)
                print(f"  [{seg.start:.1f}s - {seg.end:.1f}s] {text}")

        return " ".join(texts)
    finally:
        os.unlink(tmp_path)


def play_audio(audio: np.ndarray):
    """Play back recorded audio."""
    if len(audio) == 0:
        print("Nothing to play.")
        return
    print("Playing...")
    sd.play(audio, SAMPLE_RATE)
    sd.wait()
    print("Done.")


def save_audio(audio: np.ndarray, path: str):
    """Save audio to file."""
    sf.write(path, audio, SAMPLE_RATE)
    print(f"Saved to {path}")


def main():
    parser = argparse.ArgumentParser(description="Simple audio recorder with transcription")
    parser.add_argument("--list", "-l", action="store_true", help="List audio devices")
    parser.add_argument("--device", "-d", type=int, default=None, help="Audio device index")
    parser.add_argument("--output", "-o", type=str, default=None, help="Save audio to file")
    args = parser.parse_args()

    if args.list:
        list_devices()
        return 0

    try:
        # Record
        audio = record_audio(device=args.device)

        if len(audio) == 0:
            print("No audio recorded.")
            return 1

        # Interactive menu
        while True:
            print("\n[p] Play  [t] Transcribe  [s] Save  [r] Re-record  [q] Quit")
            choice = input("> ").strip().lower()

            if choice == 'q':
                break
            elif choice == 'p':
                play_audio(audio)
            elif choice == 't':
                text = transcribe_audio(audio)
                if text:
                    print(f"\n{'='*50}")
                    print("TRANSCRIPT:")
                    print(text)
                    print(f"{'='*50}")
            elif choice == 's':
                path = args.output or "recording.wav"
                save_audio(audio, path)
            elif choice == 'r':
                audio = record_audio(device=args.device)

    except KeyboardInterrupt:
        print("\nCancelled.")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
