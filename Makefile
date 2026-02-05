SHELL := /bin/bash
.DEFAULT_GOAL := help

include models.mk

help:
	@echo "ai — personal Ollama workflows"
	@echo
	@echo "Core:"
	@echo "  make doctor              Verify ollama + server + disk + model presence"
	@echo "  make status              Show expected vs installed models"
	@echo "  make list                List local models"
	@echo "  make pull                Pull models (MODEL_SET=default)"
	@echo "  make smoke               Run 1-prompt smoke tests"
	@echo "  make disk                Show Ollama disk usage"
	@echo "  make rm MODEL=...        Remove a model"
	@echo "  make prune               Prune unused layers"
	@echo
	@echo "Speech (TTS/STT):"
	@echo "  make speech-doctor       Setup speech venv, models, and check deps"
	@echo "  make speech-models       Download TTS models (auto-run by speech-doctor)"
	@echo "  make listen              Record mic -> speech/buffer/in.wav"
	@echo "  make stt                 Transcribe speech/buffer/in.wav -> out.txt"
	@echo "  make tts                 Speak speech/buffer/out.txt -> out.wav"
	@echo "  make say TEXT=\"...\"      Speak text directly (VOICE=, SPEED=)"
	@echo "  make talk                listen -> stt -> tts (one command)"
	@echo "  make voice-demo          Interactive TTS voice browser"
	@echo "  make stt-demo            Interactive STT recorder (TUI)"
	@echo "  make test                Run speech tests"
	@echo
	@echo "CosyVoice (high-quality Chinese TTS):"
	@echo "  make cosyvoice-setup     Full setup (deps + model, ~2GB download)"
	@echo "  make cosyvoice-install   Install dependencies only"
	@echo "  make cosyvoice-model     Download pretrained model"
	@echo "  make cosyvoice-say       TTS with CosyVoice (TEXT=, VOICE=)"
	@echo
	@echo "Model sets: minimal | fallback | default | all"
	@echo "Voices: see speech/voices/README.md (54 voices, 9 languages)"

doctor:
	@ISSUES=0; \
	echo "==> 1) Checking ollama binary"; \
	if command -v ollama >/dev/null 2>&1; then \
	  ollama --version; \
	else \
	  echo "MISSING: ollama not found in PATH"; \
	  echo "  Install: https://ollama.com/download"; \
	  ISSUES=$$((ISSUES + 1)); \
	fi; \
	echo; \
	echo "==> 2) Checking ollama server connectivity"; \
	if command -v ollama >/dev/null 2>&1 && ollama list >/dev/null 2>&1; then \
	  echo "OK: ollama server is running"; \
	elif command -v ollama >/dev/null 2>&1; then \
	  echo "MISSING: ollama installed but server not running"; \
	  echo "  Start: ollama serve"; \
	  ISSUES=$$((ISSUES + 1)); \
	else \
	  echo "SKIPPED: ollama not installed"; \
	fi; \
	echo; \
	echo "==> 3) Disk sanity"; \
	./scripts/disk.sh 2>/dev/null || echo "SKIPPED: ollama not available"; \
	echo; \
	echo "==> 4) Expected models vs installed (MODEL_SET=$(MODEL_SET))"; \
	if command -v ollama >/dev/null 2>&1 && ollama list >/dev/null 2>&1; then \
	  $(MAKE) -s status MODEL_SET=$(MODEL_SET); \
	else \
	  echo "SKIPPED: ollama not available"; \
	fi; \
	echo; \
	if [ $$ISSUES -gt 0 ]; then \
	  echo "Doctor found $$ISSUES issue(s). Fix them and re-run."; \
	else \
	  echo "Doctor complete. All checks passed."; \
	fi

status:
	@models="$$( $(MAKE) -s _models_for_set MODEL_SET=$(MODEL_SET) )"; \
	installed="$$(ollama list 2>/dev/null | awk 'NR>1{print $$1}')"; \
	echo "Expected:"; \
	echo "$$models" | tr ' ' '\n' | sed '/^$$/d' | sed 's/^/  - /'; \
	echo; \
	echo "Installed:"; \
	echo "$$installed" | sed '/^$$/d' | sed 's/^/  - /'; \
	echo; \
	echo "Missing:"; \
	echo "$$models" | tr ' ' '\n' | sed '/^$$/d' | while read -r m; do \
	  echo "$$installed" | grep -qx "$$m" || echo "  - $$m"; \
	done

list:
	@ollama list

pull:
	@echo "==> Pulling models (MODEL_SET=$(MODEL_SET))"; \
	models="$$( $(MAKE) -s _models_for_set MODEL_SET=$(MODEL_SET) )"; \
	echo "$$models" | tr ' ' '\n' | sed '/^$$/d' | while read -r m; do \
	  echo "-> ollama pull $$m"; \
	  ollama pull "$$m"; \
	done

smoke:
	@./scripts/smoke.sh "$(MODEL_SET)"

disk:
	@./scripts/disk.sh

rm:
	@if [ -z "$(MODEL)" ]; then \
	  echo "ERROR: MODEL is required. Example: make rm MODEL=llama3.3:70b"; \
	  exit 1; \
	fi
	@ollama rm "$(MODEL)"

prune:
	@ollama prune

_models_for_set:
	@case "$(MODEL_SET)" in \
	  minimal)  echo "$(MODELS_MINIMAL)" ;; \
	  fallback) echo "$(MODELS_FALLBACK)" ;; \
	  all)      echo "$(MODELS_ALL)" ;; \
	  ""|default) echo "$(MODELS_DEFAULT)" ;; \
	  *) echo "ERROR: Unknown MODEL_SET=$(MODEL_SET). Use minimal|fallback|default|all"; exit 1 ;; \
	esac

# --- Speech (STT/TTS) -------------------------------------------------------

speech-doctor:
	@echo "==> Checking speech dependencies"
	@command -v ffmpeg >/dev/null || { echo "ERROR: ffmpeg not found (brew install ffmpeg)"; exit 1; }
	@command -v espeak-ng >/dev/null || { echo "ERROR: espeak-ng not found (brew install espeak-ng)"; exit 1; }
	@python3 -V
	@echo
	@echo "==> Creating venv (if missing) and installing speech deps"
	@cd speech && ./../scripts/speech-venv.sh install
	@echo
	@echo "==> Checking/downloading speech models"
	@$(MAKE) -s speech-models
	@echo
	@echo "==> Listing audio devices (macOS avfoundation)"
	@./scripts/record.sh devices

KOKORO_MODEL_URL := https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0
SPEECH_MODELS_DIR := speech/models

speech-models:
	@# Download Kokoro TTS models if missing
	@mkdir -p $(SPEECH_MODELS_DIR)
	@if [ ! -f $(SPEECH_MODELS_DIR)/kokoro-v1.0.onnx ]; then \
	  echo "Downloading kokoro-v1.0.onnx (~310MB)..."; \
	  curl -L -o $(SPEECH_MODELS_DIR)/kokoro-v1.0.onnx $(KOKORO_MODEL_URL)/kokoro-v1.0.onnx; \
	else \
	  echo "kokoro-v1.0.onnx: OK"; \
	fi
	@if [ ! -f $(SPEECH_MODELS_DIR)/voices-v1.0.bin ]; then \
	  echo "Downloading voices-v1.0.bin (~27MB)..."; \
	  curl -L -o $(SPEECH_MODELS_DIR)/voices-v1.0.bin $(KOKORO_MODEL_URL)/voices-v1.0.bin; \
	else \
	  echo "voices-v1.0.bin: OK"; \
	fi

listen:
	@# Record microphone to speech/in.wav (default 10s; override: DURATION=30)
	@DURATION="$(DURATION)" ./scripts/record.sh record

stt:
	@# Transcribe speech/in.wav -> speech/out.txt
	@./scripts/stt.sh

tts:
	@# Speak speech/out.txt -> speech/out.wav, then play
	@./scripts/tts.sh

say:
	@# Speak text: make say TEXT="Hello" VOICE=bf_emma SPEED=1.2
	@VOICE="$(or $(VOICE),af_heart)" SPEED="$(or $(SPEED),1.0)" ./scripts/say.sh "$(TEXT)"

talk:
	@# listen -> stt -> tts (one command)
	@./scripts/talk.sh

voice-demo:
	@# Interactive voice demo with j/k navigation
	@cd speech && ./../scripts/speech-venv.sh run demo.py

stt-demo:
	@# Interactive STT recorder with waveform display (TUI)
	@cd speech && ./../scripts/speech-venv.sh run stt_demo.py

test:
	@echo "==> Installing speech dev deps + running tests"
	@cd speech && ./../scripts/speech-venv.sh install-dev
	@cd speech && ./../scripts/speech-venv.sh cmd pytest

# --- CosyVoice (high-quality Chinese TTS) ------------------------------------

cosyvoice-setup:
	@./scripts/cosyvoice-setup.sh setup

cosyvoice-install:
	@./scripts/cosyvoice-setup.sh install

cosyvoice-model:
	@./scripts/cosyvoice-setup.sh download-model

cosyvoice-say:
	@# TTS with CosyVoice: make cosyvoice-say TEXT="你好" VOICE="中文女"
	@./scripts/cosyvoice-say.sh "$(TEXT)" "$(VOICE)"
