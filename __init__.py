# -*- coding: utf-8 -*-
"""
YouTube 频道文字脚本采集器
"""

from collector import (
    collect,
    get_video_info,
    get_available_formats,
    download_video,
    download_youtube_subtitles,
    extract_audio,
    transcribe,
)
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
    # 核心采集
    "collect",
    "get_video_info",
    "get_available_formats",
    "download_video",
    "download_youtube_subtitles",
    "extract_audio",
    "transcribe",
    # 工具
    "detect_youtube_browser",
    # 配置
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
