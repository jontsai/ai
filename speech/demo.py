#!/usr/bin/env python3
"""
Interactive TTS voice demo using Textual.

Controls:
  Tab         = Switch focus between text input and voice list
  ↑/↓ or j/k  = Navigate voices
  Enter       = Play current voice with text
  Space       = Pause/resume auto-advance
  q           = Quit
"""
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

# Add parent dir to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Select,
    Static,
)
from textual.worker import Worker, WorkerState

import numpy as np
import soundfile as sf


# =============================================================================
# Custom Input with readline bindings
# =============================================================================

class ReadlineInput(Input):
    """Input widget with readline-style keybindings."""

    BINDINGS = [
        Binding("ctrl+b", "cursor_left", "Cursor left", show=False),
        Binding("ctrl+f", "cursor_right", "Cursor right", show=False),
        # ctrl+a and ctrl+e already work in Textual Input
    ]


# =============================================================================
# Constants
# =============================================================================

# Language-specific greetings for the demo
# Placeholders: {name}, {nationality_article}, {nationality}, {gender}, {notes}
LANG_GREETINGS = {
    "a": "Hi! I'm {name}, {nationality_article} {nationality} {gender}. How can I help you today?",
    "b": "Hello! I'm {name}, {nationality_article} {nationality} {gender}. How may I assist you?",
    "j": "こんにちは！私は{name}です。{nationality}の{gender}です。今日はどのようにお手伝いできますか？",
    "z": "你好！我是{name}，{nationality_article}{nationality}{gender}。今天我能帮你什么忙？",
    "e": "¡Hola! Soy {name}, {nationality_article} {gender} {nationality}. ¿En qué puedo ayudarte hoy?",
    "f": "Bonjour ! Je suis {name}, {nationality_article} {gender} {nationality}. Comment puis-je vous aider ?",
    "h": "नमस्ते! मैं {name} हूं, {nationality_article} {nationality} {gender}। आज मैं आपकी कैसे मदद कर सकती हूं?",
    "i": "Ciao! Sono {name}, {nationality_article} {gender} {nationality}. Come posso aiutarti oggi?",
    "p": "Olá! Eu sou {name}, {nationality_article} {gender} {nationality}. Como posso ajudá-lo hoje?",
}
DEFAULT_TEXT = LANG_GREETINGS["a"]


def get_greeting_for_lang(lang_prefix: str) -> str:
    """Get the greeting template for a language prefix."""
    return LANG_GREETINGS.get(lang_prefix, DEFAULT_TEXT)

# Import language metadata from tts module (single source of truth)
from tts import VOICE_LANG_META, get_article, is_cosyvoice_available


@dataclass
class Voice:
    """Voice definition with properties derived from voice_id."""
    voice_id: str
    notes: str = ""
    # Override fields for non-standard voice IDs (like CosyVoice)
    _name: str = ""
    _gender: str = ""
    _lang_code: str = ""
    _ref_audio: str = ""  # Reference audio path for CosyVoice cloning

    @property
    def name(self) -> str:
        """Derive name from voice_id (e.g., 'af_heart' -> 'Heart')."""
        if self._name:
            return self._name
        return self.voice_id.split("_", 1)[1].title()

    @property
    def gender(self) -> str:
        """Derive gender from voice_id[1] ('f'=Female, 'm'=Male)."""
        if self._gender:
            return self._gender
        return "Female" if self.voice_id[1] == "f" else "Male"

    @property
    def lang_code(self) -> str:
        """Derive language code from voice_id[0]."""
        if self._lang_code:
            return self._lang_code
        return VOICE_LANG_META.get(self.voice_id[0], ("en-us", ""))[0]

    @property
    def nationality(self) -> str:
        """Derive nationality from voice_id[0]."""
        if self._lang_code == "cmn":
            return "Chinese"
        return VOICE_LANG_META.get(self.voice_id[0], ("en-us", ""))[1]

    @property
    def nationality_article(self) -> str:
        """Compute article (a/an) based on nationality's first letter."""
        return get_article(self.nationality)

    @property
    def greeting(self) -> str:
        """Get the language-appropriate greeting template."""
        # For CosyVoice, use 'z' prefix for Chinese greeting
        if self._lang_code == "cmn":
            return get_greeting_for_lang("z")
        return get_greeting_for_lang(self.voice_id[0])

    @property
    def model(self) -> str:
        """Return the TTS model used for this voice."""
        if self.voice_id.startswith("cosyvoice_"):
            return "CosyVoice"
        return "Kokoro"

    @property
    def ref_audio(self) -> str:
        """Return the reference audio path for CosyVoice cloning."""
        return self._ref_audio


def V(voice_id: str, notes: str = "", name: str = "", gender: str = "", lang_code: str = "", ref_audio: str = "") -> Voice:
    """Shorthand for creating Voice instances."""
    return Voice(voice_id, notes, name, gender, lang_code, ref_audio)


# Voice definitions: (lang_name, lang_code, [Voice, ...])
# Voice properties (name, gender, lang_code, article, nationality) derived from voice_id
LANGUAGES = [
    ("American English", "en-us", [
        V("af_alloy"),
        V("af_aoede"),
        V("af_bella", "warm, husky"),
        V("af_heart", "default"),
        V("af_jessica"),
        V("af_kore"),
        V("af_nicole", "ASMR"),
        V("af_nova"),
        V("af_river"),
        V("af_sarah"),
        V("af_sky"),
        V("am_adam"),
        V("am_echo"),
        V("am_eric"),
        V("am_fenrir"),
        V("am_liam"),
        V("am_michael"),
        V("am_onyx"),
        V("am_puck"),
        V("am_santa"),
    ]),
    ("British English", "en-gb", [
        V("bf_alice"),
        V("bf_emma"),
        V("bf_isabella"),
        V("bf_lily"),
        V("bm_daniel"),
        V("bm_fable"),
        V("bm_george"),
        V("bm_lewis"),
    ]),
    ("Japanese", "ja", [
        V("jf_alpha"),
        V("jf_gongitsune"),
        V("jf_nezumi"),
        V("jf_tebukuro"),
        V("jm_kumo"),
    ]),
    ("Chinese", "cmn", [
        V("cosyvoice_chinese", "high quality, slow", name="CosyVoice", gender="Female", lang_code="cmn"),
        V("zf_xiaobei"),
        V("zf_xiaoni"),
        V("zf_xiaoxiao"),
        V("zf_xiaoyi"),
        V("zm_yunjian"),
        V("zm_yunxi"),
        V("zm_yunxia"),
        V("zm_yunyang"),
    ]),
    ("Spanish", "es", [
        V("ef_dora"),
        V("em_alex"),
        V("em_santa"),
    ]),
    ("French", "fr-fr", [
        V("ff_siwis"),
    ]),
    ("Hindi", "hi", [
        V("hf_alpha"),
        V("hf_beta"),
        V("hm_omega"),
        V("hm_psi"),
    ]),
    ("Italian", "it", [
        V("if_sara"),
        V("im_nicola"),
    ]),
    ("Portuguese", "pt-br", [
        V("pf_dora"),
        V("pm_alex"),
        V("pm_santa"),
    ]),
    ("Sampled Voices - Chinese", "cmn", [
        V("cosyvoice_default_zh", "default female", name="Default", gender="Female", lang_code="cmn",
          ref_audio="cosyvoice/asset/zero_shot_prompt.wav"),
        V("cosyvoice_jontsai_zh", "custom clone", name="Jonathan", gender="Male", lang_code="cmn",
          ref_audio="samples/Jonathan_Tsai/zh_psalm_23.wav"),
    ]),
    ("Sampled Voices - English", "en-us", [
        V("cosyvoice_default_en", "default female", name="Default", gender="Female", lang_code="en-us",
          ref_audio="cosyvoice/asset/zero_shot_prompt.wav"),
        V("cosyvoice_jontsai_en", "custom clone", name="Jonathan", gender="Male", lang_code="en-us",
          ref_audio="samples/Jonathan_Tsai/en_psalm_23.wav"),
    ]),
]


# =============================================================================
# Audio Functions
# =============================================================================

def stop_audio():
    """Stop any currently playing audio."""
    subprocess.run(['killall', 'afplay'], stderr=subprocess.DEVNULL)


def play_audio_file(wav_path: str) -> subprocess.Popen:
    """Start playing audio, return process handle."""
    return subprocess.Popen(
        ['afplay', wav_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )


def generate_audio(text: str, voice_id: str, lang_code: str, ref_audio: str = "") -> str:
    """Generate TTS audio and return temp file path."""
    import tts

    # Use the lang_code directly - tts.py handles espeak-ng codes
    samples, sample_rate = tts.synthesize(text, voice=voice_id, lang=lang_code, ref_audio=ref_audio)

    fd, tmp_path = tempfile.mkstemp(suffix='.wav')
    os.close(fd)
    sf.write(tmp_path, samples, sample_rate)
    return tmp_path


# =============================================================================
# Textual App
# =============================================================================

class VoiceDemoApp(App):
    """Kokoro TTS Voice Demo with editable text input."""

    CSS = """
    Screen {
        layout: vertical;
    }

    #main-container {
        height: 1fr;
        padding: 1;
    }

    #text-section {
        height: auto;
        margin-bottom: 1;
    }

    #text-label {
        margin-bottom: 0;
        color: $text-muted;
    }

    #text-input {
        width: 100%;
    }

    #controls-row {
        height: 3;
        margin-bottom: 1;
    }

    #lang-select {
        width: 30;
    }

    #status {
        width: 1fr;
        content-align: right middle;
        text-align: right;
        color: $warning;
    }

    #voice-table {
        height: 1fr;
    }

    DataTable > .datatable--cursor {
        background: $accent;
        color: $text;
    }

    .playing {
        color: $success;
    }
    """

    BINDINGS = [
        Binding("tab", "focus_next", "Next Field", show=True),
        Binding("shift+tab", "focus_previous", "Prev Field", show=False),
        Binding("j", "cursor_down", "↓ Voice", show=True),
        Binding("k", "cursor_up", "↑ Voice", show=True),
        Binding("enter", "play", "Play", show=True),
        Binding("space", "toggle_pause", "Pause", show=True),
        Binding("q", "quit", "Quit", show=True),
        Binding("escape", "quit", "Quit", show=False),
    ]

    def __init__(self):
        super().__init__()
        self.lang_idx = 0
        self.audio_proc = None
        self.tmp_path = None
        self.paused = False
        self.played = set()  # Track played (lang_idx, voice_idx)

    def compose(self) -> ComposeResult:
        """Create the UI layout."""
        yield Header()

        with Vertical(id="main-container"):
            # Text input section
            with Vertical(id="text-section"):
                yield Label("Text to speak (use {name}, {lang_name}, {desc} for placeholders):", id="text-label")
                yield ReadlineInput(value=DEFAULT_TEXT, id="text-input", select_on_focus=False)

            # Language selector and status
            with Horizontal(id="controls-row"):
                lang_options = [(name, i) for i, (name, _, _) in enumerate(LANGUAGES)]
                yield Select(lang_options, value=0, id="lang-select")
                yield Static("", id="status")

            # Voice table
            yield DataTable(id="voice-table", cursor_type="row")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize the voice table on startup."""
        self.title = "Kokoro TTS Voice Demo"
        self.sub_title = "Tab to switch focus | Enter to play"

        table = self.query_one("#voice-table", DataTable)
        table.add_columns("Voice ID", "Name", "Gender", "Model", "Notes", "Played")
        self._populate_voices()

        # Focus the table by default
        table.focus()

        # Start playing the first voice
        self.set_timer(0.5, self._play_current)

    def _populate_voices(self) -> None:
        """Fill the voice table with current language's voices."""
        table = self.query_one("#voice-table", DataTable)
        table.clear()

        _, lang_code, voices = LANGUAGES[self.lang_idx]
        for i, voice in enumerate(voices):
            played_mark = "✓" if (self.lang_idx, i) in self.played else ""
            table.add_row(voice.voice_id, voice.name, voice.gender, voice.model, voice.notes, played_mark, key=str(i))

    def _update_status(self, text: str) -> None:
        """Update the status display."""
        status = self.query_one("#status", Static)
        status.update(text)

    def _get_current_selection(self) -> tuple[Voice, str, int]:
        """Get current voice info: (Voice, lang_code, row_idx)."""
        table = self.query_one("#voice-table", DataTable)
        _, lang_code, voices = LANGUAGES[self.lang_idx]

        row_idx = table.cursor_row
        if row_idx < 0 or row_idx >= len(voices):
            row_idx = 0

        return voices[row_idx], lang_code, row_idx

    def _get_text_to_speak(self) -> str:
        """Get the text to speak, with placeholders filled in."""
        text_input = self.query_one("#text-input", Input)
        voice, _, _ = self._get_current_selection()

        text = text_input.value

        # Replace placeholders using Voice properties
        text = text.replace("{name}", voice.name)
        text = text.replace("{nationality_article}", voice.nationality_article)
        text = text.replace("{nationality}", voice.nationality)
        text = text.replace("{gender}", voice.gender)
        text = text.replace("{notes}", voice.notes)

        return text

    def _cleanup_audio(self) -> None:
        """Clean up audio process and temp file."""
        if self.audio_proc:
            self.audio_proc.terminate()
            self.audio_proc = None
        if self.tmp_path and os.path.exists(self.tmp_path):
            os.unlink(self.tmp_path)
            self.tmp_path = None

    @work(exclusive=True, thread=True)
    def _generate_and_play(self, text: str, voice_id: str, lang_code: str, ref_audio: str = "") -> str:
        """Generate audio in background thread."""
        return generate_audio(text, voice_id, lang_code, ref_audio)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Handle audio generation completion."""
        if event.state == WorkerState.SUCCESS:
            self.tmp_path = event.worker.result
            stop_audio()
            self.audio_proc = play_audio_file(self.tmp_path)
            # Show CosyVoice indicator
            voice, _, _ = self._get_current_selection()
            if voice.voice_id.startswith("cosyvoice_"):
                self._update_status("▶ Playing (CosyVoice)...")
            else:
                self._update_status("▶ Playing...")
            # Start polling for audio completion
            self.set_timer(0.5, self._check_audio_finished)
        elif event.state == WorkerState.ERROR:
            self._update_status("Error generating audio")

    def _check_audio_finished(self) -> None:
        """Poll for audio playback completion."""
        if self.audio_proc and self.audio_proc.poll() is not None:
            self.audio_proc = None
            self._update_status("")
            if not self.paused:
                self._advance_and_play()
        elif self.audio_proc:
            # Keep polling
            self.set_timer(0.3, self._check_audio_finished)

    def _advance_and_play(self) -> None:
        """Move to next voice and play."""
        table = self.query_one("#voice-table", DataTable)
        _, _, voices = LANGUAGES[self.lang_idx]

        next_row = (table.cursor_row + 1) % len(voices)
        table.move_cursor(row=next_row)
        self._play_current()

    def _play_current(self) -> None:
        """Play the currently selected voice."""
        self._cleanup_audio()
        stop_audio()

        voice, _, row_idx = self._get_current_selection()
        text = self._get_text_to_speak()

        # Mark as played
        self.played.add((self.lang_idx, row_idx))
        self._populate_voices()  # Refresh to show checkmark

        # Restore cursor position
        table = self.query_one("#voice-table", DataTable)
        table.move_cursor(row=row_idx)

        # Show CosyVoice indicator
        if voice.voice_id.startswith("cosyvoice_"):
            self._update_status("Generating (CosyVoice)...")
        else:
            self._update_status("Generating...")
        self._generate_and_play(text, voice.voice_id, voice.lang_code, voice.ref_audio)

    # -------------------------------------------------------------------------
    # Event Handlers
    # -------------------------------------------------------------------------

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle language selection change."""
        if event.select.id == "lang-select" and event.value is not None:
            self.lang_idx = event.value
            self._populate_voices()
            self._cleanup_audio()
            stop_audio()
            self._update_status("")
            # Update text input with language-appropriate greeting
            _, _, voices = LANGUAGES[self.lang_idx]
            if voices:
                text_input = self.query_one("#text-input", Input)
                text_input.value = voices[0].greeting

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle voice selection (Enter key on table)."""
        self.paused = False
        self._play_current()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter in text input."""
        self.paused = False
        self._play_current()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Restore language-appropriate default text if input is cleared."""
        if event.input.id == "text-input" and event.value == "":
            _, _, voices = LANGUAGES[self.lang_idx]
            if voices:
                event.input.value = voices[0].greeting
            else:
                event.input.value = DEFAULT_TEXT

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------

    def action_toggle_pause(self) -> None:
        """Toggle pause/resume auto-advance."""
        self.paused = not self.paused
        if self.paused:
            stop_audio()
            self._cleanup_audio()
            self._update_status("[PAUSED]")
        else:
            self._update_status("")
            self._play_current()

    def action_play(self) -> None:
        """Play current voice."""
        self.paused = False
        self._play_current()

    def action_cursor_down(self) -> None:
        """Move cursor down in voice table (j key)."""
        table = self.query_one("#voice-table", DataTable)
        if self.screen.focused == table:
            table.action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move cursor up in voice table (k key)."""
        table = self.query_one("#voice-table", DataTable)
        if self.screen.focused == table:
            table.action_cursor_up()

    def action_quit(self) -> None:
        """Clean up and quit."""
        self._cleanup_audio()
        stop_audio()
        self.exit()


def main():
    app = VoiceDemoApp()
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
