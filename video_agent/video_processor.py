"""
Core video processing: loading, clipping, cropping, concatenating,
and compositing captions onto a clip.
"""

from __future__ import annotations
import os
from typing import List, Optional, Tuple

from moviepy.editor import (
    VideoFileClip,
    CompositeVideoClip,
    concatenate_videoclips,
    ColorClip,
    ImageClip,
)
from moviepy.video.fx.all import crop, resize

from config import PLATFORMS, BRAND
from caption_renderer import CaptionRenderer, WatermarkRenderer
from transcriber import Transcript


class VideoProcessor:
    def __init__(self, platform: str = "instagram_reel",
                 caption_style: str = "bold_bottom"):
        if platform not in PLATFORMS:
            raise ValueError(f"Unknown platform '{platform}'. "
                             f"Valid: {list(PLATFORMS.keys())}")
        self.platform = platform
        self.spec = PLATFORMS[platform]
        self.caption_style = caption_style
        self.out_w = self.spec["width"]
        self.out_h = self.spec["height"]

    # ------------------------------------------------------------------
    # Clip helpers
    # ------------------------------------------------------------------

    def load(self, path: str) -> VideoFileClip:
        return VideoFileClip(path, audio=True)

    def trim(self, clip: VideoFileClip,
             start: float, end: float) -> VideoFileClip:
        """Trim a clip to [start, end] seconds."""
        return clip.subclip(start, min(end, clip.duration))

    def smart_crop(self, clip: VideoFileClip) -> VideoFileClip:
        """
        Crop + resize the clip to match the target platform resolution.
        For vertical platforms (9:16) we centre-crop landscape footage.
        For horizontal (16:9) we letterbox vertical footage.
        """
        src_w, src_h = clip.size
        target_ratio = self.out_w / self.out_h
        src_ratio = src_w / src_h

        if abs(src_ratio - target_ratio) < 0.05:
            return resize(clip, (self.out_w, self.out_h))

        if target_ratio < 1.0 and src_ratio > 1.0:
            # Landscape → vertical: crop sides
            new_w = int(src_h * target_ratio)
            x_center = src_w / 2
            clipped = crop(clip,
                           x1=x_center - new_w / 2,
                           x2=x_center + new_w / 2)
            return resize(clipped, (self.out_w, self.out_h))

        if target_ratio > 1.0 and src_ratio < 1.0:
            # Vertical → landscape: letterbox with black bars
            scale = self.out_h / src_h
            scaled_w = int(src_w * scale)
            resized = resize(clip, (scaled_w, self.out_h))
            bg = ColorClip((self.out_w, self.out_h), color=(0, 0, 0),
                           duration=clip.duration)
            x_offset = (self.out_w - scaled_w) // 2
            return CompositeVideoClip([bg, resized.set_pos((x_offset, 0))])

        # Same orientation — just resize
        return resize(clip, (self.out_w, self.out_h))

    # ------------------------------------------------------------------
    # Concatenation
    # ------------------------------------------------------------------

    def build_sequence(self, clips: List[VideoFileClip]) -> VideoFileClip:
        """Join multiple clips with a smooth cross-fade of 0.3s."""
        if len(clips) == 1:
            return clips[0]
        from moviepy.editor import concatenate_videoclips
        return concatenate_videoclips(clips, method="compose", padding=-0.3)

    # ------------------------------------------------------------------
    # Caption overlay
    # ------------------------------------------------------------------

    def add_captions(self, clip: VideoFileClip,
                     transcript: Transcript) -> CompositeVideoClip:
        renderer = CaptionRenderer(self.out_w, self.out_h, self.caption_style)
        caption_clip = renderer.make_clip(transcript, clip.duration)
        return CompositeVideoClip([clip, caption_clip])

    # ------------------------------------------------------------------
    # Branding overlays
    # ------------------------------------------------------------------

    def add_intro_watermark(self, clip: VideoFileClip,
                             duration: float = 2.5) -> CompositeVideoClip:
        wm = WatermarkRenderer(self.out_w, self.out_h)
        intro = wm.make_intro_card(duration)
        return CompositeVideoClip([clip, intro])

    def add_cta_end_card(self, clip: VideoFileClip,
                          website: str,
                          cta_duration: float = 3.0) -> CompositeVideoClip:
        wm = WatermarkRenderer(self.out_w, self.out_h)
        # CTA shows during the last cta_duration seconds
        start = max(0.0, clip.duration - cta_duration)
        cta = wm.make_cta_card(website, cta_duration).set_start(start)
        return CompositeVideoClip([clip, cta])

    # ------------------------------------------------------------------
    # Full pipeline
    # ------------------------------------------------------------------

    def process(
        self,
        input_clips: List[Tuple[str, float, float]],   # (path, start, end)
        transcript: Optional[Transcript],
        music_path: Optional[str] = None,
        website: Optional[str] = None,
        use_ducking: bool = True,
    ) -> VideoFileClip:
        """
        Full pipeline:
          1. Load + trim each clip
          2. Smart-crop to platform resolution
          3. Concatenate
          4. Add captions
          5. Add branding
          6. Mix background music
        """
        from music_mixer import mix_music, duck_music_on_speech

        # Step 1-2: load, trim, crop
        processed: List[VideoFileClip] = []
        for path, t_start, t_end in input_clips:
            raw = self.load(path)
            trimmed = self.trim(raw, t_start, t_end)
            cropped = self.smart_crop(trimmed)
            processed.append(cropped)

        # Step 3: join
        final = self.build_sequence(processed)

        # Step 4: captions
        if transcript:
            final = self.add_captions(final, transcript)

        # Step 5: branding
        final = self.add_intro_watermark(final)
        if website:
            final = self.add_cta_end_card(final, website)

        # Step 6: music
        if use_ducking and transcript and music_path:
            final = duck_music_on_speech(final, transcript, music_path)
        elif music_path:
            final = mix_music(final, music_path)

        # Enforce max duration for short-form platforms
        max_dur = self.spec["max_duration"]
        if final.duration > max_dur:
            final = final.subclip(0, max_dur)

        return final
