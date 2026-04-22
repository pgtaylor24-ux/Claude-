"""
Prime Land Solutions LLC — Photo-to-Video Agent
Uses Claude Vision to describe each job-site photo, then builds
a polished slideshow video for every social platform.

Usage:
    python photo_agent.py input/photo1.jpg input/photo2.jpg ... [options]
    python photo_agent.py input/*.jpg --topic "gravel driveway" --platforms instagram_reel tiktok
"""

from __future__ import annotations
import argparse
import base64
import json
import os
import sys
from pathlib import Path
from typing import List, Optional

import anthropic

sys.path.insert(0, str(Path(__file__).parent))

from config import BRAND, PLATFORMS
from photo_to_video import PhotoVideoBuilder
from exporter import Exporter
from music_mixer import _resolve_music


# ---------------------------------------------------------------------------
# Vision: Claude describes each photo
# ---------------------------------------------------------------------------

def _encode_image(path: str) -> tuple[str, str]:
    """Return (base64_data, media_type) for an image file."""
    ext = Path(path).suffix.lower()
    media_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                 ".png": "image/png", ".webp": "image/webp"}
    media_type = media_map.get(ext, "image/jpeg")
    with open(path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode("utf-8")
    return data, media_type


def describe_photos(
    client: anthropic.Anthropic,
    photo_paths: List[str],
    topic: str = "",
) -> List[str]:
    """
    Send all photos to Claude Vision in one call.
    Returns a caption string per photo — short, punchy, social-media ready.
    """
    print(f"[PhotoAgent] Generating captions for {len(photo_paths)} photos...")

    content = []
    for i, path in enumerate(photo_paths):
        data, media_type = _encode_image(path)
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": data},
        })
        content.append({
            "type": "text",
            "text": f"Photo {i + 1} of {len(photo_paths)} — see above.",
        })

    topic_line = f"The job is: {topic}." if topic else ""
    content.append({
        "type": "text",
        "text": f"""These are real job-site photos for Prime Land Solutions LLC, \
a professional dirtwork, drainage, and land clearing company.
{topic_line}

For EACH photo (numbered 1 to {len(photo_paths)}), write ONE short, punchy caption \
that would work as a social media text overlay. Rules:
- 5 to 10 words max
- Use active, confident language ("We cleared it." / "Gravel done right.")
- Relevant to what's actually shown in the photo
- No hashtags (those go in the post description, not the video)
- Match the brand voice: hardworking, Southern blue-collar, professional

Return ONLY a JSON array of {len(photo_paths)} strings, one per photo, in order.
Example: ["Caption for photo 1", "Caption for photo 2", ...]""",
    })

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[{"role": "user", "content": content}],
    )

    raw = response.content[0].text.strip()
    # Extract JSON array from the response
    start = raw.find("[")
    end = raw.rfind("]") + 1
    if start >= 0 and end > start:
        captions = json.loads(raw[start:end])
    else:
        # Fallback — split by newline
        captions = [line.strip().strip('"') for line in raw.split("\n") if line.strip()]

    # Ensure we have one caption per photo
    while len(captions) < len(photo_paths):
        captions.append(f"Prime Land Solutions LLC — Built right.")
    return captions[:len(photo_paths)]


def choose_cta_for_topic(topic: str) -> str:
    topic_l = topic.lower()
    if "drain" in topic_l:
        return BRAND["websites"]["drainage"]
    elif "clear" in topic_l or "tree" in topic_l or "brush" in topic_l:
        return BRAND["websites"]["land_clearing"]
    else:
        return BRAND["websites"]["dirtwork"]


# ---------------------------------------------------------------------------
# Main agent loop
# ---------------------------------------------------------------------------

class PhotoVideoAgent:
    def __init__(self, api_key: Optional[str] = None):
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set.")
        self.client = anthropic.Anthropic(api_key=api_key)

    def run(
        self,
        photo_paths: List[str],
        platforms: List[str],
        topic: str = "",
        music_path: Optional[str] = None,
        output_dir: str = "output",
        base_name: str = "prime_land",
    ) -> dict:
        # 1. Generate captions via Claude Vision
        captions = describe_photos(self.client, photo_paths, topic)
        print("\n[PhotoAgent] Captions:")
        for i, (path, cap) in enumerate(zip(photo_paths, captions)):
            print(f"  Photo {i+1} ({Path(path).name}): {cap}")

        # 2. Choose CTA website
        website = choose_cta_for_topic(topic)
        print(f"\n[PhotoAgent] CTA website: {website}")

        # 3. Resolve music
        resolved_music = _resolve_music(music_path)
        if resolved_music:
            print(f"[PhotoAgent] Music: {resolved_music}")
        else:
            print("[PhotoAgent] No music file found in assets/music/ — exporting without music.")
            print("  Tip: Drop a .mp3 or .wav into video_agent/assets/music/")

        # 4. Build and export for each platform
        exporter = Exporter(output_dir=output_dir)
        results = {}

        for platform in platforms:
            print(f"\n[PhotoAgent] Building for: {PLATFORMS[platform]['label']}")
            builder = PhotoVideoBuilder(platform=platform)
            clip = builder.build(
                photo_paths=photo_paths,
                captions=captions,
                music_path=resolved_music,
                website=website,
                base_name=base_name,
            )
            out_path = exporter.export(clip, platform, base_name)
            results[platform] = {"status": "success", "path": out_path,
                                  "label": PLATFORMS[platform]["label"]}
            clip.close()

        return {
            "captions": captions,
            "website_cta": website,
            "music": resolved_music,
            "outputs": results,
        }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Prime Land Solutions LLC — Photo to Video Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("photos", nargs="+",
                        help="One or more photo files (.jpg, .png, .webp)")
    parser.add_argument("--platforms", nargs="+",
                        choices=list(PLATFORMS.keys()),
                        default=["instagram_reel", "tiktok", "facebook_reel", "youtube_short"],
                        help="Platforms to export for")
    parser.add_argument("--topic", default="",
                        help="What the job is about (e.g. 'gravel driveway', 'drainage')")
    parser.add_argument("--music", default=None,
                        help="Path to background music file")
    parser.add_argument("--name", default="prime_land",
                        help="Base filename for output files")
    parser.add_argument("--output-dir", default="output",
                        help="Output directory")
    parser.add_argument("--api-key", default=None,
                        help="Anthropic API key (falls back to ANTHROPIC_API_KEY env var)")
    args = parser.parse_args()

    # Validate photos
    valid_photos = []
    for p in args.photos:
        if os.path.isfile(p):
            valid_photos.append(p)
        else:
            print(f"WARNING: File not found, skipping: {p}")

    if not valid_photos:
        print("ERROR: No valid photo files found.")
        sys.exit(1)

    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  Prime Land Solutions LLC — Photo to Video Agent")
    print("=" * 60)
    print(f"  Photos:    {len(valid_photos)} files")
    print(f"  Topic:     {args.topic or '(auto-detect from photos)'}")
    print(f"  Platforms: {', '.join(args.platforms)}")
    print(f"  Output:    {args.output_dir}/")
    print("=" * 60)

    try:
        agent = PhotoVideoAgent(api_key=args.api_key)
    except ValueError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    result = agent.run(
        photo_paths=valid_photos,
        platforms=args.platforms,
        topic=args.topic,
        music_path=args.music,
        output_dir=args.output_dir,
        base_name=args.name,
    )

    print("\n" + "=" * 60)
    print("DONE — Output files:")
    for platform, info in result["outputs"].items():
        status = info["status"]
        if status == "success":
            print(f"  {info['label']:25s} → {info['path']}")
        else:
            print(f"  {info['label']:25s} → ERROR: {info.get('error')}")
    print(f"\nCaptions used:")
    for i, cap in enumerate(result["captions"], 1):
        print(f"  {i}. {cap}")
    print(f"\nCTA website: {result['website_cta']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
