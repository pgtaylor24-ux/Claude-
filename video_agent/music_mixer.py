"""
Background music mixer.
Blends a music track under the voice audio at a low volume ratio
so the speaker always remains front and centre.
"""

from __future__ import annotations
import os
import random
from pathlib import Path
from typing import Optional

from config import MUSIC_VOICE_RATIO

BUILTIN_MUSIC_DIR = Path(__file__).parent / "assets" / "music"


def _resolve_music(music_path: Optional[str]) -> Optional[str]:
    if music_path and os.path.isfile(music_path):
        return music_path
    # Auto-pick from assets/music/ if available
    candidates = list(BUILTIN_MUSIC_DIR.glob("*.mp3")) + list(BUILTIN_MUSIC_DIR.glob("*.wav"))
    if candidates:
        return str(random.choice(candidates))
    return None


def mix_music(
    video_clip,
    music_path: Optional[str] = None,
    volume_ratio: float = MUSIC_VOICE_RATIO,
    fade_in: float = 1.5,
    fade_out: float = 2.0,
):
    """
    Overlays background music onto a moviepy VideoFileClip.
    Returns a new clip with mixed audio.

    volume_ratio: 0.15 means music is at 15% of the original audio level.
    """
    from moviepy.editor import AudioFileClip, CompositeAudioClip
    from moviepy.audio.fx.all import audio_fadein, audio_fadeout, volumex

    resolved = _resolve_music(music_path)
    if resolved is None:
        return video_clip  # No music available — return unchanged

    duration = video_clip.duration
    music = AudioFileClip(resolved)

    # Loop music if shorter than video
    if music.duration < duration:
        loops_needed = int(duration / music.duration) + 1
        from moviepy.editor import concatenate_audioclips
        music = concatenate_audioclips([music] * loops_needed)

    music = music.subclip(0, duration)
    music = volumex(music, volume_ratio)

    if fade_in:
        music = audio_fadein(music, fade_in)
    if fade_out:
        music = audio_fadeout(music, fade_out)

    if video_clip.audio is not None:
        mixed = CompositeAudioClip([video_clip.audio, music])
    else:
        mixed = music

    return video_clip.set_audio(mixed)


def duck_music_on_speech(
    video_clip,
    transcript,
    music_path: Optional[str] = None,
    speech_ratio: float = 0.08,
    silence_ratio: float = 0.30,
    fade: float = 0.3,
):
    """
    Advanced ducking: music pumps up in gaps between speech, ducks during speech.
    """
    from moviepy.editor import AudioFileClip, CompositeAudioClip
    from moviepy.audio.fx.all import volumex

    resolved = _resolve_music(music_path)
    if resolved is None:
        return video_clip

    duration = video_clip.duration
    music_raw = AudioFileClip(resolved)

    if music_raw.duration < duration:
        from moviepy.editor import concatenate_audioclips
        loops = int(duration / music_raw.duration) + 1
        music_raw = concatenate_audioclips([music_raw] * loops)
    music_raw = music_raw.subclip(0, duration)

    # Build per-sample volume envelope
    import numpy as np
    fps = 44100
    n_samples = int(duration * fps)
    envelope = np.full(n_samples, silence_ratio)

    for seg in transcript.segments:
        s = max(0, int((seg.start - fade) * fps))
        e = min(n_samples, int((seg.end + fade) * fps))
        envelope[s:e] = speech_ratio

    # Smooth envelope
    kernel_size = int(fade * fps)
    if kernel_size > 1:
        kernel = np.ones(kernel_size) / kernel_size
        envelope = np.convolve(envelope, kernel, mode="same")

    def make_music_frame(t):
        frame = music_raw.get_frame(t)
        idx = min(int(t * fps), n_samples - 1)
        return frame * envelope[idx]

    from moviepy.editor import AudioClip
    music_ducked = AudioClip(make_music_frame, duration=duration, fps=fps)

    if video_clip.audio is not None:
        mixed = CompositeAudioClip([video_clip.audio, music_ducked])
    else:
        mixed = music_ducked

    return video_clip.set_audio(mixed)
