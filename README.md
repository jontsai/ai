# ai

Personal CLI workflows for managing local LLMs via Ollama.
Goal: **offline-capable fallback** when cloud quotas (e.g. Opus) are exhausted.

This repo is private, for one person, optimized for:
- low memory burden (“remember processes, not details”)
- repeatable CLI operations
- quick sanity checks (doctor + smoke tests)

---

## Principles

### Routing beats replacement
No local model equals top-tier cloud judgment. The win is:
- local models handle frequent “agent work”
- cloud is reserved for hard judgment / ambiguity

### Don’t download raw HF safetensors unless you mean it
Hugging Face weights for huge models can be **400–500GB+** and are painful on macOS.
If your objective is “reliable offline fallback”, prefer **Ollama pulls**.

### Quantization (ELI5)
A model is a giant table of numbers.
Quantization stores those numbers in a smaller format:
- **smaller disk + lower memory**
- slightly less accurate
Ollama models are typically distributed in quantized form, which is why they’re practical locally.

---

## Model sets (managed in `models.mk`)

- **minimal**: tiny utility + best code worker
- **fallback**: big “brains” for planning / agentic tasks
- **default**: minimal + fallback + 2 coders (keep both for a week, delete the loser)

---

## Commands you should memorize

### 1) Verify everything works
```bash
make doctor