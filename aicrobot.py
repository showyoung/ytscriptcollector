#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 模式 CLI
输出 JSON，适合 AI 工具调用。
"""
from __future__ import annotations

import os
import sys
import json
import argparse
from pathlib import Path

from collector import collect
from config import (
    defaults as config_defaults,
    resolve_output_dir,
    supported_browsers,
    audio_formats,
)
from utils import resolve_quality
from utils import str2bool
import yt_dlp


def main() -> None:
    cfg = config_defaults()
    parser = argparse.ArgumentParser(description="YouTube 采集器（AI 模式）")
    parser.add_argument("url", help="YouTube 链接")
    parser.add_argument("-o", "--output", dest="output_dir",
                        default=cfg.get("output_dir"),
                        help=f"输出目录（默认: {cfg.get('output_dir')}）")
    parser.add_argument("-q", "--quality", default=cfg.get("quality"),
                        help=f"画质（默认: {cfg.get('quality')}）")
    parser.add_argument("--whisper-model", default=cfg.get("whisper_model"),
                        help=f"Whisper 模型（默认: {cfg.get('whisper_model')}）")
    parser.add_argument("--whisper-language", default=cfg.get("whisper_language"),
                        help=f"Whisper 语言（默认: {cfg.get('whisper_language')}）")
    parser.add_argument("--srt",
                        nargs="?", const="true", default=None, choices=["true","false"],
                        help=f"生成 .srt 字幕（默认: {cfg.get('srt')}）")
    parser.add_argument("--md",
                        nargs="?", const="true", default=None, choices=["true","false"],
                        help=f"生成 .md 文本（默认: {cfg.get('md')}）")
    parser.add_argument("--media-type",
                        default=cfg.get("media_type"),
                        choices=["video", "audio"],
                        help=f"视频或音频模式（默认: {cfg.get('media_type')}）")
    parser.add_argument("--audio-format",
                        default=cfg.get("audio_format"),
                        choices=audio_formats(),
                        help=f"音频格式（默认: {cfg.get('audio_format')}）")
    parser.add_argument("--separate-audio",
                        nargs="?", const="true", default=None, choices=["true","false"],
                        help=f"分离音频文件（默认: {cfg.get('separate_audio')}）")
    parser.add_argument("--code-convert",
                        nargs="?", const="true", default=None, choices=["true","false"],
                        help=f"视频转码（默认: {cfg.get('code_convert')}）")
    parser.add_argument("--cookies",
                        default=cfg.get("cookies_method"),
                        choices=supported_browsers() + ["auto"],
                        help=f"浏览器（默认: {cfg.get('cookies_method')}）")

    args = parser.parse_args()

    # 转换 bool 参数
    audio_only        = (args.media_type == "audio")
    generate_subtitle = str2bool(args.srt, cfg.get("srt"))
    generate_md       = str2bool(args.md,   cfg.get("md"))
    separate_audio    = str2bool(args.separate_audio, cfg.get("separate_audio"))
    do_hevc           = str2bool(args.code_convert,   cfg.get("code_convert"))

    # 修正 output_dir：config 中 "~" 代表软件目录下的 downloads/，
    # argparse 的 default 会把 "~" 展开成主目录，需纠正回来
    user_home = Path(os.path.expanduser("~"))
    if args.output_dir and Path(args.output_dir).expanduser() == user_home:
        output_dir = str(resolve_output_dir("~"))
    else:
        output_dir = args.output_dir or str(resolve_output_dir(cfg.get("output_dir")))

    # ------------------------------------------------------------------
    # 解析画质（可能视频没有请求的画质，需要上下寻找）
    # ------------------------------------------------------------------
    resolved_quality, _ = resolve_quality(args.quality, args.url, args.cookies)

    # ------------------------------------------------------------------
    # 调用 collect()，成功后构建新 JSON 格式，写入 result.json
    # ------------------------------------------------------------------
    result = None
    try:
        result = collect(
            url=args.url,
            output_dir=output_dir,
            quality=resolved_quality,
            audio_only=audio_only,
            generate_subtitle=generate_subtitle,
            generate_md=generate_md,
            whisper_model=args.whisper_model,
            whisper_language=args.whisper_language,
            cookies_method=args.cookies,
            extract_audio_separate=separate_audio,
            audio_format=args.audio_format,
            hevc=do_hevc,
            subtitle_source="auto",
            verbose=False,
        )

        # 构建成功 JSON
        result_json = {
            "success": True,
            "url": result.get("url"),
            "quality": result.get("quality"),
            "media_type": "audio" if audio_only else "video",
            "code_convert": do_hevc,
            "title": result.get("title"),
            "channel": result.get("channel"),
            "duration": result.get("duration"),
            "upload_date": result.get("upload_date"),
            "downloaded_file": result.get("downloaded_file"),
            "transcript": result.get("transcript", {}),
        }

        # 写入视频子目录的 result.json
        if result.get("downloaded_file"):
            video_dir = Path(result["downloaded_file"]).parent
            result_path = video_dir / "result.json"
            result_path.write_text(json.dumps(result_json, ensure_ascii=False, indent=2))

        print(json.dumps(result_json, ensure_ascii=False, indent=2))

    except yt_dlp.utils.ExtractorError as e:
        err = {
            "success": False,
            "error": {
                "type": "ExtractorError",
                "message": f"提取失败: {e}",
                "url": args.url,
            },
        }
        _print_and_write_error(output_dir, err, result, err_url=args.url)
        sys.exit(1)
    except yt_dlp.utils.DownloadError as e:
        err = {
            "success": False,
            "error": {
                "type": "DownloadError",
                "message": f"下载失败: {e}",
                "url": args.url,
                "title": result.get("title") if result else None,
            },
        }
        _print_and_write_error(output_dir, err, result)
        sys.exit(1)
    except RuntimeError as e:
        if "无法获取视频信息" in str(e):
            err = {
                "success": False,
                "error": {
                    "type": "ExtractorError",
                    "message": str(e),
                    "url": args.url,
                },
            }
        else:
            err = {
                "success": False,
                "error": {
                    "type": "DownloadError",
                    "message": str(e),
                    "url": args.url,
                    "title": result.get("title") if result else None,
                },
            }
        _print_and_write_error(output_dir, err, result, err_url=err["error"].get("url"))
        sys.exit(1)
    except Exception as e:
        # TranscriptionError 或其他未预期错误
        # 尝试从异常信息判断是否是转录相关错误
        err_type = "TranscriptionError" if any(
            kw in str(e).lower() for kw in ["whisper", "transcribe", "ffmpeg", "audio"]
        ) else "UnexpectedError"
        err = {
            "success": False,
            "error": {
                "type": err_type,
                "message": str(e),
                "url": args.url if err_type != "UnexpectedError" else None,
                "downloaded_file": result.get("downloaded_file") if result else None,
            },
        }
        _print_and_write_error(output_dir, err, result)
        sys.exit(1)


def _print_and_write_error(output_dir: str, err: dict, result: dict | None, err_url: str | None = None) -> None:
    """
    打印错误 JSON 并写入 result.json。
    - 有 downloaded_file：从路径提取目录
    - 无 downloaded_file（ExtractorError）：从 err_url 提取 video_id 创建目录
    """
    if result and result.get("downloaded_file"):
        video_dir = Path(result["downloaded_file"]).parent
    else:
        # ExtractorError：没有下载文件，从 err_url 提取 video_id 创建目录
        url = err_url or (result.get("url") if result else None)
        if url:
            video_id = url.split("v=")[-1].split("&")[0]
            video_dir = Path(output_dir) / video_id
            video_dir.mkdir(parents=True, exist_ok=True)
        else:
            print(json.dumps(err, ensure_ascii=False, indent=2), file=sys.stderr)
            return
    result_path = video_dir / "result.json"
    result_path.write_text(json.dumps(err, ensure_ascii=False, indent=2))
    print(json.dumps(err, ensure_ascii=False, indent=2), file=sys.stderr)


if __name__ == "__main__":
    main()
