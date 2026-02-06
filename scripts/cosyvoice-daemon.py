#!/usr/bin/env python3
"""
CosyVoice TTS Daemon - keeps model loaded for fast synthesis.

Automatically shuts down after IDLE_TIMEOUT_MINUTES of inactivity.
"""
import asyncio
import io
import os
import signal
import sys
import threading
import time
from contextlib import asynccontextmanager

# Add CosyVoice paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
COSYVOICE_DIR = os.path.join(SCRIPT_DIR, "..", "speech", "cosyvoice")
sys.path.insert(0, COSYVOICE_DIR)  # Add CosyVoice root for cosyvoice module
sys.path.insert(0, os.path.join(COSYVOICE_DIR, "third_party", "Matcha-TTS"))
os.chdir(COSYVOICE_DIR)

from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

# Configuration
IDLE_TIMEOUT_MINUTES = int(os.environ.get("COSYVOICE_IDLE_TIMEOUT", "30"))
PORT = int(os.environ.get("COSYVOICE_PORT", "8765"))
HOST = os.environ.get("COSYVOICE_HOST", "127.0.0.1")

# Global state
model = None
last_request_time = time.time()
shutdown_event = threading.Event()


class SynthesizeRequest(BaseModel):
    text: str
    lang: str = "zh"  # zh, en, ja, ko


def load_model():
    """Load CosyVoice model."""
    global model
    print("Loading CosyVoice model...", flush=True)
    from cosyvoice.cli.cosyvoice import AutoModel
    model = AutoModel(model_dir="pretrained_models/CosyVoice2-0.5B")
    print("Model loaded!", flush=True)


def idle_watchdog():
    """Shutdown server after idle timeout."""
    global last_request_time
    while not shutdown_event.is_set():
        idle_seconds = time.time() - last_request_time
        idle_minutes = idle_seconds / 60
        if idle_minutes >= IDLE_TIMEOUT_MINUTES:
            print(f"Idle for {idle_minutes:.1f} minutes, shutting down...", flush=True)
            os.kill(os.getpid(), signal.SIGTERM)
            break
        # Check every 30 seconds
        shutdown_event.wait(30)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup: load model and start watchdog
    load_model()
    watchdog_thread = threading.Thread(target=idle_watchdog, daemon=True)
    watchdog_thread.start()
    yield
    # Shutdown
    shutdown_event.set()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health():
    """Health check endpoint."""
    global last_request_time
    idle_seconds = time.time() - last_request_time
    return {
        "status": "ok",
        "model_loaded": model is not None,
        "idle_seconds": int(idle_seconds),
        "idle_timeout_minutes": IDLE_TIMEOUT_MINUTES,
    }


@app.post("/synthesize")
async def synthesize(request: SynthesizeRequest):
    """Synthesize speech from text."""
    global last_request_time
    last_request_time = time.time()

    if model is None:
        return JSONResponse({"error": "Model not loaded"}, status_code=503)

    try:
        import torchaudio

        # Add language tag
        lang_tags = {"zh": "<|zh|>", "en": "<|en|>", "ja": "<|ja|>", "ko": "<|ko|>"}
        tagged_text = lang_tags.get(request.lang, "<|zh|>") + request.text

        # Generate audio
        audio_data = None
        for _, result in enumerate(
            model.inference_cross_lingual(tagged_text, "./asset/zero_shot_prompt.wav")
        ):
            audio_data = result["tts_speech"]
            break

        if audio_data is None:
            return JSONResponse({"error": "No audio generated"}, status_code=500)

        # Convert to WAV bytes
        buffer = io.BytesIO()
        torchaudio.save(buffer, audio_data, model.sample_rate, format="wav")
        buffer.seek(0)

        return Response(content=buffer.read(), media_type="audio/wav")

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/shutdown")
async def shutdown():
    """Gracefully shutdown the daemon."""
    os.kill(os.getpid(), signal.SIGTERM)
    return {"status": "shutting down"}


if __name__ == "__main__":
    print(f"Starting CosyVoice daemon on {HOST}:{PORT}", flush=True)
    print(f"Idle timeout: {IDLE_TIMEOUT_MINUTES} minutes", flush=True)
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
