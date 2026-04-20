# Prime Land Solutions LLC — AI Video Editing Agent

An AI-powered video editing agent built with Claude claude-sonnet-4-6.  
Automatically edits job-site footage into polished, platform-ready social media content for:

- **Instagram Reels** (1080×1920, ≤90s)
- **TikTok** (1080×1920, ≤3min)
- **Facebook Reels + Feed** (1080×1920 and 1080×1080)
- **YouTube** (1920×1080, full length — for monetization)
- **YouTube Shorts** (1080×1920, ≤60s)

---

## Features

| Feature | Details |
|---|---|
| Smart clip selection | Claude picks the most engaging segments |
| Word-highlighted captions | Karaoke-style, auto-generated from speech |
| Background music | Sits at 15% volume; ducks under speech |
| Speech ducking | Music rises in gaps, quiet during talking |
| Brand watermark | Prime Land Solutions intro card |
| CTA end card | Auto-selects the right website per topic |
| Multi-platform export | One command, all platforms |

**Websites auto-matched to content:**
- Drainage → `drainage.primelandsolutionsllc.com`
- Land Clearing → `landclearing.primelandsolutionsllc.com`
- Dirt Work → `dirtwork.primelandsolutionsllc.com`

---

## Quick Start

### 1. Install
```bash
cd video_agent
bash setup.sh
source .venv/bin/activate
```

### 2. Set API Key
```bash
export ANTHROPIC_API_KEY="your-anthropic-api-key"
```
Get a key at https://console.anthropic.com

### 3. Add Your Videos
Drop your raw footage into the `video_agent/input/` folder.

### 4. (Optional) Add Background Music
Drop `.mp3` or `.wav` files into `video_agent/assets/music/`.  
The agent auto-picks one if you don't specify.

### 5. Run
```bash
# All platforms (Instagram, TikTok, Facebook, YouTube)
python main.py input/job_site.mp4 --topic "drainage installation"

# Short-form only
python main.py input/job_site.mp4 \
  --platforms instagram_reel tiktok facebook_reel \
  --topic "land clearing"

# YouTube only (for monetization)
python main.py input/walkthrough.mp4 \
  --platforms youtube \
  --topic "dirtwork"

# Custom music
python main.py input/job_site.mp4 \
  --music assets/music/my_beat.mp3 \
  --topic "drainage"

# Custom output name
python main.py input/job_site.mp4 \
  --name prime_land_june2026 \
  --topic "land clearing"
```

Output files appear in `video_agent/output/`:
```
output/
  prime_land_instagram_reel.mp4
  prime_land_tiktok.mp4
  prime_land_facebook_reel.mp4
  prime_land_youtube.mp4
```

---

## Project Layout
```
video_agent/
├── main.py              # CLI entrypoint
├── agent.py             # Claude agent orchestrator + tool loop
├── video_processor.py   # Clip, crop, composite
├── caption_renderer.py  # Word-highlighted captions (Pillow)
├── music_mixer.py       # Background music + ducking
├── exporter.py          # Platform-specific FFmpeg export
├── transcriber.py       # Speech-to-text (faster-whisper)
├── config.py            # Platform specs + brand config
├── requirements.txt
├── setup.sh
├── input/               # Drop your raw videos here
├── output/              # Exported platform videos
└── assets/
    ├── music/           # Background music files (.mp3/.wav)
    └── fonts/           # Custom fonts (optional)
```

---

## Platform Specs

| Platform | Resolution | Max Duration | Best For |
|---|---|---|---|
| `instagram_reel` | 1080×1920 | 90s | Short hooks, transformations |
| `tiktok` | 1080×1920 | 3min | Process videos, how-to content |
| `facebook_reel` | 1080×1920 | 90s | Local community reach |
| `facebook_feed` | 1080×1080 | 4min | Standard posts |
| `youtube` | 1920×1080 | 60min | Full job documentation (monetization) |
| `youtube_short` | 1080×1920 | 60s | YouTube discovery |

---

## Content Strategy Tips

**Short-form (TikTok / Reels):**
- Hook the viewer in the first 2 seconds — show something dramatic
- Show the before/after or the biggest machine moment
- Keep energy high — the music keeps it moving
- End card: website URL

**YouTube (Monetization):**
- Full job walkthrough — problem → process → result
- Talk about the what, why, and how (builds trust)
- Add chapters in the description
- Upload consistently (2× per week minimum to grow the channel)

---

## System Requirements

- Python 3.10+
- ffmpeg (installed by `setup.sh`)
- 4 GB RAM minimum (8 GB recommended for Whisper)
- Anthropic API key
