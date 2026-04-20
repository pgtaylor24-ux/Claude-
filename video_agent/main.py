#!/usr/bin/env python3
"""
Prime Land Solutions LLC — Video Editing Agent CLI
Usage:
    python main.py <video_file> [options]

Examples:
    # Edit a clip for all short-form platforms + YouTube
    python main.py input/job_site.mp4 --topic "drainage installation"

    # Only TikTok and Instagram
    python main.py input/job_site.mp4 --platforms tiktok instagram_reel --topic "land clearing"

    # YouTube long-form only
    python main.py input/walkthrough.mp4 --platforms youtube --topic "dirtwork"

    # With custom background music
    python main.py input/job_site.mp4 --music assets/music/beat.mp3 --topic "land clearing"
"""

import argparse
import os
import sys
from pathlib import Path

# Ensure the video_agent package is on the path
sys.path.insert(0, str(Path(__file__).parent))

from agent import VideoEditingAgent
from config import PLATFORMS


def build_request(args: argparse.Namespace) -> str:
    """Build a natural-language editing request for the agent."""
    platforms_str = ", ".join(args.platforms)
    music_str = f"Use the music file at {args.music}." if args.music else \
        "Pick the best available background music."
    topic = args.topic or "dirtwork / construction job site footage"

    request = f"""
Please edit this video for Prime Land Solutions LLC:

Video file: {args.video}
Content topic: {topic}
Target platforms: {platforms_str}
{music_str}

Steps to complete:
1. Get the video info (duration, resolution, etc.)
2. Transcribe the audio for word-level captions
3. For each platform group:
   a. Select the best clips (hook at start, best action, CTA at end)
   b. Choose the right caption style
   c. Choose the right CTA website based on the content topic
4. Render and export the video for: {platforms_str}
5. Report the output file paths when done.

Output base filename: {args.name}
""".strip()

    return request


def main():
    parser = argparse.ArgumentParser(
        description="Prime Land Solutions LLC — AI Video Editing Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("video", help="Path to the input video file")
    parser.add_argument(
        "--platforms", nargs="+",
        choices=list(PLATFORMS.keys()),
        default=["instagram_reel", "tiktok", "facebook_reel", "youtube"],
        help="Platforms to export for (default: all)",
    )
    parser.add_argument(
        "--topic", default="",
        help="What the video is about (e.g. 'drainage installation', 'land clearing')",
    )
    parser.add_argument(
        "--music", default=None,
        help="Path to background music file (mp3/wav). Auto-selects if omitted.",
    )
    parser.add_argument(
        "--name", default="prime_land",
        help="Base filename for output files (default: prime_land)",
    )
    parser.add_argument(
        "--output-dir", default="output",
        help="Output directory (default: ./output)",
    )
    parser.add_argument(
        "--api-key", default=None,
        help="Anthropic API key (falls back to ANTHROPIC_API_KEY env var)",
    )
    parser.add_argument(
        "--caption-style",
        choices=["bold_bottom", "center_pop"],
        default="bold_bottom",
        help="Caption overlay style",
    )

    args = parser.parse_args()

    # Validate input file
    if not os.path.isfile(args.video):
        print(f"ERROR: Video file not found: {args.video}")
        sys.exit(1)

    # Set output dir env for exporter
    os.environ["VIDEO_OUTPUT_DIR"] = args.output_dir
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    # Build and run the agent
    try:
        agent = VideoEditingAgent(api_key=args.api_key)
    except ValueError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    request = build_request(args)
    print("=" * 60)
    print("  Prime Land Solutions LLC — Video Editing Agent")
    print("=" * 60)
    print(f"  Input:     {args.video}")
    print(f"  Platforms: {', '.join(args.platforms)}")
    print(f"  Topic:     {args.topic or '(auto-detect)'}")
    print(f"  Output:    {args.output_dir}/")
    print("=" * 60)

    result = agent.run(request)

    print("\n" + "=" * 60)
    print("AGENT COMPLETE")
    print("=" * 60)
    print(result)
    print(f"\nOutputs saved to: {args.output_dir}/")


if __name__ == "__main__":
    main()
