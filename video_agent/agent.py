"""
Prime Land Solutions LLC — Video Editing Agent
Powered by Claude claude-sonnet-4-6 with tool use.

The agent:
  1. Accepts raw video files + optional metadata
  2. Uses Claude to decide clip selections, captions, CTAs, and music choices
  3. Calls the video processing pipeline
  4. Exports platform-specific files
"""

from __future__ import annotations
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

import anthropic

from config import BRAND, PLATFORMS, SHORT_FORM_PLATFORMS, LONG_FORM_PLATFORMS
from transcriber import Transcriber, mock_transcript, WHISPER_AVAILABLE
from video_processor import VideoProcessor
from exporter import Exporter

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "get_video_info",
        "description": (
            "Get metadata about a video file: duration, resolution, fps, "
            "has_audio. Call this first before any editing decisions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "video_path": {
                    "type": "string",
                    "description": "Absolute or relative path to the video file.",
                }
            },
            "required": ["video_path"],
        },
    },
    {
        "name": "transcribe_video",
        "description": (
            "Transcribe the spoken audio in a video file and return a transcript "
            "with word-level timestamps. Use this to generate captions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "video_path": {"type": "string"},
                "language": {
                    "type": "string",
                    "description": "ISO language code (e.g. 'en'). Omit to auto-detect.",
                },
            },
            "required": ["video_path"],
        },
    },
    {
        "name": "select_clips",
        "description": (
            "Given a video path and transcript, decide which time segments to include "
            "in the final edit. Returns a list of {start, end, reason} dicts. "
            "For short-form content keep total ≤ 60s; for YouTube keep the best content."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "video_path": {"type": "string"},
                "transcript_text": {
                    "type": "string",
                    "description": "Full transcript text from transcribe_video.",
                },
                "video_duration": {"type": "number"},
                "target_platform": {
                    "type": "string",
                    "enum": list(PLATFORMS.keys()),
                },
                "content_topic": {
                    "type": "string",
                    "description": (
                        "What the video is about "
                        "(e.g. 'drainage installation', 'land clearing timelapse')."
                    ),
                },
            },
            "required": ["video_path", "transcript_text", "video_duration",
                         "target_platform"],
        },
    },
    {
        "name": "generate_captions",
        "description": (
            "Generate styled caption text for a clip. Returns caption segments "
            "ready for the caption renderer."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "transcript_text": {"type": "string"},
                "platform": {
                    "type": "string",
                    "enum": list(PLATFORMS.keys()),
                },
                "style": {
                    "type": "string",
                    "enum": ["bold_bottom", "center_pop"],
                    "description": (
                        "bold_bottom: typical TikTok/Reel style at the bottom. "
                        "center_pop: centred big-text style."
                    ),
                },
            },
            "required": ["transcript_text", "platform"],
        },
    },
    {
        "name": "choose_music",
        "description": (
            "Choose the best background music style for a dirtwork / construction "
            "content video. Returns a music style recommendation and, if available, "
            "the path to a music file."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content_topic": {"type": "string"},
                "platform": {
                    "type": "string",
                    "enum": list(PLATFORMS.keys()),
                },
                "mood": {
                    "type": "string",
                    "description": "e.g. 'energetic', 'epic', 'chill', 'motivational'",
                },
            },
            "required": ["content_topic", "platform"],
        },
    },
    {
        "name": "choose_cta",
        "description": (
            "Choose the best website CTA URL for the content topic. "
            "Returns one of the Prime Land Solutions LLC website URLs."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content_topic": {
                    "type": "string",
                    "description": "What the video is about.",
                },
            },
            "required": ["content_topic"],
        },
    },
    {
        "name": "render_video",
        "description": (
            "Run the full video rendering pipeline and export files. "
            "Call this after all decisions have been made."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "video_path": {"type": "string"},
                "clip_selections": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "start": {"type": "number"},
                            "end": {"type": "number"},
                        },
                        "required": ["start", "end"],
                    },
                    "description": "List of {start, end} clip segments to include.",
                },
                "platforms": {
                    "type": "array",
                    "items": {"type": "string", "enum": list(PLATFORMS.keys())},
                    "description": "Which platforms to export for.",
                },
                "caption_style": {
                    "type": "string",
                    "enum": ["bold_bottom", "center_pop"],
                    "default": "bold_bottom",
                },
                "music_path": {
                    "type": "string",
                    "description": "Path to background music file. Optional.",
                },
                "website": {
                    "type": "string",
                    "description": "CTA website URL for end card.",
                },
                "base_name": {
                    "type": "string",
                    "description": "Base filename for output files.",
                    "default": "prime_land",
                },
                "use_ducking": {
                    "type": "boolean",
                    "description": "Use speech-aware music ducking. Default true.",
                    "default": True,
                },
            },
            "required": ["video_path", "clip_selections", "platforms"],
        },
    },
]

# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def _get_video_info(video_path: str) -> dict:
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", "-show_format", video_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return {"error": f"ffprobe failed: {result.stderr}"}

    data = json.loads(result.stdout)
    info: dict[str, Any] = {"path": video_path}

    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            info["width"] = stream.get("width")
            info["height"] = stream.get("height")
            info["fps"] = eval(stream.get("r_frame_rate", "30/1"))
            info["duration"] = float(stream.get("duration", 0))
        elif stream.get("codec_type") == "audio":
            info["has_audio"] = True
            info["audio_codec"] = stream.get("codec_name")

    fmt = data.get("format", {})
    if "duration" not in info:
        info["duration"] = float(fmt.get("duration", 0))
    info.setdefault("has_audio", False)
    return info


def _transcribe(video_path: str, language: Optional[str] = None) -> dict:
    if not WHISPER_AVAILABLE:
        print("[Agent] faster-whisper not available — using mock transcript")
        from transcriber import mock_transcript
        info = _get_video_info(video_path)
        dur = info.get("duration", 60.0)
        t = mock_transcript(dur)
        return {
            "full_text": t.full_text,
            "language": t.language,
            "segments": [
                {
                    "text": s.text,
                    "start": s.start,
                    "end": s.end,
                    "words": [{"text": w.text, "start": w.start, "end": w.end}
                              for w in s.words],
                }
                for s in t.segments
            ],
        }

    tr = Transcriber(model_size="base")
    transcript = tr.extract_audio_and_transcribe(video_path)
    return {
        "full_text": transcript.full_text,
        "language": transcript.language,
        "segments": [
            {
                "text": s.text,
                "start": s.start,
                "end": s.end,
                "words": [{"text": w.text, "start": w.start, "end": w.end}
                          for w in s.words],
            }
            for s in transcript.segments
        ],
    }


def _select_clips(video_path: str, transcript_text: str, video_duration: float,
                  target_platform: str, content_topic: str = "") -> dict:
    """
    Claude itself decides clips via the outer agentic loop.
    This tool just validates and returns a default full-clip selection.
    The agent overrides this via the tool call arguments.
    """
    max_dur = PLATFORMS[target_platform]["max_duration"]
    end = min(video_duration, max_dur)
    return {
        "selections": [{"start": 0.0, "end": end, "reason": "Full clip"}],
        "total_duration": end,
    }


def _generate_captions(transcript_text: str, platform: str,
                       style: str = "bold_bottom") -> dict:
    return {
        "style": style,
        "platform": platform,
        "transcript": transcript_text,
        "note": "Captions will be word-highlighted using the transcript timestamps.",
    }


def _choose_music(content_topic: str, platform: str, mood: str = "energetic") -> dict:
    music_dir = Path(__file__).parent / "assets" / "music"
    available = (
        list(music_dir.glob("*.mp3")) + list(music_dir.glob("*.wav"))
    )
    recs = {
        "drainage": "upbeat hip-hop or trap beat — shows precision and expertise",
        "land clearing": "epic orchestral or aggressive rock — shows raw power",
        "dirtwork": "motivational hip-hop — shows hustle and hard work",
        "default": "energetic country rap or Southern hip-hop — relatable to the trade",
    }
    topic_lower = content_topic.lower()
    for k, v in recs.items():
        if k in topic_lower:
            recommendation = v
            break
    else:
        recommendation = recs["default"]

    return {
        "recommendation": recommendation,
        "mood": mood,
        "volume_ratio": 0.15,
        "note": (
            "Music sits at 15% volume — never overpowers the speaker. "
            "During speech gaps music rises slightly to 30%."
        ),
        "available_files": [str(p) for p in available],
        "music_path": str(available[0]) if available else None,
    }


def _choose_cta(content_topic: str) -> dict:
    topic_lower = content_topic.lower()
    websites = BRAND["websites"]
    if "drainage" in topic_lower or "drain" in topic_lower:
        url = websites["drainage"]
    elif "clearing" in topic_lower or "trees" in topic_lower or "brush" in topic_lower:
        url = websites["land_clearing"]
    else:
        url = websites["dirtwork"]
    return {"website": url, "content_topic": content_topic}


def _render_video(
    video_path: str,
    clip_selections: list,
    platforms: list,
    caption_style: str = "bold_bottom",
    music_path: Optional[str] = None,
    website: Optional[str] = None,
    base_name: str = "prime_land",
    use_ducking: bool = True,
    _transcript_cache: Optional[dict] = None,
) -> dict:
    from transcriber import Transcript, Segment, Word

    print(f"\n[Agent] Rendering: {video_path}")
    print(f"[Agent] Platforms: {platforms}")
    print(f"[Agent] Clips: {clip_selections}")

    # Rebuild transcript from cache if available
    transcript = None
    if _transcript_cache:
        segs = []
        for s in _transcript_cache.get("segments", []):
            words = [Word(w["text"], w["start"], w["end"])
                     for w in s.get("words", [])]
            segs.append(Segment(s["text"], s["start"], s["end"], words))
        transcript = Transcript(
            segments=segs,
            language=_transcript_cache.get("language", "en"),
            full_text=_transcript_cache.get("full_text", ""),
        )

    input_clips = [(video_path, sel["start"], sel["end"])
                   for sel in clip_selections]

    exporter = Exporter(output_dir=str(Path("output")))
    outputs = {}

    for platform in platforms:
        print(f"\n[Agent] Processing for: {platform}")
        proc = VideoProcessor(platform=platform, caption_style=caption_style)

        try:
            final_clip = proc.process(
                input_clips=input_clips,
                transcript=transcript,
                music_path=music_path,
                website=website,
                use_ducking=use_ducking and transcript is not None,
            )
            out_path = exporter.export(final_clip, platform, base_name)
            outputs[platform] = {"status": "success", "path": out_path}
            final_clip.close()
        except Exception as e:
            print(f"[Agent] ERROR on {platform}: {e}")
            outputs[platform] = {"status": "error", "error": str(e)}

    return {"outputs": outputs}


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

class VideoEditingAgent:
    """
    Agentic loop that uses Claude to orchestrate the full editing pipeline.
    """

    def __init__(self, api_key: Optional[str] = None):
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable not set. "
                "Export it before running the agent."
            )
        self.client = anthropic.Anthropic(api_key=api_key)
        self._transcript_cache: Optional[dict] = None

    def _system_prompt(self) -> str:
        return f"""You are an expert social media video editor for {BRAND['company']}, \
a professional dirtwork, land clearing, and drainage company.

Your job:
1. Analyse raw job-site footage
2. Select the most engaging, high-energy clips
3. Add bold word-highlighted captions
4. Pick background music that energises the viewer WITHOUT overpowering the speaker
5. Export optimised videos for each platform

Content strategy:
- Short-form (Instagram Reel, TikTok, Facebook Reel, YouTube Short): hook in the \
first 2 seconds, show the most dramatic transformation/action, end with a clear CTA
- YouTube (long-form): full documentation of the job, professional narration, SEO-rich

Brand voice: Confident, hardworking, Southern blue-collar. "We get it done right."

Business websites:
- Drainage work → {BRAND['websites']['drainage']}
- Land clearing → {BRAND['websites']['land_clearing']}
- Dirt work / general → {BRAND['websites']['dirtwork']}

Always:
- Keep music at ≤15% volume during speech (ducking handled automatically)
- Use bold_bottom caption style for TikTok/Instagram, bold_bottom or center_pop for YouTube
- Add the matching website as the end-card CTA
- Export short-form first, then YouTube separately at full resolution
"""

    def run(self, user_request: str, max_iterations: int = 20) -> str:
        """Run the agentic loop for a user editing request."""
        messages = [{"role": "user", "content": user_request}]
        print(f"\n[Agent] Starting: {user_request}\n")

        for iteration in range(max_iterations):
            response = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=self._system_prompt(),
                tools=TOOLS,
                messages=messages,
            )

            # Collect text output
            text_parts = []
            tool_uses = []
            for block in response.content:
                if hasattr(block, "text"):
                    text_parts.append(block.text)
                    if block.text:
                        print(f"[Claude] {block.text}")
                elif block.type == "tool_use":
                    tool_uses.append(block)

            # Append assistant message
            messages.append({"role": "assistant", "content": response.content})

            # If no tool calls, we're done
            if response.stop_reason == "end_turn" or not tool_uses:
                return "\n".join(text_parts)

            # Execute tools and collect results
            tool_results = []
            for tool_use in tool_uses:
                result = self._dispatch_tool(tool_use.name, tool_use.input)
                print(f"[Tool:{tool_use.name}] → {json.dumps(result, indent=2)[:400]}")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": json.dumps(result),
                })

            messages.append({"role": "user", "content": tool_results})

        return "Agent reached max iterations."

    def _dispatch_tool(self, name: str, inputs: dict) -> dict:
        if name == "get_video_info":
            return _get_video_info(inputs["video_path"])

        if name == "transcribe_video":
            result = _transcribe(
                inputs["video_path"],
                inputs.get("language"),
            )
            self._transcript_cache = result
            return result

        if name == "select_clips":
            return _select_clips(
                inputs["video_path"],
                inputs.get("transcript_text", ""),
                inputs["video_duration"],
                inputs["target_platform"],
                inputs.get("content_topic", ""),
            )

        if name == "generate_captions":
            return _generate_captions(
                inputs["transcript_text"],
                inputs["platform"],
                inputs.get("style", "bold_bottom"),
            )

        if name == "choose_music":
            return _choose_music(
                inputs["content_topic"],
                inputs["platform"],
                inputs.get("mood", "energetic"),
            )

        if name == "choose_cta":
            return _choose_cta(inputs["content_topic"])

        if name == "render_video":
            return _render_video(
                video_path=inputs["video_path"],
                clip_selections=inputs["clip_selections"],
                platforms=inputs["platforms"],
                caption_style=inputs.get("caption_style", "bold_bottom"),
                music_path=inputs.get("music_path"),
                website=inputs.get("website"),
                base_name=inputs.get("base_name", "prime_land"),
                use_ducking=inputs.get("use_ducking", True),
                _transcript_cache=self._transcript_cache,
            )

        return {"error": f"Unknown tool: {name}"}
