# Kokoro TTS Voices

54 voices across 9 languages. Use with `./scripts/say.sh -v <voice_id>` or `make say VOICE=<voice_id>`.

## American English (20 voices)

| Voice ID | Name | Gender |
|----------|------|--------|
| `af_alloy` | Alloy | Female |
| `af_aoede` | Aoede | Female |
| `af_bella` | Bella | Female |
| `af_heart` | Heart | Female (default) |
| `af_jessica` | Jessica | Female |
| `af_kore` | Kore | Female |
| `af_nicole` | Nicole | Female |
| `af_nova` | Nova | Female |
| `af_river` | River | Female |
| `af_sarah` | Sarah | Female |
| `af_sky` | Sky | Female |
| `am_adam` | Adam | Male |
| `am_echo` | Echo | Male |
| `am_eric` | Eric | Male |
| `am_fenrir` | Fenrir | Male |
| `am_liam` | Liam | Male |
| `am_michael` | Michael | Male |
| `am_onyx` | Onyx | Male |
| `am_puck` | Puck | Male |
| `am_santa` | Santa | Male |

## British English (8 voices)

| Voice ID | Name | Gender |
|----------|------|--------|
| `bf_alice` | Alice | Female |
| `bf_emma` | Emma | Female |
| `bf_isabella` | Isabella | Female |
| `bf_lily` | Lily | Female |
| `bm_daniel` | Daniel | Male |
| `bm_fable` | Fable | Male |
| `bm_george` | George | Male |
| `bm_lewis` | Lewis | Male |

## Japanese (5 voices)

| Voice ID | Name | Gender |
|----------|------|--------|
| `jf_alpha` | Alpha | Female |
| `jf_gongitsune` | Gongitsune | Female |
| `jf_nezumi` | Nezumi | Female |
| `jf_tebukuro` | Tebukuro | Female |
| `jm_kumo` | Kumo | Male |

## Mandarin Chinese (8 voices)

| Voice ID | Name | Gender |
|----------|------|--------|
| `zf_xiaobei` | Xiaobei | Female |
| `zf_xiaoni` | Xiaoni | Female |
| `zf_xiaoxiao` | Xiaoxiao | Female |
| `zf_xiaoyi` | Xiaoyi | Female |
| `zm_yunjian` | Yunjian | Male |
| `zm_yunxi` | Yunxi | Male |
| `zm_yunxia` | Yunxia | Male |
| `zm_yunyang` | Yunyang | Male |

## Spanish (3 voices)

| Voice ID | Name | Gender |
|----------|------|--------|
| `ef_dora` | Dora | Female |
| `em_alex` | Alex | Male |
| `em_santa` | Santa | Male |

## French (1 voice)

| Voice ID | Name | Gender |
|----------|------|--------|
| `ff_siwis` | Siwis | Female |

## Hindi (4 voices)

| Voice ID | Name | Gender |
|----------|------|--------|
| `hf_alpha` | Alpha | Female |
| `hf_beta` | Beta | Female |
| `hm_omega` | Omega | Male |
| `hm_psi` | Psi | Male |

## Italian (2 voices)

| Voice ID | Name | Gender |
|----------|------|--------|
| `if_sara` | Sara | Female |
| `im_nicola` | Nicola | Male |

## Brazilian Portuguese (3 voices)

| Voice ID | Name | Gender |
|----------|------|--------|
| `pf_dora` | Dora | Female |
| `pm_alex` | Alex | Male |
| `pm_santa` | Santa | Male |

## Voice ID Convention

The voice ID format is `{lang}{gender}_{name}`:
- **Lang**: `a`=American, `b`=British, `j`=Japanese, `z`=Chinese, `e`=Spanish, `f`=French, `h`=Hindi, `i`=Italian, `p`=Portuguese
- **Gender**: `f`=female, `m`=male

## Speed Control

Adjust speech rate with `-s` or `SPEED`:
- `0.5` = half speed (slower)
- `1.0` = normal (default)
- `1.5` = 1.5x faster
- `2.0` = double speed

```bash
./scripts/say.sh -v bf_emma -s 1.2 "Hello world"
make say TEXT="Hello" VOICE=am_adam SPEED=0.8
```

## Demo Voices

```bash
# Interactive demo with j/k navigation
make voice-demo

# Play all 54 voices sequentially
make voice-demo-all
```

### Interactive Controls

| Key | Action |
|-----|--------|
| `j` / `n` / `→` / `Space` | Next voice |
| `k` / `p` / `←` | Previous voice |
| `r` | Replay current |
| `1-9` | Jump to voice |
| `q` / `Esc` | Quit |
