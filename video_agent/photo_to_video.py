"""
Photo-to-video engine for Prime Land Solutions LLC.
Takes job site photos and builds a dynamic video with:
  - Ken Burns effect (slow pan + zoom) on each image
  - Cross-fade transitions between photos
  - Caption text overlay per photo
  - Background music + brand watermark
"""

from __future__ import annotations
import os
import random
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image, ImageFilter, ImageEnhance

from config import BRAND, PLATFORMS, SHORT_FORM_PLATFORMS, LONG_FORM_PLATFORMS

# Seconds each photo is shown (before transition)
SHORT_FORM_PHOTO_DURATION = 3.0
LONG_FORM_PHOTO_DURATION = 5.0
TRANSITION_DURATION = 0.5   # cross-fade seconds


# ---------------------------------------------------------------------------
# Ken Burns motion helpers
# ---------------------------------------------------------------------------

class KenBurnsClip:
    """
    Animates a still image with a slow pan+zoom (Ken Burns effect).
    Zoom goes from 1.0→1.12 or 1.12→1.0, pan varies per image.
    """

    MOVES = [
        # (zoom_start, zoom_end, pan_start_x, pan_start_y, pan_end_x, pan_end_y)
        # values are fractions of the overflow (zoom-1 area)
        (1.0, 1.12, 0.0, 0.0, 1.0, 1.0),    # zoom in, pan bottom-right
        (1.12, 1.0, 1.0, 1.0, 0.0, 0.0),    # zoom out, pan top-left
        (1.0, 1.10, 0.5, 0.0, 0.5, 1.0),    # zoom in, pan down-centre
        (1.0, 1.10, 0.0, 0.5, 1.0, 0.5),    # zoom in, pan right
        (1.08, 1.0, 0.0, 1.0, 1.0, 0.0),    # zoom out, pan top-right
    ]

    def __init__(self, img: Image.Image, out_w: int, out_h: int,
                 duration: float, move_index: Optional[int] = None):
        self.out_w = out_w
        self.out_h = out_h
        self.duration = duration

        # Fit image to output frame (cover — crop to fill)
        img = _cover_fit(img, out_w, out_h)
        self.img_np = np.array(img.convert("RGB"))
        self.move = self.MOVES[
            move_index % len(self.MOVES) if move_index is not None
            else random.randint(0, len(self.MOVES) - 1)
        ]

    def get_frame(self, t: float) -> np.ndarray:
        progress = t / self.duration  # 0.0 → 1.0
        z_start, z_end, px_s, py_s, px_e, py_e = self.move

        zoom = z_start + (z_end - z_start) * progress
        px = px_s + (px_e - px_s) * progress
        py = py_s + (py_e - py_s) * progress

        h, w = self.img_np.shape[:2]
        # Crop region size
        crop_w = int(w / zoom)
        crop_h = int(h / zoom)

        # Pan offsets within the overflow region
        max_x = w - crop_w
        max_y = h - crop_h
        x = int(px * max_x)
        y = int(py * max_y)

        cropped = self.img_np[y:y + crop_h, x:x + crop_w]

        # Resize back to output size using PIL for quality
        pil = Image.fromarray(cropped).resize(
            (self.out_w, self.out_h), Image.LANCZOS
        )
        return np.array(pil)


def _cover_fit(img: Image.Image, out_w: int, out_h: int) -> Image.Image:
    """Resize + centre-crop image to fill out_w × out_h (cover mode)."""
    src_w, src_h = img.size
    scale = max(out_w / src_w, out_h / src_h)
    new_w = int(src_w * scale)
    new_h = int(src_h * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    x = (new_w - out_w) // 2
    y = (new_h - out_h) // 2
    return img.crop((x, y, x + out_w, y + out_h))


# ---------------------------------------------------------------------------
# Caption overlay for photos
# ---------------------------------------------------------------------------

def _make_caption_frame(
    text: str,
    out_w: int, out_h: int,
    t: float, duration: float,
    font_size: int = 48,
) -> np.ndarray:
    """Render a caption with fade-in/out onto a transparent layer."""
    from PIL import ImageDraw, ImageFont

    img = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))
    if not text:
        return np.array(img)

    # Fade: 0→0.5s in, duration-0.5→duration out
    fade_in = min(1.0, t / 0.5)
    fade_out = max(0.0, min(1.0, (duration - t) / 0.5))
    alpha = int(fade_in * fade_out * 220)
    if alpha <= 0:
        return np.array(img)

    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    font = None
    for fp in font_paths:
        try:
            font = ImageFont.truetype(fp, font_size)
            break
        except (IOError, OSError):
            continue
    if font is None:
        font = ImageFont.load_default()

    draw = ImageDraw.Draw(img)

    # Word wrap
    words = text.split()
    lines = []
    current = []
    for word in words:
        test = " ".join(current + [word])
        bbox = font.getbbox(test)
        if bbox[2] > int(out_w * 0.88) and current:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))

    line_h = font_size + 12
    total_h = len(lines) * line_h + 24
    block_y = out_h - 180 - total_h   # above safe area

    # Background pill
    bg = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))
    bg_draw = ImageDraw.Draw(bg)
    pad = 16
    bg_draw.rounded_rectangle(
        [int(out_w * 0.04), block_y - pad,
         int(out_w * 0.96), block_y + total_h + pad],
        radius=14,
        fill=(0, 0, 0, int(alpha * 0.6)),
    )
    img = Image.alpha_composite(img, bg)
    draw = ImageDraw.Draw(img)

    # Text lines
    primary_hex = BRAND["colors"]["primary"].lstrip("#")
    pr, pg, pb = int(primary_hex[0:2], 16), int(primary_hex[2:4], 16), int(primary_hex[4:6], 16)

    y = block_y
    for i, line in enumerate(lines):
        bbox = font.getbbox(line)
        lw = bbox[2] - bbox[0]
        x = (out_w - lw) // 2
        stroke = 3
        for dx in range(-stroke, stroke + 1):
            for dy in range(-stroke, stroke + 1):
                if dx == 0 and dy == 0:
                    continue
                draw.text((x + dx, y + dy), line, font=font,
                          fill=(0, 0, 0, alpha))
        # First line in brand gold, rest in white
        color = (pr, pg, pb, alpha) if i == 0 else (255, 255, 255, alpha)
        draw.text((x, y), line, font=font, fill=color)
        y += line_h

    return np.array(img)


# ---------------------------------------------------------------------------
# Photo slideshow builder
# ---------------------------------------------------------------------------

class PhotoVideoBuilder:
    def __init__(self, platform: str = "instagram_reel"):
        from config import PLATFORMS
        if platform not in PLATFORMS:
            raise ValueError(f"Unknown platform: {platform}")
        self.platform = platform
        self.spec = PLATFORMS[platform]
        self.out_w = self.spec["width"]
        self.out_h = self.spec["height"]
        self.is_short = platform in SHORT_FORM_PLATFORMS
        self.photo_dur = SHORT_FORM_PHOTO_DURATION if self.is_short else LONG_FORM_PHOTO_DURATION

    def build(
        self,
        photo_paths: List[str],
        captions: Optional[List[str]] = None,
        music_path: Optional[str] = None,
        website: Optional[str] = None,
        base_name: str = "prime_land",
    ):
        """
        Build a full slideshow video from a list of image paths.
        Returns a moviepy VideoClip.
        """
        from moviepy.editor import (
            VideoClip, CompositeVideoClip, concatenate_videoclips, AudioFileClip
        )
        from caption_renderer import WatermarkRenderer
        from music_mixer import mix_music

        if not captions:
            captions = [""] * len(photo_paths)
        # Pad captions if needed
        while len(captions) < len(photo_paths):
            captions.append("")

        clips = []
        for idx, (photo_path, caption) in enumerate(zip(photo_paths, captions)):
            img = Image.open(photo_path)
            kb = KenBurnsClip(img, self.out_w, self.out_h,
                              self.photo_dur, move_index=idx)

            cap_text = caption  # capture for closure

            def make_frame(t, _kb=kb, _cap=cap_text):
                base = _kb.get_frame(t)
                cap_layer = _make_caption_frame(
                    _cap, self.out_w, self.out_h, t, _kb.duration
                )
                # Blend caption (RGBA) over base (RGB)
                base_pil = Image.fromarray(base)
                cap_pil = Image.fromarray(cap_layer, "RGBA")
                base_pil.paste(cap_pil, (0, 0), cap_pil)
                return np.array(base_pil)

            clip = VideoClip(make_frame, duration=self.photo_dur)
            clip = clip.set_fps(self.spec["fps"])
            clips.append(clip)

        # Concatenate with cross-fade
        final = concatenate_videoclips(
            clips, method="compose", padding=-TRANSITION_DURATION
        )

        # Brand watermark intro
        wm = WatermarkRenderer(self.out_w, self.out_h)
        final = CompositeVideoClip([final, wm.make_intro_card(2.5)])

        # CTA end card
        if website:
            cta_dur = 3.0
            start = max(0.0, final.duration - cta_dur)
            cta = wm.make_cta_card(website, cta_dur).set_start(start)
            final = CompositeVideoClip([final, cta])

        # Enforce max duration
        max_dur = self.spec["max_duration"]
        if final.duration > max_dur:
            final = final.subclip(0, max_dur)

        # Background music (no voice, so can be a bit louder)
        if music_path or True:
            from music_mixer import _resolve_music
            resolved = _resolve_music(music_path)
            if resolved:
                from moviepy.editor import AudioFileClip
                from moviepy.audio.fx.all import audio_fadein, audio_fadeout, volumex
                music = AudioFileClip(resolved)
                if music.duration < final.duration:
                    from moviepy.editor import concatenate_audioclips
                    loops = int(final.duration / music.duration) + 1
                    music = concatenate_audioclips([music] * loops)
                music = music.subclip(0, final.duration)
                music = volumex(music, 0.30)   # 30% — no voice to compete with
                music = audio_fadein(music, 1.5)
                music = audio_fadeout(music, 2.0)
                final = final.set_audio(music)

        return final
