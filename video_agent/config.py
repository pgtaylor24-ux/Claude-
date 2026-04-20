"""
Platform configs and Prime Land Solutions LLC branding.
"""

BRAND = {
    "company": "Prime Land Solutions LLC",
    "tagline": "Built on the ground. Built right.",
    "websites": {
        "drainage": "drainage.primelandsolutionsllc.com",
        "land_clearing": "landclearing.primelandsolutionsllc.com",
        "dirtwork": "dirtwork.primelandsolutionsllc.com",
    },
    "colors": {
        "primary": "#D4890A",    # earthy gold / heavy equipment yellow
        "secondary": "#1A1A1A",  # near-black for contrast
        "accent": "#FFFFFF",     # white text
        "shadow": "#000000",
    },
    "font_size_caption": 52,
    "font_size_watermark": 28,
    "font_size_cta": 38,
}

# Per-platform export specs
PLATFORMS = {
    "instagram_reel": {
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "max_duration": 90,       # seconds
        "bitrate": "8000k",
        "audio_bitrate": "192k",
        "format": "mp4",
        "label": "Instagram Reel",
    },
    "tiktok": {
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "max_duration": 180,
        "bitrate": "8000k",
        "audio_bitrate": "192k",
        "format": "mp4",
        "label": "TikTok",
    },
    "facebook_reel": {
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "max_duration": 90,
        "bitrate": "8000k",
        "audio_bitrate": "192k",
        "format": "mp4",
        "label": "Facebook Reel",
    },
    "facebook_feed": {
        "width": 1080,
        "height": 1080,
        "fps": 30,
        "max_duration": 240,
        "bitrate": "6000k",
        "audio_bitrate": "192k",
        "format": "mp4",
        "label": "Facebook Feed",
    },
    "youtube": {
        "width": 1920,
        "height": 1080,
        "fps": 30,
        "max_duration": 3600,     # full length for monetization
        "bitrate": "12000k",
        "audio_bitrate": "320k",
        "format": "mp4",
        "label": "YouTube",
    },
    "youtube_short": {
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "max_duration": 60,
        "bitrate": "8000k",
        "audio_bitrate": "192k",
        "format": "mp4",
        "label": "YouTube Short",
    },
}

# Music volume ratio: background music relative to voice
MUSIC_VOICE_RATIO = 0.15   # 15% — audible but never overpowers speech

# Caption style presets
CAPTION_STYLES = {
    "bold_bottom": {
        "position": "bottom",
        "margin_bottom": 160,      # px from bottom (above safe area)
        "bg_opacity": 0.55,
        "word_highlight": True,    # highlight current word
        "highlight_color": "#D4890A",
        "text_color": "#FFFFFF",
        "stroke_color": "#000000",
        "stroke_width": 3,
    },
    "center_pop": {
        "position": "center",
        "margin_bottom": 0,
        "bg_opacity": 0.0,
        "word_highlight": True,
        "highlight_color": "#D4890A",
        "text_color": "#FFFFFF",
        "stroke_color": "#000000",
        "stroke_width": 4,
    },
}

SHORT_FORM_PLATFORMS = {"instagram_reel", "tiktok", "facebook_reel", "youtube_short"}
LONG_FORM_PLATFORMS = {"youtube", "facebook_feed"}
