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

DEFAULT_TEXT = "Hi! I'm {name}, {lang_name} {desc}. How can I help you today?"

LANG_NAMES = {
    "en-us": "an American",
    "en-gb": "a British",
    "ja": "a Japanese",
    "zh": "a Chinese",
    "es": "a Spanish",
    "fr": "a French",
    "hi": "a Hindi",
    "it": "an Italian",
    "pt-br": "a Brazilian Portuguese",
}

# Voice definitions: (lang_name, lang_code, [(voice_id, name, desc), ...])
LANGUAGES = [
    ("American English", "en-us", [
        ("af_alloy", "Alloy", "Female"),
        ("af_aoede", "Aoede", "Female"),
        ("af_bella", "Bella", "Female, warm/husky"),
        ("af_heart", "Heart", "Female (default)"),
        ("af_jessica", "Jessica", "Female"),
        ("af_kore", "Kore", "Female"),
        ("af_nicole", "Nicole", "Female, ASMR"),
        ("af_nova", "Nova", "Female"),
        ("af_river", "River", "Female"),
        ("af_sarah", "Sarah", "Female"),
        ("af_sky", "Sky", "Female"),
        ("am_adam", "Adam", "Male"),
        ("am_echo", "Echo", "Male"),
        ("am_eric", "Eric", "Male"),
        ("am_fenrir", "Fenrir", "Male"),
        ("am_liam", "Liam", "Male"),
        ("am_michael", "Michael", "Male"),
        ("am_onyx", "Onyx", "Male"),
        ("am_puck", "Puck", "Male"),
        ("am_santa", "Santa", "Male"),
    ]),
    ("British English", "en-gb", [
        ("bf_alice", "Alice", "Female"),
        ("bf_emma", "Emma", "Female"),
        ("bf_isabella", "Isabella", "Female"),
        ("bf_lily", "Lily", "Female"),
        ("bm_daniel", "Daniel", "Male"),
        ("bm_fable", "Fable", "Male"),
        ("bm_george", "George", "Male"),
        ("bm_lewis", "Lewis", "Male"),
    ]),
    ("Japanese", "ja", [
        ("jf_alpha", "Alpha", "Female"),
        ("jf_gongitsune", "Gongitsune", "Female"),
        ("jf_nezumi", "Nezumi", "Female"),
        ("jf_tebukuro", "Tebukuro", "Female"),
        ("jm_kumo", "Kumo", "Male"),
    ]),
    ("Chinese", "zh", [
        ("zf_xiaobei", "Xiaobei", "Female"),
        ("zf_xiaoni", "Xiaoni", "Female"),
        ("zf_xiaoxiao", "Xiaoxiao", "Female"),
        ("zf_xiaoyi", "Xiaoyi", "Female"),
        ("zm_yunjian", "Yunjian", "Male"),
        ("zm_yunxi", "Yunxi", "Male"),
        ("zm_yunxia", "Yunxia", "Male"),
        ("zm_yunyang", "Yunyang", "Male"),
    ]),
    ("Spanish", "es", [
        ("ef_dora", "Dora", "Female"),
        ("em_alex", "Alex", "Male"),
        ("em_santa", "Santa", "Male"),
    ]),
    ("French", "fr", [
        ("ff_siwis", "Siwis", "Female"),
    ]),
    ("Hindi", "hi", [
        ("hf_alpha", "Alpha", "Female"),
        ("hf_beta", "Beta", "Female"),
        ("hm_omega", "Omega", "Male"),
        ("hm_psi", "Psi", "Male"),
    ]),
    ("Italian", "it", [
        ("if_sara", "Sara", "Female"),
        ("im_nicola", "Nicola", "Male"),
    ]),
    ("Portuguese", "pt-br", [
        ("pf_dora", "Dora", "Female"),
        ("pm_alex", "Alex", "Male"),
        ("pm_santa", "Santa", "Male"),
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


def generate_audio(text: str, voice_id: str, lang_code: str) -> str:
    """Generate TTS audio and return temp file path."""
    import tts

    # kokoro-onnx only supports en-us/en-gb phonemization
    tts_lang = "en-gb" if lang_code == "en-gb" else "en-us"
    samples, sample_rate = tts.synthesize(text, voice=voice_id, lang=tts_lang)

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
        table.add_columns("Voice ID", "Name", "Type", "Played")
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
        for i, (vid, name, desc) in enumerate(voices):
            played_mark = "✓" if (self.lang_idx, i) in self.played else ""
            table.add_row(vid, name, desc, played_mark, key=str(i))

    def _update_status(self, text: str) -> None:
        """Update the status display."""
        status = self.query_one("#status", Static)
        status.update(text)

    def _get_current_selection(self) -> tuple:
        """Get current voice info: (voice_id, name, desc, lang_code, row_idx)."""
        table = self.query_one("#voice-table", DataTable)
        _, lang_code, voices = LANGUAGES[self.lang_idx]

        row_idx = table.cursor_row
        if row_idx < 0 or row_idx >= len(voices):
            row_idx = 0

        voice_id, name, desc = voices[row_idx]
        return voice_id, name, desc, lang_code, row_idx

    def _get_text_to_speak(self) -> str:
        """Get the text to speak, with placeholders filled in."""
        text_input = self.query_one("#text-input", Input)
        voice_id, name, desc, lang_code, _ = self._get_current_selection()

        text = text_input.value
        lang_name = LANG_NAMES.get(lang_code, "a")

        # Replace placeholders
        text = text.replace("{name}", name)
        text = text.replace("{lang_name}", lang_name)
        text = text.replace("{desc}", desc)

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
    def _generate_and_play(self, text: str, voice_id: str, lang_code: str) -> str:
        """Generate audio in background thread."""
        return generate_audio(text, voice_id, lang_code)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Handle audio generation completion."""
        if event.state == WorkerState.SUCCESS:
            self.tmp_path = event.worker.result
            stop_audio()
            self.audio_proc = play_audio_file(self.tmp_path)
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

        voice_id, name, desc, lang_code, row_idx = self._get_current_selection()
        text = self._get_text_to_speak()

        # Mark as played
        self.played.add((self.lang_idx, row_idx))
        self._populate_voices()  # Refresh to show checkmark

        # Restore cursor position
        table = self.query_one("#voice-table", DataTable)
        table.move_cursor(row=row_idx)

        self._update_status("Generating...")
        self._generate_and_play(text, voice_id, lang_code)

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

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle voice selection (Enter key on table)."""
        self.paused = False
        self._play_current()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter in text input."""
        self.paused = False
        self._play_current()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Restore default text if input is cleared."""
        if event.input.id == "text-input" and event.value == "":
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
