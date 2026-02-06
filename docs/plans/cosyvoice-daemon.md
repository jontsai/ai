# CosyVoice Persistent Daemon

## Problem

CosyVoice currently loads the 2GB model on every TTS request, causing:
- ~10 second startup time per synthesis
- High memory churn
- Poor user experience in interactive demos

## Proposed Solution

Create a persistent daemon that keeps the CosyVoice model loaded in memory.

### Architecture

```
┌─────────────────┐     HTTP/Unix Socket      ┌──────────────────────┐
│   tts.py        │ ──────────────────────────▶│  cosyvoice-daemon    │
│ (speech venv)   │                            │  (cosyvoice venv)    │
└─────────────────┘                            │                      │
                                               │  - Model loaded once │
                                               │  - Handles requests  │
                                               │  - Returns audio     │
                                               └──────────────────────┘
```

### Components

1. **cosyvoice-daemon.py** - FastAPI/Flask server running in CosyVoice venv
   - Loads model on startup
   - POST `/synthesize` endpoint accepts text, returns WAV audio
   - Health check endpoint

2. **scripts/cosyvoice-daemon.sh** - Start/stop/status management
   - `start` - Launch daemon in background
   - `stop` - Graceful shutdown
   - `status` - Check if running
   - `restart` - Stop + start

3. **tts.py updates**
   - Check if daemon is running before subprocess fallback
   - HTTP client to daemon for synthesis
   - Graceful fallback to subprocess if daemon not running

### API

```
POST /synthesize
Content-Type: application/json

{
  "text": "你好世界",
  "lang": "zh"  // optional, auto-detected
}

Response: audio/wav binary
```

### Makefile Targets

```makefile
cosyvoice-daemon-start:  # Start the daemon
cosyvoice-daemon-stop:   # Stop the daemon
cosyvoice-daemon-status: # Check daemon status
```

### Memory Considerations

- Model uses ~2-3GB RAM when loaded
- Daemon should auto-shutdown after idle timeout (configurable, default 30 min)
- Consider launchd/systemd integration for production use

### Implementation Steps

1. [x] Create `scripts/cosyvoice-daemon.py` with FastAPI server
2. [x] Create `scripts/cosyvoice-daemon.sh` for process management
3. [x] Update `tts.py` to use daemon when available
4. [x] Add Makefile targets
5. [x] Add idle timeout auto-shutdown
6. [ ] Test integration with voice-demo

### Future Enhancements

- Multiple voice support via different reference audio files
- Voice cloning endpoint (upload reference audio)
- Streaming synthesis for long text
