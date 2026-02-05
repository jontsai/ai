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
	@echo "Model sets: minimal | fallback | default | all"

doctor:
	@echo "==> 1) Checking ollama binary"
	@command -v ollama >/dev/null || { echo "ERROR: ollama not found in PATH"; exit 1; }
	@ollama --version
	@echo
	@echo "==> 2) Checking ollama server connectivity"
	@ollama list >/dev/null || { echo "ERROR: cannot reach ollama server"; exit 1; }
	@echo
	@echo "==> 3) Disk sanity"
	@./scripts/disk.sh || true
	@echo
	@echo "==> 4) Expected models vs installed (MODEL_SET=$(MODEL_SET))"
	@$(MAKE) -s status MODEL_SET=$(MODEL_SET)
	@echo
	@echo "Doctor complete."

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
	@python3 -V
	@echo
	@echo "==> Creating venv (if missing) and installing speech deps"
	@cd speech && ./../scripts/speech-venv.sh install
	@echo
	@echo "==> Listing audio devices (macOS avfoundation)"
	@./scripts/record.sh devices

listen:
	@# Record microphone to speech/in.wav (default 10s; override: DURATION=30)
	@DURATION="$(DURATION)" ./scripts/record.sh record

stt:
	@# Transcribe speech/in.wav -> speech/out.txt
	@./scripts/stt.sh

tts:
	@# Speak speech/out.txt -> speech/out.wav, then play
	@./scripts/tts.sh

talk:
	@# listen -> stt -> tts (one command)
	@./scripts/talk.sh

test:
	@echo "==> Installing speech dev deps + running tests"
	@cd speech && ./../scripts/speech-venv.sh install-dev
	@cd speech && ./../scripts/speech-venv.sh cmd pytest
