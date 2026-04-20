"""
Platform-specific video export.
Writes final clips to disk with correct codecs, bitrates, and file names.
"""

from __future__ import annotations
import os
from pathlib import Path
from typing import Optional

from config import PLATFORMS


class Exporter:
    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(
        self,
        clip,
        platform: str,
        base_name: str = "prime_land",
        threads: int = 4,
    ) -> str:
        """
        Write the clip to disk in the correct format for the given platform.
        Returns the output file path.
        """
        if platform not in PLATFORMS:
            raise ValueError(f"Unknown platform: {platform}")

        spec = PLATFORMS[platform]
        ext = spec["format"]
        filename = f"{base_name}_{platform}.{ext}"
        out_path = str(self.output_dir / filename)

        ffmpeg_params = [
            "-crf", "18",          # high quality
            "-preset", "slow",     # better compression
            "-movflags", "+faststart",   # streaming-friendly
        ]

        print(f"[Exporter] Writing {spec['label']} → {out_path}")

        clip.write_videofile(
            out_path,
            fps=spec["fps"],
            codec="libx264",
            audio_codec="aac",
            bitrate=spec["bitrate"],
            audio_bitrate=spec["audio_bitrate"],
            threads=threads,
            ffmpeg_params=ffmpeg_params,
            verbose=False,
            logger=None,
        )

        size_mb = os.path.getsize(out_path) / (1024 * 1024)
        print(f"[Exporter] Done: {out_path} ({size_mb:.1f} MB)")
        return out_path

    def export_all_short_form(self, clip, base_name: str = "prime_land") -> dict:
        """Export the same clip for Instagram Reel, TikTok, and Facebook Reel."""
        results = {}
        for platform in ("instagram_reel", "tiktok", "facebook_reel"):
            results[platform] = self.export(clip, platform, base_name)
        return results

    def export_youtube(self, clip, base_name: str = "prime_land",
                       short: bool = False) -> str:
        platform = "youtube_short" if short else "youtube"
        return self.export(clip, platform, base_name)
