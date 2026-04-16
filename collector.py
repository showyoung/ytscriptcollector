# -*- coding: utf-8 -*-
"""
核心采集模块
提供 YouTube 视频下载、音频提取、文字转录的完整流程。
不依赖任何 UI 或 CLI 模块，纯粹的公共服务接口。
"""
from __future__ import annotations

import datetime
import os
import re
import subprocess
from pathlib import Path

import yt_dlp
import whisper

from config import quality_map as _quality_map
from utils import (
    detect_youtube_browser,
    get_ffmpeg,
    get_js_runtime,
    format_duration,
)
from config import resolve_output_dir, defaults as config_defaults, subtitle_languages


# ============================================================================
# 内部工具
# ============================================================================

def _build_ydl_opts(url: str, *, cookies_method: str) -> tuple[dict, str]:
    """
    构造 yt-dlp 通用选项，并返回 (opts_dict, js_runtime_path)。
    cookies_method 为 "auto" 时自动检测浏览器。
    """
    if cookies_method == "auto":
        cookies_method = detect_youtube_browser() or config_defaults().get("cookies_fallback")

    js_runtime = get_js_runtime()
    return {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "cookiesfrombrowser": (cookies_method, None),
        "js_runtimes": {"node": {"path": js_runtime}},
        "extractor_args": {"youtube": {"js_runtime": "node"}}
    }, js_runtime


def _resolve_audio_only(quality: str, audio_only: bool) -> tuple[str, bool]:
    """
    统一处理 quality / audio_only 参数。
    quality == "audio" 或 audio_only == True 都映射到 True。
    返回 (effective_quality, effective_audio_only)。
    """
    if quality == "audio" or audio_only:
        return "best", True
    return quality, False


def _parse_quality_height(quality: str) -> int:
    """从 quality 字符串（如 '720p', 'best'）解析目标高度。"""
    m = re.search(r'(\d+)p', quality, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return 0  # best/audio 不限


def _probe_codec(video_path: Path, ffmpeg: str) -> str:
    """用 ffprobe 获取视频编码名称，失败返回空字符串。"""
    for ff_cmd in ("ffprobe", ffmpeg):
        try:
            cmd = [ff_cmd, "-v", "error",
                   "-select_streams", "v:0",
                   "-show_entries", "stream=codec_name",
                   "-of", "csv=p=0", str(video_path)]
            probe = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if probe.returncode == 0 and probe.stdout.strip():
                return probe.stdout.strip().split("\n")[0].strip()
        except Exception:
            continue
    return ""


def _ensure_mp4(video_path: Path, hevc: bool, target_height: int) -> Path:
    """
    将视频转为 mp4 容器。
    - hevc=False：直接 remux，不改编码（速度快）。
    - hevc=True：target_height >= 1440 → H.265，以下 → H.264。
      target_height 由调用方根据用户选择的画质（或 best 时的 info['height']）传入。
    转换后删除原文件，返回 mp4 路径。
    """
    ffmpeg = get_ffmpeg()
    mp4_path = video_path.with_suffix(".mp4")

    if not hevc and video_path.suffix.lower() == ".mp4":
        return video_path

    if hevc and target_height > 0:
        use_hevc = target_height >= 1440
        if video_path.suffix.lower() == ".mp4":
            codec = _probe_codec(video_path, ffmpeg)
            if (use_hevc and codec == "hevc") or (not use_hevc and codec == "h264"):
                return video_path

    if hevc and target_height >= 1440:
        cmd = [ffmpeg, "-y", "-i", str(video_path),
               "-c:v", "libx265", "-preset", "fast",
               "-c:a", "aac", "-ar", "44100", "-ac", "2",
               str(mp4_path)]
    elif hevc:
        cmd = [ffmpeg, "-y", "-i", str(video_path),
               "-c:v", "libx264", "-preset", "fast",
               "-c:a", "aac", "-ar", "44100", "-ac", "2",
               str(mp4_path)]
    else:
        cmd = [ffmpeg, "-y", "-i", str(video_path),
               "-c", "copy", "-c:a", "aac", str(mp4_path)]

    result = subprocess.run(cmd, capture_output=True)
    if result.returncode == 0 and mp4_path.exists():
        try:
            os.remove(video_path)
        except OSError:
            pass
        return mp4_path
    return video_path


# ============================================================================
# 视频信息获取
# ============================================================================

def get_video_info(url: str, *, cookies_method: str) -> dict | None:
    """
    获取视频基本信息（不下载）。
    失败返回 None。
    """
    ydl_opts, _ = _build_ydl_opts(url, cookies_method=cookies_method)
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info:
                return {
                    "title":      info.get("title", ""),
                    "channel":    info.get("channel") or info.get("uploader", ""),
                    "duration":   info.get("duration") or 0,
                    "upload_date": info.get("upload_date", ""),
                }
    except Exception:
        pass
    return None


def get_available_formats(url: str, *, cookies_method: str) -> list[dict]:
    """
    获取视频可用画质列表。
    每项包含: itag, ext, resolution, height, vcodec, acodec, filesize。
    """
    ydl_opts, _ = _build_ydl_opts(url, cookies_method=cookies_method)
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return []
            result = []
            for f in info.get("formats", []):
                vcodec   = f.get("vcodec", "")
                acodec   = f.get("acodec", "")
                height   = f.get("height") or 0
                ext      = f.get("ext", "")
                fsize    = f.get("filesize") or f.get("filesize_approx") or 0
                filesize = f"{fsize / 1024 / 1024:.1f}M" if fsize else ""

                if vcodec == "none" and acodec != "none":
                    result.append({
                        "itag": f.get("format_id", ""),
                        "ext": ext,
                        "resolution": "audio",
                        "vcodec": vcodec,
                        "acodec": acodec,
                        "height": 0,
                        "filesize": filesize,
                    })
                elif height > 0 and vcodec != "none":
                    result.append({
                        "itag": f.get("format_id", ""),
                        "ext": ext,
                        "resolution": f"{height}p",
                        "vcodec": vcodec,
                        "acodec": acodec,
                        "height": height,
                        "filesize": filesize,
                    })
            return result
    except Exception:
        return []


# ============================================================================
# 视频 / 音频下载
# ============================================================================

def download_video(
    url: str,
    output_dir: str | Path,
    *,
    quality: str,
    audio_only: bool,
    audio_format: str,
    cookies_method: str,
    hevc: bool,
) -> tuple[Path, dict]:
    """
    下载 YouTube 视频或音频。
    返回 (下载文件 Path, yt-dlp info dict)。
    异常: RuntimeError
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    effective_quality, is_audio_only = _resolve_audio_only(quality, audio_only)
    ydl_opts, js_runtime = _build_ydl_opts(url, cookies_method=cookies_method)

    ydl_opts.update({
        "quiet":           False,
        "skip_download":    False,
        "outtmpl":         str(output_dir / "%(id)s") + "/%(title).30s.%(ext)s",
        "noplaylist":       True,
        "ffmpeg_location":  str(Path(get_ffmpeg()).parent),
    })

    if is_audio_only:
        ydl_opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": audio_format,
        }]
        ydl_opts["format"] = "bestaudio/best"
    else:
        ydl_opts["format"] = _quality_map().get(quality, "best")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                raise RuntimeError("下载失败: 未能获取视频信息")

            filename = ydl.prepare_filename(info)
            downloaded = Path(filename)

            if downloaded.exists():
                target_h = info.get("height") or _parse_quality_height(quality)
                downloaded = _ensure_mp4(downloaded, hevc=hevc, target_height=target_h)
                return downloaded, info

            if is_audio_only:
                for ext in (audio_format, "m4a", "ogg", "wav", "flac"):
                    candidate = downloaded.with_suffix(f".{ext}")
                    if candidate.exists():
                        return candidate, info

            files = [f for f in output_dir.glob("*")
                     if f.is_file() and f.stat().st_size > 0
                     and not f.name.endswith(".part")
                     and not f.name.endswith(".part frag")]
            if files:
                return max(files, key=lambda p: p.stat().st_mtime), info

            raise RuntimeError("下载失败: 未找到下载的文件")

    except yt_dlp.utils.DownloadError as e:
        raise RuntimeError(f"下载失败: {e}")


def download_youtube_subtitles(
    url: str,
    output_base: str | Path | None = None,
    *,
    cookies_method: str,
    languages: list[str] | None = None,
) -> dict[str, str]:
    """
    用 yt-dlp 下载 YouTube 字幕（所有可用语言），转为 .srt 文件。
    - output_base: 字幕文件基础名（不含扩展名），如 "/path/to/[id]/video title"
    返回 {"zh-Hans": "/path/to/zh-Hans.srt", "en": "/path/to/en.srt", ...}。
    下载失败或无可用字幕时返回空字典 {}。
    """
    ydl_opts, _ = _build_ydl_opts(url, cookies_method=cookies_method)

    lang_list = languages or subtitle_languages()
    if "all" in lang_list:
        lang_list = ["all"]  # yt-dlp 下载所有可用字幕

    ydl_opts.update({
        "quiet":              True,
        "skip_download":       True,
        "writesubtitles":     True,
        "writeautomaticsubs": True,
        "subtitleslangs":    lang_list,
        "subtitlesformat":   "srt",
        "outtmpl":           f"{output_base}.%(ext)s",
        "noplaylist":        True,
    })

    downloaded = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            out_base = Path(output_base)
            # 遍历目录找字幕文件（不用 glob，避免 [id] 被当作特殊字符）
            for srt in out_base.parent.iterdir():
                if not srt.is_file() or srt.suffix != ".srt":
                    continue
                # 文件名必须以 output_base 开头
                if not srt.name.startswith(out_base.name):
                    continue
                remaining = srt.stem[len(out_base.name):].lstrip(".")
                if remaining:
                    downloaded.append((remaining, str(srt)))
    except Exception:
        pass

    return dict(downloaded)


# ============================================================================
# 音频提取
# ============================================================================

def extract_audio(
    video_path: str | Path,
    audio_format: str,
    audio_path: str | Path | None = None,
) -> str:
    """
    从视频文件中提取高质量音频（44.1kHz 立体声，192kbps MP3 / 16bit WAV）。
    返回音频文件路径字符串。
    异常: RuntimeError
    """
    video_path = Path(video_path)
    audio_path = Path(audio_path) if audio_path else video_path.with_suffix(f".{audio_format}")

    ffmpeg = get_ffmpeg()
    if audio_format == "wav":
        cmd = [ffmpeg, "-y", "-i", str(video_path),
               "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
               str(audio_path)]
    else:
        cmd = [ffmpeg, "-y", "-i", str(video_path),
               "-vn", "-acodec", "libmp3lame", "-ar", "44100", "-ac", "2", "-b:a", "192k",
               str(audio_path)]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"音频提取失败: {result.stderr.decode('utf-8', errors='replace')[:200]}"
        )
    return str(audio_path)


# ============================================================================
# 文字转录 (Whisper)
# ============================================================================

def transcribe(
    audio_path: str | Path,
    output_base: str | Path,
    *,
    model_size: str,
    language: str,
    generate_subtitle: bool,
    generate_md: bool,
) -> dict:
    """
    用 OpenAI Whisper 将音频转写为文字。
    按需生成 .srt 字幕和/或 .md 文本。
    返回 {"srt": path, "md": path}（只含开启的项）。
    """
    model = whisper.load_model(model_size)
    result = model.transcribe(str(audio_path), language=language, fp16=False)
    result_dict = {}

    if generate_subtitle:
        srt_path = f"{output_base}.srt"
        with open(srt_path, "w", encoding="utf-8") as f:
            for i, seg in enumerate(result["segments"], 1):
                f.write(f"{i}\n")
                f.write(f"{_format_srt_time(seg['start'])} --> {_format_srt_time(seg['end'])}\n")
                f.write(f"{seg['text'].strip()}\n\n")
        result_dict["srt"] = srt_path

    if generate_md:
        md_path = f"{output_base}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(f"# {Path(audio_path).stem}\n\n")
            for seg in result["segments"]:
                f.write(f"{seg['text'].strip()} ")
        result_dict["md"] = md_path

    return result_dict


def _format_srt_time(seconds: float) -> str:
    """秒数 -> SRT 时间码 (HH:MM:SS,mmm)"""
    td = datetime.timedelta(seconds=seconds)
    h  = td.seconds // 3600
    m  = (td.seconds % 3600) // 60
    s  = td.seconds % 60
    ms = td.microseconds // 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _convert_srt_to_md(srt_paths: dict[str, str], md_path: str) -> None:
    """
    将多个 SRT 文件（不同语言）合并为一个 Markdown 文件。
    srt_paths: {语言标签: srt文件路径}
    """
    with open(md_path, "w", encoding="utf-8") as out:
        out.write(f"# {Path(md_path).stem}\n\n")
        for lang, srt_path in srt_paths.items():
            with open(srt_path, encoding="utf-8") as f:
                content = f.read()
            blocks = content.strip().split("\n\n")
            lines_out = []
            for block in blocks:
                parts = block.split("\n")
                if len(parts) >= 3:
                    lines_out.append(parts[2])
            text = " ".join(lines_out).strip()
            out.write(f"## {lang}\n\n{text}\n\n***\n\n")


# ============================================================================
# 完整采集流程
# ============================================================================

def collect(
    url: str,
    output_dir: str | Path | None = None,
    *,
    quality: str,
    audio_only: bool,
    generate_subtitle: bool,
    generate_md: bool,
    whisper_model: str,
    whisper_language: str,
    cookies_method: str,
    extract_audio_separate: bool,
    audio_format: str,
    hevc: bool,
    subtitle_source: str,
    verbose: bool,
) -> dict:
    """
    完整采集流程：获取信息 → 下载视频 → 字幕/转录。
    subtitle_source:
      - "youtube": 只用 YouTube 内置字幕（多语言全下）
      - "whisper": 只用 Whisper 转录
      - "auto"（默认）: 先尝试 YouTube 字幕，失败则用 Whisper
    返回 {"url", "output_dir", "quality", "audio_only", "hevc",
          "title", "channel", "duration"（已格式化，如 "2h 33m 0s"）,
          "downloaded_file", "transcript": {...}, "audio_file"}
    异常: RuntimeError
    """
    output_dir = Path(output_dir) if output_dir else resolve_output_dir(config_defaults().get("output_dir"))
    output_dir.mkdir(parents=True, exist_ok=True)

    def vprint(*args, **kwargs):
        if verbose:
            print(*args, **kwargs)

    effective_quality, is_audio = _resolve_audio_only(quality, audio_only)

    result_info: dict = {
        "url":        url,
        "output_dir": str(output_dir),
        "quality":    effective_quality,
        "audio_only": is_audio,
        "hevc":       hevc,
    }

    # 1/5: 获取视频信息
    vprint("\n[1/5] 获取视频信息...")
    info = get_video_info(url, cookies_method=cookies_method)
    if not info:
        raise RuntimeError("无法获取视频信息，请检查 URL 是否正确")
    result_info.update(info)
    result_info["duration"] = format_duration(info["duration"])
    vprint(f"   标题: {info['title']}")
    vprint(f"   时长: {result_info['duration']} | 频道: {info['channel']}")

    # 2/5: 下载
    codec_hint = "" if not hevc else " (转码中)"
    vprint(f"\n[2/5] 下载 {'音频' if is_audio else '视频'} ({effective_quality}){codec_hint}...")
    try:
        downloaded_file, video_info = download_video(
            url, output_dir,
            quality=effective_quality,
            audio_only=is_audio,
            audio_format=audio_format,
            cookies_method=cookies_method,
            hevc=hevc,
        )
        vprint(f"   已下载: {downloaded_file.name}")
        result_info["downloaded_file"] = str(downloaded_file)
    except Exception as e:
        raise RuntimeError(f"下载失败: {e}")

    # 3/5: 字幕 / 转录
    audio_path: str | None = None
    do_whisper = subtitle_source in ("whisper", "auto") and not is_audio and (generate_subtitle or generate_md)
    subtitle_result: dict = {}

    if is_audio:
        audio_path = str(downloaded_file)
    elif generate_subtitle or generate_md or extract_audio_separate:
        audio_path = extract_audio(str(downloaded_file), audio_format)
        vprint(f"   音频已提取: {Path(audio_path).name}")

    # output_base 在 YouTube 字幕和 Whisper 转录中都会用到，提前定义
    output_base = str(downloaded_file.with_suffix(""))
    if subtitle_source not in ("whisper", "none"):
        # 尝试下载 YouTube 字幕
        vprint(f"\n[3/5] 下载 YouTube 字幕...")
        youtube_subs = download_youtube_subtitles(
            url, output_base,
            cookies_method=cookies_method,
        )
        if youtube_subs:
            langs = list(youtube_subs.keys())
            vprint(f"   YouTube 字幕已下载 ({len(langs)} 个语言): {', '.join(langs)}")
            if generate_subtitle:
                subtitle_result = youtube_subs
                vprint(f"   字幕: {', '.join(f'{k}:{v}' for k, v in youtube_subs.items())}")
            if generate_md:
                md_path = f"{output_base}.md"
                _convert_srt_to_md(youtube_subs, md_path)
                subtitle_result["md"] = md_path
                vprint(f"   文本: {Path(md_path).name}")
            # generate_subtitle=False 且 generate_md=True 时，srt 仅用于生成 md，生成完清理
            if not generate_subtitle and generate_md:
                for srt_path in youtube_subs.values():
                    try:
                        Path(srt_path).unlink(missing_ok=True)
                        vprint(f"   已清理临时字幕: {Path(srt_path).name}")
                    except OSError:
                        pass
        elif do_whisper:
            do_whisper = True

    if subtitle_source != "none" and (subtitle_source == "whisper" or (subtitle_source == "auto" and not subtitle_result)):
        if subtitle_source == "auto" and not is_audio:
            vprint(f"   YouTube 字幕无，切换 Whisper...")
        if audio_path:
            vprint(f"\n[4/5] 转录中 (Whisper {whisper_model})...")
            whisper_result = transcribe(
                audio_path, output_base,
                model_size=whisper_model,
                language=whisper_language,
                generate_subtitle=generate_subtitle,
                generate_md=generate_md,
            )
            subtitle_result = whisper_result
            if generate_subtitle and whisper_result.get("srt"):
                vprint(f"   字幕: {Path(whisper_result['srt']).name}")
            if generate_md and whisper_result.get("md"):
                vprint(f"   文本: {Path(whisper_result['md']).name}")

    if subtitle_result:
        result_info["transcript"] = subtitle_result

    # 4/4: 完成
    vprint("\n[5/5] 完成")

    # 单独音频文件（仅在需要分离保存时记录）
    if extract_audio_separate and audio_path and audio_path != str(downloaded_file):
        result_info["audio_file"] = audio_path
        vprint(f"   音频文件: {Path(audio_path).name}")

    # 清理临时音频（extract_audio 产生的独立音频文件，不需要时删除）
    if not extract_audio_separate and audio_path and audio_path != str(downloaded_file):
        try:
            os.remove(audio_path)
            vprint(f"   已清理临时音频: {Path(audio_path).name}")
        except OSError:
            pass

    return result_info
