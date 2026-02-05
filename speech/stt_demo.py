#!/usr/bin/env python3
"""
Interactive STT recording demo using Textual.

Features:
  - Live transcription during recording (updates every few seconds)
  - Waveform visualization with trim markers
  - Segment-based editing (select and delete transcript segments)
  - Play selected audio regions

Controls:
  Space       = Start/stop recording
  Enter       = Transcribe full audio (if not live)
  p           = Play audio (selected region or full)
  [           = Set selection start
  ]           = Set selection end
  d           = Delete selected region
  t           = Transcribe selected region only
  r           = Reset selection
  s           = Save audio to file
  c           = Clear all
  q           = Quit
"""
import os
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Add parent dir to path for imports
sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import sounddevice as sd
import soundfile as sf
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.widgets import Footer, Header, Label, Static, DataTable, ProgressBar
from textual.worker import Worker, WorkerState

# =============================================================================
# Constants
# =============================================================================

SAMPLE_RATE = 16000  # 16kHz for speech recognition
CHANNELS = 1  # Mono
WAVEFORM_WIDTH = 70  # Characters for waveform display
WAVEFORM_CHARS = " ▁▂▃▄▅▆▇█"
LIVE_TRANSCRIBE_INTERVAL = 3.0  # Seconds between live transcriptions


# =============================================================================
# Audio State
# =============================================================================

@dataclass
class TranscriptSegment:
    """A segment of transcribed audio with timing info."""
    text: str
    start_time: float  # seconds
    end_time: float    # seconds

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


@dataclass
class AudioBuffer:
    """Holds recorded audio data and editing state."""
    samples: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.float32))
    sample_rate: int = SAMPLE_RATE

    # Selection markers (in samples)
    select_start: int = 0
    select_end: int = 0  # 0 means end of buffer

    # Transcript segments
    segments: list = field(default_factory=list)

    # Currently selected segment index
    selected_segment: int = -1

    @property
    def duration(self) -> float:
        """Duration in seconds."""
        return len(self.samples) / self.sample_rate if len(self.samples) > 0 else 0.0

    @property
    def select_end_actual(self) -> int:
        """Actual selection end position (0 means end of buffer)."""
        return self.select_end if self.select_end > 0 else len(self.samples)

    @property
    def selected_samples(self) -> np.ndarray:
        """Get samples within selection markers."""
        end = self.select_end_actual
        return self.samples[self.select_start:end]

    @property
    def selected_duration(self) -> float:
        """Duration of selected audio in seconds."""
        return len(self.selected_samples) / self.sample_rate

    @property
    def full_transcript(self) -> str:
        """Get full transcript text from all segments."""
        return " ".join(s.text for s in self.segments)

    def append(self, data: np.ndarray) -> None:
        """Append audio data to buffer."""
        self.samples = np.concatenate([self.samples, data.flatten()])

    def clear(self) -> None:
        """Clear the buffer."""
        self.samples = np.array([], dtype=np.float32)
        self.select_start = 0
        self.select_end = 0
        self.segments = []
        self.selected_segment = -1

    def delete_selection(self) -> None:
        """Delete audio within selection markers."""
        if len(self.samples) == 0:
            return

        end = self.select_end_actual
        # Keep audio before and after selection
        before = self.samples[:self.select_start]
        after = self.samples[end:]
        self.samples = np.concatenate([before, after])

        # Update segments - remove or adjust any that overlap
        deleted_start_sec = self.select_start / self.sample_rate
        deleted_end_sec = end / self.sample_rate
        deleted_duration = deleted_end_sec - deleted_start_sec

        new_segments = []
        for seg in self.segments:
            if seg.end_time <= deleted_start_sec:
                # Segment is entirely before deletion - keep as is
                new_segments.append(seg)
            elif seg.start_time >= deleted_end_sec:
                # Segment is entirely after deletion - shift times
                new_segments.append(TranscriptSegment(
                    text=seg.text,
                    start_time=seg.start_time - deleted_duration,
                    end_time=seg.end_time - deleted_duration
                ))
            # Segments that overlap with deletion are removed

        self.segments = new_segments
        self.select_start = 0
        self.select_end = 0

    def reset_selection(self) -> None:
        """Reset selection markers."""
        self.select_start = 0
        self.select_end = 0
        self.selected_segment = -1

    def time_to_samples(self, seconds: float) -> int:
        """Convert time in seconds to sample position."""
        return int(seconds * self.sample_rate)

    def samples_to_time(self, samples: int) -> float:
        """Convert sample position to time in seconds."""
        return samples / self.sample_rate


def render_waveform(samples: np.ndarray, width: int = WAVEFORM_WIDTH,
                    select_start: int = 0, select_end: int = 0,
                    play_pos: int = 0) -> str:
    """Render audio samples as ASCII waveform with selection highlight."""
    if len(samples) == 0:
        return "─" * width

    # Downsample to fit width
    chunk_size = max(1, len(samples) // width)
    chunks = []
    for i in range(width):
        start = i * chunk_size
        end = min(start + chunk_size, len(samples))
        if start < len(samples):
            chunk = samples[start:end]
            rms = np.sqrt(np.mean(chunk ** 2)) if len(chunk) > 0 else 0
            chunks.append(rms)
        else:
            chunks.append(0)

    # Normalize
    max_amp = max(chunks) if chunks else 1
    if max_amp > 0:
        chunks = [c / max_amp for c in chunks]

    # Convert to characters with selection highlighting
    waveform = ""
    select_end_actual = select_end if select_end > 0 else len(samples)

    for i, amp in enumerate(chunks):
        char_idx = int(amp * (len(WAVEFORM_CHARS) - 1))
        char = WAVEFORM_CHARS[char_idx]

        sample_pos = i * chunk_size

        # Playback position marker
        if play_pos > 0 and abs(sample_pos - play_pos) < chunk_size:
            waveform += f"\033[1;33m▼\033[0m"
        elif select_start > 0 or select_end > 0:
            # Selection active
            if select_start <= sample_pos < select_end_actual:
                # Inside selection - bright cyan
                waveform += f"\033[1;36m{char}\033[0m"
            else:
                # Outside selection - dim
                waveform += f"\033[2m{char}\033[0m"
        else:
            # No selection - normal green
            waveform += f"\033[1;32m{char}\033[0m"

    return waveform


def format_time(seconds: float) -> str:
    """Format seconds as MM:SS.s"""
    mins = int(seconds // 60)
    secs = seconds % 60
    return f"{mins:02d}:{secs:04.1f}"


# =============================================================================
# Textual App
# =============================================================================

class STTDemoApp(App):
    """STT Recording Demo with live transcription and segment editing."""

    CSS = """
    Screen {
        layout: vertical;
    }

    #main-container {
        height: 1fr;
        padding: 1;
    }

    #status-section {
        height: 3;
        margin-bottom: 1;
    }

    #status-label {
        width: 100%;
    }

    #waveform-section {
        height: 5;
        margin-bottom: 1;
        border: solid green;
        padding: 0 1;
    }

    #waveform-header {
        height: 1;
    }

    #waveform-label {
        color: $text-muted;
    }

    #time-label {
        color: $warning;
        text-align: right;
        width: 1fr;
    }

    #waveform {
        height: 1;
    }

    #selection-label {
        height: 1;
        color: $text-muted;
    }

    #segments-section {
        height: 1fr;
        margin-bottom: 1;
    }

    #segments-label {
        color: $text-muted;
        margin-bottom: 0;
    }

    #segments-table {
        height: 1fr;
    }

    DataTable > .datatable--cursor {
        background: $accent;
    }

    .recording {
        color: $error;
    }

    .playing {
        color: $success;
    }
    """

    BINDINGS = [
        Binding("space", "toggle_recording", "⏺ Record", show=True),
        Binding("p", "toggle_playback", "▶ Play", show=True),
        Binding("enter", "transcribe_all", "Transcribe", show=True),
        Binding("bracketleft", "set_select_start", "[", show=True),
        Binding("bracketright", "set_select_end", "]", show=True),
        Binding("d", "delete_selection", "Delete", show=True),
        Binding("t", "transcribe_selection", "Transcribe Sel", show=False),
        Binding("r", "reset_selection", "Reset", show=False),
        Binding("s", "save_audio", "Save", show=False),
        Binding("c", "clear_buffer", "Clear", show=False),
        Binding("q", "quit", "Quit", show=True),
        Binding("escape", "quit", "Quit", show=False),
    ]

    def __init__(self):
        super().__init__()
        self.audio = AudioBuffer()
        self.is_recording = False
        self.is_playing = False
        self.recording_stream = None
        self.record_start_time = 0
        self.play_position = 0
        self.last_transcribe_time = 0
        self.live_transcribe_enabled = True

    def compose(self) -> ComposeResult:
        """Create the UI layout."""
        yield Header()

        with Vertical(id="main-container"):
            # Status section
            with Vertical(id="status-section"):
                yield Static("Ready. Press Space to start recording.", id="status-label")

            # Waveform section
            with Vertical(id="waveform-section"):
                with Horizontal(id="waveform-header"):
                    yield Label("Waveform:", id="waveform-label")
                    yield Label("00:00.0", id="time-label")
                yield Static("─" * WAVEFORM_WIDTH, id="waveform")
                yield Static("Selection: none", id="selection-label")

            # Segments table
            with Vertical(id="segments-section"):
                yield Label("Transcript Segments (↑↓ to select, d to delete):", id="segments-label")
                yield DataTable(id="segments-table", cursor_type="row")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize on startup."""
        self.title = "STT Recording Demo"
        self.sub_title = "Space=Record | p=Play | [/]=Select | d=Delete"

        table = self.query_one("#segments-table", DataTable)
        table.add_columns("Time", "Duration", "Text")
        table.cursor_type = "row"

    def _update_status(self, text: str, style: str = "") -> None:
        """Update the status display."""
        status = self.query_one("#status-label", Static)
        if style:
            status.update(f"[{style}]{text}[/{style}]")
        else:
            status.update(text)

    def _update_waveform(self) -> None:
        """Update the waveform display."""
        waveform_widget = self.query_one("#waveform", Static)
        time_widget = self.query_one("#time-label", Label)
        selection_widget = self.query_one("#selection-label", Static)

        waveform = render_waveform(
            self.audio.samples,
            WAVEFORM_WIDTH,
            self.audio.select_start,
            self.audio.select_end,
            self.play_position
        )
        waveform_widget.update(waveform)

        time_widget.update(format_time(self.audio.duration))

        # Selection info
        if self.audio.select_start > 0 or self.audio.select_end > 0:
            start_sec = self.audio.samples_to_time(self.audio.select_start)
            end_sec = self.audio.samples_to_time(self.audio.select_end_actual)
            selection_widget.update(
                f"Selection: {format_time(start_sec)} - {format_time(end_sec)} "
                f"({end_sec - start_sec:.1f}s)"
            )
        else:
            selection_widget.update("Selection: none (use [ and ] to select)")

    def _update_segments_table(self) -> None:
        """Update the segments table."""
        table = self.query_one("#segments-table", DataTable)
        table.clear()

        for seg in self.audio.segments:
            time_str = format_time(seg.start_time)
            dur_str = f"{seg.duration:.1f}s"
            # Truncate long text
            text = seg.text[:60] + "..." if len(seg.text) > 60 else seg.text
            table.add_row(time_str, dur_str, text)

    # -------------------------------------------------------------------------
    # Recording
    # -------------------------------------------------------------------------

    def _recording_callback(self, indata, frames, time_info, status):
        """Called by sounddevice for each audio block during recording."""
        if self.is_recording:
            self.audio.append(indata.copy())

    def _start_recording(self) -> None:
        """Start recording audio."""
        self.audio.clear()
        self._update_segments_table()
        self.is_recording = True
        self.record_start_time = time.time()
        self.last_transcribe_time = time.time()

        self.recording_stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=np.float32,
            callback=self._recording_callback
        )
        self.recording_stream.start()

        self._update_status("● Recording... Press Space to stop", "bold red")
        self._start_recording_timer()

    def _stop_recording(self) -> None:
        """Stop recording audio."""
        self.is_recording = False

        if self.recording_stream:
            self.recording_stream.stop()
            self.recording_stream.close()
            self.recording_stream = None

        duration = self.audio.duration
        self._update_status(f"Recorded {duration:.1f}s. Press Enter to transcribe, or p to play.")
        self._update_waveform()

    def _start_recording_timer(self) -> None:
        """Timer to update display and trigger live transcription."""
        if not self.is_recording:
            return

        elapsed = time.time() - self.record_start_time
        self._update_status(f"● Recording... [{format_time(elapsed)}] Press Space to stop", "bold red")
        self._update_waveform()

        # Live transcription every N seconds
        if self.live_transcribe_enabled and elapsed - (self.last_transcribe_time - self.record_start_time) >= LIVE_TRANSCRIBE_INTERVAL:
            if self.audio.duration > 1.0:  # Only if we have at least 1 second
                self.last_transcribe_time = time.time()
                self._transcribe_live()

        self.set_timer(0.1, self._start_recording_timer)

    # -------------------------------------------------------------------------
    # Playback
    # -------------------------------------------------------------------------

    def _start_playback(self) -> None:
        """Start playing audio."""
        if len(self.audio.samples) == 0:
            self._update_status("Nothing to play. Record something first.")
            return

        self.is_playing = True

        # Play selection or full audio
        if self.audio.select_start > 0 or self.audio.select_end > 0:
            samples_to_play = self.audio.selected_samples
            self.play_position = self.audio.select_start
        else:
            samples_to_play = self.audio.samples
            self.play_position = 0

        def playback_finished():
            self.is_playing = False
            self.play_position = 0
            self._update_status(f"Playback finished. {self.audio.duration:.1f}s recorded.")
            self._update_waveform()

        def play_thread():
            try:
                sd.play(samples_to_play, SAMPLE_RATE)
                sd.wait()
            finally:
                self.call_from_thread(playback_finished)

        threading.Thread(target=play_thread, daemon=True).start()
        self._update_status("▶ Playing...", "bold green")
        self._start_playback_timer()

    def _stop_playback(self) -> None:
        """Stop playback."""
        sd.stop()
        self.is_playing = False
        self.play_position = 0
        self._update_status(f"Playback stopped. {self.audio.duration:.1f}s recorded.")
        self._update_waveform()

    def _start_playback_timer(self) -> None:
        """Update playback position display."""
        if self.is_playing:
            self.play_position += int(SAMPLE_RATE * 0.1)
            end = self.audio.select_end_actual if self.audio.select_end > 0 else len(self.audio.samples)
            if self.play_position > end:
                self.play_position = end
            self._update_waveform()
            self.set_timer(0.1, self._start_playback_timer)

    # -------------------------------------------------------------------------
    # Transcription
    # -------------------------------------------------------------------------

    @work(exclusive=True, thread=True, group="transcribe")
    def _transcribe_audio(self, start_sample: int = 0, end_sample: int = 0) -> list:
        """Transcribe audio in background thread. Returns list of segments."""
        import stt as stt_module
        from faster_whisper import WhisperModel

        # Get samples to transcribe
        if end_sample == 0:
            end_sample = len(self.audio.samples)
        samples = self.audio.samples[start_sample:end_sample]

        if len(samples) < SAMPLE_RATE * 0.5:  # Less than 0.5 seconds
            return []

        # Save to temp file
        fd, tmp_path = tempfile.mkstemp(suffix='.wav')
        os.close(fd)

        try:
            sf.write(tmp_path, samples, SAMPLE_RATE)

            # Transcribe with timestamps
            model = WhisperModel("large-v3", device="auto", compute_type="int8")
            raw_segments, info = model.transcribe(tmp_path, vad_filter=True, word_timestamps=True)

            # Convert to our segment format
            segments = []
            start_offset = start_sample / SAMPLE_RATE

            for seg in raw_segments:
                text = (seg.text or "").strip()
                if text:
                    segments.append(TranscriptSegment(
                        text=text,
                        start_time=seg.start + start_offset,
                        end_time=seg.end + start_offset
                    ))

            return segments
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    @work(exclusive=True, thread=True, group="transcribe_live")
    def _transcribe_live(self) -> list:
        """Live transcription during recording - transcribe recent audio."""
        if len(self.audio.samples) < SAMPLE_RATE:
            return []

        # Transcribe the last few seconds
        samples = self.audio.samples[-int(SAMPLE_RATE * LIVE_TRANSCRIBE_INTERVAL * 2):]

        fd, tmp_path = tempfile.mkstemp(suffix='.wav')
        os.close(fd)

        try:
            sf.write(tmp_path, samples, SAMPLE_RATE)

            from faster_whisper import WhisperModel
            model = WhisperModel("base", device="auto", compute_type="int8")  # Faster model for live
            raw_segments, _ = model.transcribe(tmp_path, vad_filter=True)

            # Get text only for live preview
            texts = []
            for seg in raw_segments:
                text = (seg.text or "").strip()
                if text:
                    texts.append(text)

            return texts
        except Exception:
            return []
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Handle transcription completion."""
        if event.worker.group == "transcribe":
            if event.state == WorkerState.SUCCESS:
                segments = event.worker.result
                if segments:
                    self.audio.segments = segments
                    self._update_segments_table()
                    total_text = self.audio.full_transcript
                    self._update_status(f"Transcribed: {len(segments)} segments, {len(total_text)} chars")
                else:
                    self._update_status("No speech detected.")
            elif event.state == WorkerState.ERROR:
                self._update_status("Transcription failed!", "bold red")

        elif event.worker.group == "transcribe_live":
            if event.state == WorkerState.SUCCESS and self.is_recording:
                texts = event.worker.result
                if texts:
                    # Show live preview in status
                    preview = " ".join(texts)[:50]
                    if len(preview) < len(" ".join(texts)):
                        preview += "..."
                    elapsed = time.time() - self.record_start_time
                    self._update_status(
                        f"● [{format_time(elapsed)}] {preview}",
                        "bold red"
                    )

    # -------------------------------------------------------------------------
    # Table events
    # -------------------------------------------------------------------------

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """When a segment is selected, set selection to that time range."""
        if event.cursor_row < len(self.audio.segments):
            seg = self.audio.segments[event.cursor_row]
            self.audio.select_start = self.audio.time_to_samples(seg.start_time)
            self.audio.select_end = self.audio.time_to_samples(seg.end_time)
            self.audio.selected_segment = event.cursor_row
            self._update_waveform()
            self._update_status(f"Selected segment: {seg.text[:40]}...")

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------

    def action_toggle_recording(self) -> None:
        """Toggle recording on/off."""
        if self.is_playing:
            self._stop_playback()

        if self.is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def action_toggle_playback(self) -> None:
        """Toggle playback on/off."""
        if self.is_recording:
            self._stop_recording()

        if self.is_playing:
            self._stop_playback()
        else:
            self._start_playback()

    def action_transcribe_all(self) -> None:
        """Transcribe the full recorded audio."""
        if len(self.audio.samples) == 0:
            self._update_status("Nothing to transcribe. Record something first.")
            return

        if self.is_recording:
            self._stop_recording()
        if self.is_playing:
            self._stop_playback()

        self._update_status("Transcribing full audio...", "bold yellow")
        self._transcribe_audio(0, 0)

    def action_transcribe_selection(self) -> None:
        """Transcribe only the selected region."""
        if len(self.audio.samples) == 0:
            self._update_status("Nothing to transcribe.")
            return

        if self.audio.select_start == 0 and self.audio.select_end == 0:
            self._update_status("No selection. Use [ and ] to select a region.")
            return

        if self.is_recording:
            self._stop_recording()
        if self.is_playing:
            self._stop_playback()

        self._update_status("Transcribing selection...", "bold yellow")
        self._transcribe_audio(self.audio.select_start, self.audio.select_end_actual)

    def action_set_select_start(self) -> None:
        """Set selection start at current play position or 10% in."""
        if len(self.audio.samples) == 0:
            return

        if self.play_position > 0:
            self.audio.select_start = self.play_position
        else:
            self.audio.select_start = int(len(self.audio.samples) * 0.1)

        self._update_waveform()
        self._update_status(f"Selection start: {format_time(self.audio.samples_to_time(self.audio.select_start))}")

    def action_set_select_end(self) -> None:
        """Set selection end at current play position or 10% from end."""
        if len(self.audio.samples) == 0:
            return

        if self.play_position > 0:
            self.audio.select_end = self.play_position
        else:
            self.audio.select_end = int(len(self.audio.samples) * 0.9)

        self._update_waveform()
        self._update_status(f"Selection end: {format_time(self.audio.samples_to_time(self.audio.select_end))}")

    def action_delete_selection(self) -> None:
        """Delete selected region (audio and associated transcript segments)."""
        if len(self.audio.samples) == 0:
            return

        if self.audio.select_start == 0 and self.audio.select_end == 0:
            # If a segment is selected in table, delete that
            table = self.query_one("#segments-table", DataTable)
            if table.cursor_row < len(self.audio.segments):
                seg = self.audio.segments[table.cursor_row]
                self.audio.select_start = self.audio.time_to_samples(seg.start_time)
                self.audio.select_end = self.audio.time_to_samples(seg.end_time)

        if self.audio.select_start == 0 and self.audio.select_end == 0:
            self._update_status("No selection. Use [ and ] or select a segment.")
            return

        old_duration = self.audio.duration
        self.audio.delete_selection()
        new_duration = self.audio.duration

        self._update_waveform()
        self._update_segments_table()
        self._update_status(f"Deleted {old_duration - new_duration:.1f}s of audio")

    def action_reset_selection(self) -> None:
        """Reset selection markers."""
        self.audio.reset_selection()
        self._update_waveform()
        self._update_status("Selection reset.")

    def action_clear_buffer(self) -> None:
        """Clear the audio buffer."""
        self.audio.clear()
        self._update_waveform()
        self._update_segments_table()
        self._update_status("Buffer cleared. Press Space to record.")

    def action_save_audio(self) -> None:
        """Save audio to file."""
        if len(self.audio.samples) == 0:
            self._update_status("Nothing to save.")
            return

        os.makedirs("buffer", exist_ok=True)
        out_path = "buffer/recording.wav"

        # Save selection or full audio
        if self.audio.select_start > 0 or self.audio.select_end > 0:
            samples = self.audio.selected_samples
        else:
            samples = self.audio.samples

        sf.write(out_path, samples, SAMPLE_RATE)

        # Also save transcript if available
        if self.audio.segments:
            txt_path = "buffer/recording.txt"
            with open(txt_path, 'w') as f:
                f.write(self.audio.full_transcript)
            self._update_status(f"Saved to {out_path} and {txt_path}")
        else:
            self._update_status(f"Saved to {out_path}")

    def action_quit(self) -> None:
        """Clean up and quit."""
        if self.is_recording:
            self._stop_recording()
        if self.is_playing:
            self._stop_playback()
        self.exit()


def main():
    app = STTDemoApp()
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
