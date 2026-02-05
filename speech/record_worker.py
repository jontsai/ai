#!/usr/bin/env python3
"""
Audio recording worker using ffmpeg (not sounddevice).
ffmpeg is more stable with async event loops.
"""
import os
import signal
import subprocess
import sys

SAMPLE_RATE = 16000


def main():
    if len(sys.argv) < 2:
        print("Usage: record_worker.py <output_file> [device_index]", file=sys.stderr)
        sys.exit(1)

    output_file = sys.argv[1]
    device_index = sys.argv[2] if len(sys.argv) > 2 else "0"

    # Use ffmpeg to record from macOS microphone
    # -f avfoundation: macOS audio/video capture
    # -i ":N": audio device N (colon prefix means audio-only)
    # -ar: sample rate
    # -ac: channels (1 = mono)
    # -f: output format (raw 32-bit float)
    cmd = [
        "ffmpeg",
        "-f", "avfoundation",
        "-i", f":{device_index}",
        "-ar", str(SAMPLE_RATE),
        "-ac", "1",
        "-f", "f32le",  # raw 32-bit float, little-endian
        "-y",  # overwrite
        output_file
    ]

    # Start ffmpeg
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    def handle_signal(sig, frame):
        # Send 'q' to ffmpeg to quit gracefully
        try:
            proc.stdin.write(b"q")
            proc.stdin.flush()
        except:
            proc.terminate()
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    # Wait for ffmpeg to finish (it won't until signaled)
    proc.wait()


if __name__ == "__main__":
    main()
