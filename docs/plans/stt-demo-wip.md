# STT Demo - Work in Progress

## Current State

The STT (Speech-to-Text) demo TUI is partially working. The Textual UI is responsive, but audio recording is not yet functional.

### What Works
- Textual TUI launches and is responsive
- Timer updates during "recording" (UI doesn't freeze)
- Key bindings work (Space to toggle recording, q to quit, etc.)
- Mic selector dropdown populated from sounddevice
- Playback via `afplay` subprocess works
- Waveform visualization code is ready
- Transcription via faster-whisper is implemented

### What Doesn't Work
- **Audio recording**: No audio is actually captured

### Root Cause
The `sounddevice` library (which uses PortAudio) conflicts with Textual's async event loop. We tried multiple approaches:

1. **Threading** - Froze at 00:00.1
2. **Multiprocessing with Queue/Event** - "bad value(s) in fds_to_keep" error
3. **Multiprocessing with spawn context** - Same error
4. **Subprocess with pipes** - Froze at 00:00.5
5. **Subprocess with file-based IPC** - Froze (sounddevice issue)
6. **Subprocess with ffmpeg** - UI works! But ffmpeg not installed

## Next Step

**Install ffmpeg and test:**

```bash
brew install ffmpeg
make stt-demo
```

The current implementation uses ffmpeg for recording (via `record_worker.py`), which should work because:
- ffmpeg is a completely separate binary process
- No Python library conflicts with Textual
- Already proven to work in this codebase (`make listen` uses ffmpeg)

## Files

| File | Purpose |
|------|---------|
| `speech/stt_demo.py` | Main Textual TUI app |
| `speech/record_worker.py` | Subprocess that runs ffmpeg to record audio |
| `speech/common.py` | Shared utilities (created but not yet used) |

## Architecture

```
┌─────────────────────────────────────────┐
│  stt_demo.py (Textual App)              │
│  - Main event loop                       │
│  - UI rendering                          │
│  - Polls temp file for audio data        │
└─────────────┬───────────────────────────┘
              │ subprocess.Popen
              ▼
┌─────────────────────────────────────────┐
│  record_worker.py                        │
│  - Launches ffmpeg                       │
│  - ffmpeg writes raw audio to temp file  │
└─────────────┬───────────────────────────┘
              │ subprocess
              ▼
┌─────────────────────────────────────────┐
│  ffmpeg                                  │
│  - Records from mic via avfoundation     │
│  - Outputs raw f32le audio to file       │
└─────────────────────────────────────────┘
```

## Key Code Sections

### record_worker.py - ffmpeg command
```python
cmd = [
    "ffmpeg",
    "-f", "avfoundation",
    "-i", f":{device_index}",  # macOS audio device
    "-ar", str(SAMPLE_RATE),   # 16000 Hz
    "-ac", "1",                # mono
    "-f", "f32le",             # raw 32-bit float
    "-y",
    output_file
]
```

### stt_demo.py - File polling
```python
def _poll_record_file(self) -> None:
    file_size = os.path.getsize(self._record_tmp)
    if file_size > self._record_file_pos:
        with open(self._record_tmp, 'rb') as f:
            f.seek(self._record_file_pos)
            new_data = f.read()
            # Convert raw bytes to numpy float32 array
            chunk = np.frombuffer(new_data, dtype=np.float32)
            self.audio.append(chunk)
```

## Alternative Approach (if ffmpeg doesn't work)

If ffmpeg still has issues, consider:
1. Using PyAudio instead of sounddevice
2. Recording without real-time waveform updates (record blind, show waveform after)
3. Using a WebSocket/HTTP server in a separate process for IPC

## Related Commands

```bash
make voice-demo    # TTS demo (working)
make stt-demo      # STT demo (WIP)
make listen        # Simple ffmpeg recording (working)
make stt           # Transcribe existing file (working)
```
