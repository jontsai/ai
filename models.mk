# models.mk
# Maintain your model sets here.

MODEL_SET ?= default

# --- Model sets ------------------------------------------------------------

# Keep small utility + best code worker(s)
MODELS_MINIMAL := \
	llama3.2:3b \
	qwen2.5-coder:32b

# Fallback brains (bigger, more capable)
MODELS_FALLBACK := \
	gpt-oss:120b \
	qwen3:235b-a22b

# Default = minimal + fallback + an extra coder to compare for a week
MODELS_DEFAULT := \
	$(MODELS_MINIMAL) \
	$(MODELS_FALLBACK) \
	qwen3-coder:30b

MODELS_ALL := \
	$(MODELS_DEFAULT)

# --- Smoke prompts ---------------------------------------------------------
# One prompt per model. Keep them short and deterministic-ish.

SMOKE_PROMPT_llama3_2_3b := \
"Return valid JSON with keys: ok (bool), model (string), note (string)."

SMOKE_PROMPT_qwen2_5_coder_32b := \
"Write a small TypeScript function that dedupes an array of objects by id. Include tests in Jest."

SMOKE_PROMPT_qwen3_coder_30b := \
"Refactor this code for clarity:\nfunction f(x){return x&&x.y&&x.y.z}\nReturn the refactored JS only."

SMOKE_PROMPT_gpt_oss_120b := \
"Explain mixture-of-experts vs dense models in 3 bullets, then give one practical routing rule for agents."

SMOKE_PROMPT_qwen3_235b_a22b := \
"You are a codebase planner. Given a large monorepo, propose a 6-step strategy to locate the most impactful refactor targets with minimal risk."

# Map a model tag -> variable name-safe key used by scripts.
# scripts/smoke.sh converts ":" and "-" and "." into "_" to match these variables.