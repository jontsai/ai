#!/usr/bin/env bash
set -euo pipefail

# Demo all voices with a greeting

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Voice definitions: voice_id|name|description
VOICES=(
  # American English - Female
  "af_alloy|Alloy|an American female"
  "af_aoede|Aoede|an American female"
  "af_bella|Bella|an American female"
  "af_heart|Heart|an American female"
  "af_jessica|Jessica|an American female"
  "af_kore|Kore|an American female"
  "af_nicole|Nicole|an American female"
  "af_nova|Nova|an American female"
  "af_river|River|an American female"
  "af_sarah|Sarah|an American female"
  "af_sky|Sky|an American female"
  # American English - Male
  "am_adam|Adam|an American male"
  "am_echo|Echo|an American male"
  "am_eric|Eric|an American male"
  "am_fenrir|Fenrir|an American male"
  "am_liam|Liam|an American male"
  "am_michael|Michael|an American male"
  "am_onyx|Onyx|an American male"
  "am_puck|Puck|an American male"
  "am_santa|Santa|an American male"
  # British English - Female
  "bf_alice|Alice|a British female"
  "bf_emma|Emma|a British female"
  "bf_isabella|Isabella|a British female"
  "bf_lily|Lily|a British female"
  # British English - Male
  "bm_daniel|Daniel|a British male"
  "bm_fable|Fable|a British male"
  "bm_george|George|a British male"
  "bm_lewis|Lewis|a British male"
  # Japanese - Female (greet in Japanese)
  "jf_alpha|Alpha|日本語の女性|ja"
  "jf_gongitsune|Gongitsune|日本語の女性|ja"
  "jf_nezumi|Nezumi|日本語の女性|ja"
  "jf_tebukuro|Tebukuro|日本語の女性|ja"
  # Japanese - Male (greet in Japanese)
  "jm_kumo|Kumo|日本語の男性|ja"
  # Mandarin Chinese - Female (greet in Chinese)
  "zf_xiaobei|Xiaobei|中文女声|zh"
  "zf_xiaoni|Xiaoni|中文女声|zh"
  "zf_xiaoxiao|Xiaoxiao|中文女声|zh"
  "zf_xiaoyi|Xiaoyi|中文女声|zh"
  # Mandarin Chinese - Male (greet in Chinese)
  "zm_yunjian|Yunjian|中文男声|zh"
  "zm_yunxi|Yunxi|中文男声|zh"
  "zm_yunxia|Yunxia|中文男声|zh"
  "zm_yunyang|Yunyang|中文男声|zh"
  # Spanish - Female
  "ef_dora|Dora|una voz femenina española|es"
  # Spanish - Male
  "em_alex|Alex|una voz masculina española|es"
  "em_santa|Santa|una voz masculina española|es"
  # French - Female
  "ff_siwis|Siwis|une voix féminine française|fr"
  # Hindi - Female
  "hf_alpha|Alpha|एक हिंदी महिला|hi"
  "hf_beta|Beta|एक हिंदी महिला|hi"
  # Hindi - Male
  "hm_omega|Omega|एक हिंदी पुरुष|hi"
  "hm_psi|Psi|एक हिंदी पुरुष|hi"
  # Italian - Female
  "if_sara|Sara|una voce femminile italiana|it"
  # Italian - Male
  "im_nicola|Nicola|una voce maschile italiana|it"
  # Brazilian Portuguese - Female
  "pf_dora|Dora|uma voz feminina brasileira|pt-br"
  # Brazilian Portuguese - Male
  "pm_alex|Alex|uma voz masculina brasileira|pt-br"
  "pm_santa|Santa|uma voz masculina brasileira|pt-br"
)

echo "Voice demo: ${#VOICES[@]} voices"
echo "=========================================="

for entry in "${VOICES[@]}"; do
  IFS='|' read -r voice_id name desc lang <<< "$entry"
  lang="${lang:-en-us}"  # default to English

  echo "[$voice_id] $name - $desc"

  # Generate greeting based on language
  case "$lang" in
    ja)
      text="こんにちは！私は${name}です、${desc}です。今日はどうお手伝いしましょうか？"
      ;;
    zh)
      text="你好！我是${name}，${desc}。今天我能帮您什么？"
      ;;
    es)
      text="¡Hola! Soy ${name}, ${desc}. ¿En qué puedo ayudarte hoy?"
      ;;
    fr)
      text="Bonjour! Je suis ${name}, ${desc}. Comment puis-je vous aider aujourd'hui?"
      ;;
    hi)
      text="नमस्ते! मैं ${name} हूं, ${desc}। आज मैं आपकी कैसे मदद कर सकती हूं?"
      ;;
    it)
      text="Ciao! Sono ${name}, ${desc}. Come posso aiutarti oggi?"
      ;;
    pt-br)
      text="Olá! Eu sou ${name}, ${desc}. Como posso ajudá-lo hoje?"
      ;;
    *)
      text="Hi! I'm ${name}, ${desc}. How can I help you today?"
      ;;
  esac

  "$SCRIPT_DIR/say.sh" -v "$voice_id" "$text"

  sleep 0.5
done

echo "=========================================="
echo "Done!"
