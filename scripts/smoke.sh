#!/usr/bin/env bash
set -euo pipefail

MODEL_SET="${1:-default}"

# Load model sets and smoke prompts
# shellcheck disable=SC1091
source ./models.mk >/dev/null 2>&1 || true

# models.mk is Make syntax, not Bash. We parse via `make` for model list,
# and rely on environment-style prompt keys baked into this script via case.
models="$(make -s _models_for_set MODEL_SET="$MODEL_SET")"

if [[ -z "${models// }" ]]; then
  echo "ERROR: No models for MODEL_SET=$MODEL_SET"
  exit 1
fi

echo "MODEL_SET=$MODEL_SET"
echo

run_smoke () {
  local model="$1"
  local prompt="$2"

  echo "=== $model ==="
  echo "Prompt: ${prompt:0:120}..."
  echo

  # Use a low token budget; smoke tests should be quick.
  # `ollama run` supports -p / --prompt on some versions; if not, we pipe.
  if ollama run "$model" -p "$prompt" >/dev/null 2>&1; then
    ollama run "$model" -p "$prompt" | head -n 60
  else
    printf "%s\n" "$prompt" | ollama run "$model" | head -n 60
  fi

  echo
}

# Pick prompt per model
for m in $models; do
  case "$m" in
    "llama3.2:3b")
      run_smoke "$m" 'Return valid JSON with keys: ok (bool), model (string), note (string).'
      ;;
    "qwen2.5-coder:32b")
      run_smoke "$m" $'Write a small TypeScript function that dedupes an array of objects by id. Include tests in Jest.'
      ;;
    "qwen3-coder:30b")
      run_smoke "$m" $'Refactor this code for clarity:\nfunction f(x){return x&&x.y&&x.y.z}\nReturn the refactored JS only.'
      ;;
    "gpt-oss:120b")
      run_smoke "$m" $'Explain mixture-of-experts vs dense models in 3 bullets, then give one practical routing rule for agents.'
      ;;
    "qwen3:235b-a22b")
      run_smoke "$m" $'You are a codebase planner. Given a large monorepo, propose a 6-step strategy to locate the most impactful refactor targets with minimal risk.'
      ;;
    *)
      run_smoke "$m" "Say 'ok' and explain in one sentence what you are good at."
      ;;
  esac
done