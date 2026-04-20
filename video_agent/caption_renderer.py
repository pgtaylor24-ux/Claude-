"""
Renders animated word-by-word captions onto video clips.
Uses PIL/Pillow to draw styled text frames, then overlays via moviepy.
"""

from __future__ import annotations
import textwrap
from typing import List, Tuple, Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from config import BRAND, CAPTION_STYLES
from transcriber import Transcript, Word


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for fp in font_paths:
        try:
            return ImageFont.truetype(fp, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


def _hex_to_rgba(hex_color: str, alpha: int = 255) -> Tuple[int, int, int, int]:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (r, g, b, alpha)


def _wrap_words(words: List[str], font: ImageFont.FreeTypeFont,
                max_width: int, max_words: int = 7) -> List[List[str]]:
    """Split word list into lines that fit within max_width."""
    lines: List[List[str]] = []
    current: List[str] = []
    for word in words[:max_words]:
        test = " ".join(current + [word])
        bbox = font.getbbox(test)
        if bbox[2] > max_width and current:
            lines.append(current)
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(current)
    return lines


class CaptionRenderer:
    """
    Creates a moviepy ImageClip overlay with animated captions.
    Words highlight one at a time as they're spoken.
    """

    def __init__(self, video_width: int, video_height: int,
                 style_name: str = "bold_bottom"):
        self.w = video_width
        self.h = video_height
        self.style = CAPTION_STYLES[style_name]
        self.font_size = BRAND["font_size_caption"]
        self.font = _load_font(self.font_size)
        self.small_font = _load_font(int(self.font_size * 0.75))

    def _make_frame(self, t: float, transcript: Transcript) -> np.ndarray:
        img = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Find words visible at time t (current segment window)
        segments = transcript.segments_in_range(t - 0.05, t + 3.0)
        if not segments:
            return np.array(img)

        # Collect words for the current "caption window" (~5 words ahead)
        all_words: List[Word] = []
        for seg in segments:
            all_words.extend(seg.words)

        # Show words from the most recent spoken word up to 6 words ahead
        visible_words: List[Word] = []
        start_idx = 0
        for i, w in enumerate(all_words):
            if w.start <= t:
                start_idx = i
        window_start = max(0, start_idx - 1)
        visible_words = all_words[window_start: window_start + 7]

        if not visible_words:
            return np.array(img)

        word_texts = [w.text for w in visible_words]
        lines = _wrap_words(word_texts, self.font, int(self.w * 0.85))

        # Measure total text block height
        line_height = self.font_size + 10
        total_h = len(lines) * line_height + 20  # padding

        # Compute block position
        if self.style["position"] == "bottom":
            block_y = self.h - self.style["margin_bottom"] - total_h
        else:
            block_y = (self.h - total_h) // 2

        # Draw semi-transparent background pill
        if self.style["bg_opacity"] > 0:
            alpha = int(self.style["bg_opacity"] * 255)
            bg_img = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
            bg_draw = ImageDraw.Draw(bg_img)
            pad = 20
            bg_draw.rounded_rectangle(
                [int(self.w * 0.05), block_y - pad,
                 int(self.w * 0.95), block_y + total_h + pad],
                radius=18,
                fill=(0, 0, 0, alpha),
            )
            img = Image.alpha_composite(img, bg_img)
            draw = ImageDraw.Draw(img)

        # Draw each line
        word_idx = 0
        for line in lines:
            line_text = " ".join(line)
            bbox = self.font.getbbox(line_text)
            line_w = bbox[2] - bbox[0]
            x = (self.w - line_w) // 2
            y = block_y

            # Draw each word in the line individually for highlighting
            cx = x
            for word_text in line:
                w_obj = visible_words[word_idx] if word_idx < len(visible_words) else None
                is_current = (w_obj is not None and w_obj.start <= t <= w_obj.end)
                word_idx += 1

                color = (
                    _hex_to_rgba(self.style["highlight_color"])
                    if (is_current and self.style["word_highlight"])
                    else _hex_to_rgba(self.style["text_color"])
                )

                # Stroke / shadow
                stroke_c = _hex_to_rgba(self.style["stroke_color"])
                sw = self.style["stroke_width"]
                for dx in range(-sw, sw + 1):
                    for dy in range(-sw, sw + 1):
                        if dx == 0 and dy == 0:
                            continue
                        draw.text((cx + dx, y + dy), word_text,
                                  font=self.font, fill=stroke_c)

                draw.text((cx, y), word_text, font=self.font, fill=color)
                w_bbox = self.font.getbbox(word_text + " ")
                cx += w_bbox[2] - w_bbox[0]

            block_y += line_height

        return np.array(img)

    def make_clip(self, transcript: Transcript, duration: float):
        """Return a moviepy VideoClip with captions overlay."""
        from moviepy.editor import VideoClip

        def make_frame(t: float) -> np.ndarray:
            frame = self._make_frame(t, transcript)
            return frame[:, :, :3]  # RGB for moviepy

        def make_mask_frame(t: float) -> np.ndarray:
            frame = self._make_frame(t, transcript)
            return frame[:, :, 3] / 255.0  # Alpha channel as mask

        clip = VideoClip(make_frame, duration=duration)
        clip = clip.set_mask(VideoClip(make_mask_frame, ismask=True, duration=duration))
        return clip


class WatermarkRenderer:
    """Renders brand watermark / CTA overlay."""

    def __init__(self, video_width: int, video_height: int):
        self.w = video_width
        self.h = video_height
        self.font = _load_font(BRAND["font_size_watermark"])
        self.cta_font = _load_font(BRAND["font_size_cta"])

    def make_intro_card(self, duration: float = 2.5):
        """Semi-transparent intro card with company name."""
        from moviepy.editor import VideoClip

        text = BRAND["company"].upper()

        def make_frame(t: float) -> np.ndarray:
            img = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            fade = min(1.0, t / 0.4) * max(0.0, 1.0 - max(0.0, t - 2.0) / 0.5)
            alpha = int(fade * 230)
            bg = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
            bg_draw = ImageDraw.Draw(bg)
            bg_draw.rectangle([0, int(self.h * 0.38), self.w, int(self.h * 0.62)],
                               fill=(0, 0, 0, alpha))
            img = Image.alpha_composite(img, bg)
            draw = ImageDraw.Draw(img)
            bbox = self.cta_font.getbbox(text)
            tw = bbox[2] - bbox[0]
            x = (self.w - tw) // 2
            y = int(self.h * 0.44)
            draw.text((x, y), text, font=self.cta_font,
                      fill=_hex_to_rgba(BRAND["colors"]["primary"], alpha))
            return np.array(img)[:, :, :3]

        def make_mask(t: float) -> np.ndarray:
            fade = min(1.0, t / 0.4) * max(0.0, 1.0 - max(0.0, t - 2.0) / 0.5)
            return np.full((self.h, self.w), fade, dtype=float)

        from moviepy.editor import VideoClip
        clip = VideoClip(make_frame, duration=duration)
        clip = clip.set_mask(VideoClip(make_mask, ismask=True, duration=duration))
        return clip

    def make_cta_card(self, website: str, duration: float = 3.0):
        """End card with website CTA."""
        from moviepy.editor import VideoClip

        line1 = "VISIT US ONLINE"
        line2 = website

        def make_frame(t: float) -> np.ndarray:
            img = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
            bg = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
            bg_draw = ImageDraw.Draw(bg)
            fade = min(1.0, t / 0.5)
            alpha = int(fade * 210)
            bg_draw.rectangle([0, int(self.h * 0.35), self.w, int(self.h * 0.65)],
                               fill=(26, 26, 26, alpha))
            img = Image.alpha_composite(img, bg)
            draw = ImageDraw.Draw(img)
            f1 = _load_font(BRAND["font_size_watermark"])
            f2 = _load_font(BRAND["font_size_cta"])
            b1 = f1.getbbox(line1)
            b2 = f2.getbbox(line2)
            draw.text(((self.w - (b1[2] - b1[0])) // 2, int(self.h * 0.40)),
                      line1, font=f1, fill=_hex_to_rgba("#FFFFFF", alpha))
            draw.text(((self.w - (b2[2] - b2[0])) // 2, int(self.h * 0.48)),
                      line2, font=f2, fill=_hex_to_rgba(BRAND["colors"]["primary"], alpha))
            return np.array(img)[:, :, :3]

        def make_mask(t: float) -> np.ndarray:
            fade = min(1.0, t / 0.5)
            return np.full((self.h, self.w), fade, dtype=float)

        clip = VideoClip(make_frame, duration=duration)
        clip = clip.set_mask(VideoClip(make_mask, ismask=True, duration=duration))
        return clip
