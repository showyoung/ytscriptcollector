# -*- coding: utf-8 -*-
"""
配置管理
从 config.yaml 加载配置，缺失时回退到默认值。
用户可直接编辑 config.yaml 修改行为。
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml

# ============================================================================
# 默认值（config.yaml 不存在时使用）
# ============================================================================

_DEFAULTS = {
    "ytdlp_quality": {
        "audio":  "bestaudio/best",
        "144p":   "bestvideo[height<=144]+bestaudio/best[height<=144]/best",
        "240p":   "bestvideo[height<=240]+bestaudio/best[height<=240]/best",
        "360p":   "bestvideo[height<=360]+bestaudio/best[height<=360]/best",
        "480p":   "bestvideo[height<=480]+bestaudio/best[height<=480]/best",
        "720p":   "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
        "1080p":  "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
        "1440p":  "bestvideo[height<=1440]+bestaudio/best[height<=1440]/best",
        "2160p":  "bestvideo[height<=2160]+bestaudio/best[height<=2160]/best",
        "3840p":  "bestvideo[height<=3840]+bestaudio/best[height<=3840]/best",
        "4320p":  "bestvideo[height<=4320]+bestaudio/best[height<=4320]/best",
        "best":   "bestvideo+bestaudio/best",
    },
    "browsers": ["chrome", "firefox", "edge", "brave", "opera", "chromium"],
    "media_type": ["video", "audio"],
    "audio_format": ["mp3", "wav"],
    "whisper_model": ["tiny", "base", "small", "medium", "large"],
    "subtitle_languages": ["all", "zh", "en", "de", "ja", "fr", "ko", "es", "hi", "pt", "ar", "nb", "da", "sv", "nl", "ru", "vi", "id"],
    "defaults": {
        "media_type":      "video",
        "quality":         "360p",
        "code_convert":    False,
        "srt":             True,
        "md":              True,
        "whisper_model":   "tiny",
        "whisper_language": "zh",
        "separate_audio":   False,
        "audio_format":    "mp3",
        "cookies_method":  "auto",
        "cookies_fallback": "chrome",
        "output_dir":      "~",
    },
    "web_ui": {
        "port": 8765,
        "timeout_seconds": 3600,
    },
}

# ============================================================================
# 加载
# ============================================================================

_config: dict | None = None


def _load() -> dict:
    """加载 config.yaml，失败时使用默认配置"""
    global _config
    if _config is not None:
        return _config

    config_path = Path(__file__).parent / "config.yaml"
    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                raw = yaml.safe_load(f)
            # Deep merge with defaults
            _config = _deep_merge(_DEFAULTS.copy(), raw or {})
        except Exception:
            _config = _DEFAULTS
    else:
        _config = _DEFAULTS

    return _config


def _deep_merge(base: dict, overlay: dict) -> dict:
    """深度合并 overlay 到 base"""
    result = base.copy()
    for k, v in overlay.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


# ============================================================================
# 公开接口
# ============================================================================

def quality_map() -> dict[str, str]:
    """返回 yt-dlp 画质格式映射"""
    return _load()["ytdlp_quality"]


def qualities() -> list[str]:
    """返回可选的画质列表（YAML key: ytdlp_quality 的子键）"""
    return list(_load()["ytdlp_quality"].keys())


def supported_browsers() -> list[str]:
    """返回浏览器检测顺序"""
    return _load()["browsers"]


def whisper_models() -> list[str]:
    """返回可选的 Whisper 模型（YAML key: whisper_model）"""
    return _load()["whisper_model"]


def media_types() -> list[str]:
    """返回可选的媒体类型（YAML key: media_type）"""
    return _load()["media_type"]


def audio_formats() -> list[str]:
    """返回可选的音频格式（YAML key: audio_format）"""
    return _load()["audio_format"]


def subtitle_languages() -> list[str]:
    """
    返回 YouTube 字幕语言列表（YAML key: subtitle_languages）。
    若列表中包含字符串 "all"，代表下载所有可用字幕。
    """
    return _load()["subtitle_languages"]


def defaults() -> dict:
    """返回默认设置"""
    return _load()["defaults"]


def default_quality() -> str:
    return _load()["defaults"]["quality"]


def default_whisper_model() -> str:
    return _load()["defaults"]["whisper_model"]


def default_whisper_language() -> str:
    return _load()["defaults"]["whisper_language"]


def default_audio_format() -> str:
    return _load()["defaults"]["audio_format"]


def port() -> int:
    """返回 Web UI 端口"""
    return _load().get("web_ui", {}).get("port")


def timeout_seconds() -> int:
    """返回采集超时秒数"""
    return _load().get("web_ui", {}).get("timeout_seconds")


def resolve_output_dir(user_dir: str | None) -> Path:
    """
    解析输出目录。
    user_dir 为 None 或 "~" 时，返回软件目录下的 downloads/。
    """
    if not user_dir or user_dir == "~":
        return Path(__file__).parent / "downloads"
    return Path(user_dir).expanduser()
