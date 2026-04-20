"""
Audio transcription using faster-whisper.
Produces word-level timestamps for animated captions.
"""

from __future__ import annotations
import os
import tempfile
from dataclasses import dataclass, field
from typing import List, Optional

try:
    from faster_whisper import WhisperModel
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False


@dataclass
class Word:
    text: str
    start: float
    end: float


@dataclass
class Segment:
    text: str
    start: float
    end: float
    words: List[Word] = field(default_factory=list)


@dataclass
class Transcript:
    segments: List[Segment]
    language: str
    full_text: str

    def words_in_range(self, t_start: float, t_end: float) -> List[Word]:
        return [
            w for seg in self.segments
            for w in seg.words
            if w.end >= t_start and w.start <= t_end
        ]

    def segments_in_range(self, t_start: float, t_end: float) -> List[Segment]:
        return [s for s in self.segments if s.end >= t_start and s.start <= t_end]


class Transcriber:
    """Wraps faster-whisper for word-level transcription."""

    def __init__(self, model_size: str = "base"):
        if not WHISPER_AVAILABLE:
            raise RuntimeError(
                "faster-whisper is not installed.\n"
                "Run: pip install faster-whisper"
            )
        self.model = WhisperModel(model_size, device="cpu", compute_type="int8")

    def transcribe(self, audio_path: str, language: Optional[str] = None) -> Transcript:
        kwargs: dict = {"word_timestamps": True, "beam_size": 5}
        if language:
            kwargs["language"] = language

        segments_raw, info = self.model.transcribe(audio_path, **kwargs)

        segments: List[Segment] = []
        full_text_parts: List[str] = []

        for seg in segments_raw:
            words = []
            if seg.words:
                words = [Word(text=w.word.strip(), start=w.start, end=w.end) for w in seg.words]
            s = Segment(text=seg.text.strip(), start=seg.start, end=seg.end, words=words)
            segments.append(s)
            full_text_parts.append(seg.text.strip())

        return Transcript(
            segments=segments,
            language=info.language,
            full_text=" ".join(full_text_parts),
        )

    def extract_audio_and_transcribe(self, video_path: str) -> Transcript:
        """Extract audio from video then transcribe."""
        import subprocess
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", video_path, "-ac", "1", "-ar", "16000",
                 "-vn", tmp_path],
                check=True,
                capture_output=True,
            )
            return self.transcribe(tmp_path)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


def mock_transcript(duration: float) -> Transcript:
    """Return a stub transcript when Whisper is unavailable (for testing)."""
    words = [
        Word("Prime", 0.5, 1.0),
        Word("Land", 1.0, 1.4),
        Word("Solutions", 1.4, 2.0),
        Word("—", 2.0, 2.1),
        Word("built", 2.2, 2.6),
        Word("on", 2.6, 2.8),
        Word("the", 2.8, 2.9),
        Word("ground,", 2.9, 3.4),
        Word("built", 3.5, 3.9),
        Word("right.", 3.9, 4.5),
    ]
    seg = Segment(
        text="Prime Land Solutions — built on the ground, built right.",
        start=0.5, end=min(4.5, duration),
        words=[w for w in words if w.end <= duration],
    )
    return Transcript(segments=[seg], language="en",
                      full_text=seg.text)
