# -*- coding: utf-8 -*-
"""
YouTube 频道文字脚本采集器
"""
from collector import collect, get_video_info, get_available_formats
from utils import detect_youtube_browser
from config import (
    quality_map,
    qualities,
    whisper_models,
    subtitle_languages,
    media_types,
    audio_formats,
    supported_browsers,
    defaults as config_defaults,
    resolve_output_dir,
)

__all__ = [
    "collect",
    "get_video_info",
    "get_available_formats",
    "detect_youtube_browser",
    "quality_map",
    "qualities",
    "whisper_models",
    "subtitle_languages",
    "media_types",
    "audio_formats",
    "supported_browsers",
    "config_defaults",
    "resolve_output_dir",
]
