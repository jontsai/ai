# speech

Local Speech-to-Text + Text-to-Speech workflows for macOS.

## Commands (from repo root)

One-time:
- `make speech-doctor`

Daily:
- `make talk`  (record -> transcribe -> speak)

Piecewise:
- `make listen` (records speech/in.wav)
- `make stt`    (writes speech/out.txt)
- `make tts`    (writes speech/out.wav and plays it)

## Adjustments

### Choose the right mic
1) List devices:
   - `./scripts/record.sh devices`

2) Record from a device index:
   - `MIC=":1" DURATION=15 make listen`

### Quality / speed knobs

STT:
- Model is Whisper `large-v3` via faster-whisper.  [oai_citation:9‡GitHub](https://github.com/SYSTRAN/faster-whisper?utm_source=chatgpt.com)
- For faster/cheaper, change to `medium` or `small`.

TTS:
- Kokoro uses a `voice` string (default `af_heart`).  [oai_citation:10‡PyPI](https://pypi.org/project/kokoro/?utm_source=chatgpt.com)
- After you like a voice, lock it in `speech/tts.py`.

## Philosophy

- Offline by default
- One-command sanity: `make speech-doctor`
- One-command loop: `make talk`