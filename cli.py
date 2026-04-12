#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import argparse
import tempfile
import shutil
from pathlib import Path

from collector import (
    collect,
    get_video_info,
    get_available_formats,
    detect_youtube_browser,
    _resolve_audio_only,
    download_youtube_subtitles,
)
from utils import format_duration, str2bool, resolve_quality
from config import (
    defaults as config_defaults,
    resolve_output_dir,
    quality_map,
    supported_browsers,
    default_whisper_language,
    whisper_models as config_whisper_models,
    media_types,
    audio_formats,
    qualities,
)


# ============================================================================
# argparse（所有默认值从 config 读取）
# ============================================================================

def _cfg() -> dict:
    """读取当前配置（每次调用获取最新值）"""
    return config_defaults()



def parse_args():
    cfg = _cfg()
    parser = argparse.ArgumentParser(description="YouTube 视频采集工具")

    # 位置参数（交互模式可空，命令行模式必填）
    parser.add_argument("url", nargs="?", help="YouTube 链接")

    # --cookies 浏览器
    parser.add_argument("--cookies",
                        default=cfg.get("cookies_method"),
                        choices=supported_browsers() + ["auto"],
                        help=f"Cookie 来源浏览器（默认: {cfg.get('cookies_method')})")

    # 问题1：--media-type
    parser.add_argument("--media-type",
                        default=cfg.get("media_type"),
                        choices=media_types(),
                        help=f"视频或音频模式（默认: {cfg.get('media_type')})")

    # 问题2：--quality
    parser.add_argument("-q", "--quality",
                        default=cfg.get("quality"),
                        choices=qualities(),
                        help=f"画质（默认: {cfg.get('quality')})")

    # 问题3：--code-convert
    parser.add_argument("--code-convert",
                        nargs="?", const="true",
                        default=None,
                        choices=["true","false"],
                        help=f"是否转码（默认: {cfg.get('code_convert')}）")

    # 问题4：--srt
    parser.add_argument("--srt",
                        nargs="?", const="true",
                        default=None,
                        choices=["true","false"],
                        help=f"生成 .srt 字幕（默认: {cfg.get('srt')}）")

    # 问题5：--md
    parser.add_argument("--md",
                        nargs="?", const="true",
                        default=None,
                        choices=["true","false"],
                        help=f"生成 .md 文本（默认: {cfg.get('md')}）")

    # 问题6：--whisper-model
    parser.add_argument("--whisper-model",
                        default=cfg.get("whisper_model"),
                        choices=config_whisper_models(),
                        help=f"Whisper 精度（默认: {cfg.get('whisper_model')}）")

    # 问题7：--whisper-language
    parser.add_argument("--whisper-language",
                        default=cfg.get("whisper_language"),
                        help=f"Whisper 转录语言，ISO 639-1 代码，如: zh, en, ja （默认: {cfg.get('whisper_language')}）")

    # 问题8：--separate-audio
    parser.add_argument("--separate-audio",
                        nargs="?", const="true",
                        default=None,
                        choices=["true","false"],
                        help=f"分离音频文件（默认: {cfg.get('separate_audio')}）")

    # 问题9：--audio-format
    parser.add_argument("--audio-format",
                        default=cfg.get("audio_format"),
                        choices=audio_formats(),
                        help=f"音频格式（默认: {cfg.get('audio_format')}）")

    # 问题10：--output
    default_out = resolve_output_dir(cfg.get("output_dir")).resolve()
    parser.add_argument("-o", "--output", dest="output_dir",
                        default=cfg.get("output_dir"),
                        help=f"输出目录（默认: {default_out}）")

    return parser.parse_args()


# ============================================================================
# 交互问答（默认值从 config 读取）
# ============================================================================

def ask_mode() -> tuple[str, bool]:
    """问题 1：视频 or 音频"""
    cfg = _cfg()
    default = cfg.get("media_type")
    choice = input(f"1. 请问提取音频还是视频（1.视频，2.音频，默认{default}）: ").strip()
    if not choice:
        choice = default
    is_audio = (choice == "2")
    return ("音频", is_audio) if is_audio else ("视频", is_audio)


def ask_video_quality(url: str, cookies: str) -> tuple[str, str]:
    """
    问题 2：视频画质。
    动态获取视频支持的画质，显示实际可用的选项。
    """
    cfg = _cfg()
    default_q = cfg.get("quality")

    # 动态获取可用画质
    formats = get_available_formats(url, cookies_method=cookies)
    seen = set()
    available_heights = []
    for f in formats:
        h = f.get("height", 0)
        if h and h not in seen:
            seen.add(h)
            available_heights.append(h)
    available_heights.sort(reverse=True)

    if not available_heights:
        print("  ⚠️ 无法获取视频画质信息，仅提供最佳画质")

    # 把可用高度映射到最接近的 ytdlp_quality key
    qmap = quality_map()  # {height_str: format_string}
    quality_keys = [k for k in qmap.keys() if k != "audio"]

    def closest_quality(height: int) -> str:
        h_str = f"{height}p"
        if h_str in quality_keys:
            return h_str
        # 向下找
        for h in range(height - 1, 0, -1):
            if f"{h}p" in quality_keys:
                return f"{h}p"
        # 向下找不到，向上找
        for h in range(height + 1, 10000):
            if f"{h}p" in quality_keys:
                return f"{h}p"
        return "best"

    # 可用选项（去重，按高度从高到低），best 始终加在第一个
    raw_options = set(closest_quality(h) for h in available_heights)
    options = ["best"] + sorted(
        raw_options,
        key=lambda q: int(q.rstrip("p")) if q.rstrip("p").isdigit() else 0,
        reverse=True,
    )

    # 找到默认画质在选项中的位置
    labels_map = {q: (q if q != "best" else "最佳画质") for q in options}
    try:
        default_idx = options.index(default_q) + 1
    except ValueError:
        # config 默认不在可用选项里，选最接近的
        target_h = int(default_q.rstrip("p")) if default_q not in ("best", "audio") else 99999
        closest = min(
            options,
            key=lambda q: abs(int(q.rstrip("p")) - target_h) if q not in ("best", "audio") else 9999,
        )
        default_idx = options.index(closest) + 1

    max_h = available_heights[0] if available_heights else 0
    if max_h:
        print()
        print(f"2. 可选画质（视频最高可用 {max_h}p）:")
    else:
        print()
        print("2. 可选画质（无法获取视频信息）:")
    for i, q in enumerate(options, 1):
        marker = " ← 默认" if i == default_idx else ""
        print(f"  {i}. {labels_map[q]}{marker}")

    choices = {str(i): q for i, q in enumerate(options, 1)}
    choice = input(f"请选择 [1-{len(options)}] (直接回车默认 {default_idx}): ").strip() or str(default_idx)
    quality = choices.get(choice, options[default_idx - 1])
    return quality, labels_map.get(quality, quality)


def ask_transcode(is_audio: bool) -> bool:
    """问题 3：是否转码（仅视频）"""
    if is_audio:
        return False
    cfg = _cfg()
    default = "y" if cfg.get("code_convert") else "n"
    choice = input(f"3. 视频编码需要转换为 h.264（≤1080p）或 h.265（>1080p）么？[Y/n]（默认{default}）: ").strip().lower() or default
    return choice == "y"


def ask_subtitle() -> tuple[bool, bool]:
    """问题 4、5：srt 和 md（两个独立问题）"""
    cfg = _cfg()
    default_srt = "y" if cfg.get("srt") else "n"
    default_md  = "y" if cfg.get("md")  else "n"

    yn = input(f"4. 生成字幕(.srt)？[Y/n]（默认{default_srt.upper()}）: ").strip().lower() or default_srt
    generate_srt = (yn != "n")

    yn = input(f"5. 生成文本(.md)？[Y/n]（默认{default_md.upper()}）: ").strip().lower()
    if not yn:
        yn = default_md
    generate_md = (yn != "n")

    return generate_srt, generate_md


def ask_whisper_model() -> str:
    """问题 6：Whisper 精度"""
    cfg = _cfg()
    models = config_whisper_models()
    default = cfg.get("whisper_model")
    default_idx = models.index(default) + 1 if default in models else 1

    print("6. 使用什么 Whisper 精度（1-5，精度越高越准越慢，默认"
          + str(default_idx) + f"）:")
    choice = input("请选择: ").strip()
    if choice.isdigit() and 1 <= int(choice) <= len(models):
        return models[int(choice) - 1]
    return default


def ask_whisper_language() -> str:
    """问题 7：Whisper 转录语言"""
    cfg = _cfg()
    default = cfg.get("whisper_language")
    choice = input(f"7. 该视频是什么语言，用于 Whisper 语音转文字，默认 {default}）: ").strip()
    return choice if choice else default


def ask_separate_audio(is_audio: bool) -> bool:
    """问题 8：是否分离音频（仅视频；音频模式自动 True）"""
    if is_audio:
        return True
    cfg = _cfg()
    default = "y" if cfg.get("separate_audio") else "n"
    choice = input(f"8. 需要生成单独的音频文件么？[Y/n]（默认{default.upper()}）: ").strip().lower() or default
    return choice == "y"


def ask_audio_format(is_audio: bool, separate_audio: bool) -> str:
    """问题 9：音频格式"""
    if not is_audio and not separate_audio:
        return _cfg().get("audio_format")
    cfg = _cfg()
    default = cfg.get("audio_format")
    default_choice = "2" if default == "wav" else "1"
    choice = input(f"9. 音频文件使用什么格式存储（1.mp3，2.wav，默认{default_choice}）: ").strip() or default_choice
    return "wav" if choice == "2" else "mp3"


# ============================================================================
# 字幕来源判断（auto 模式：先探 YouTube，失败再问 Whisper）
# ============================================================================

def resolve_subtitle_source(
    generate_subtitle: bool,
    generate_md: bool,
    url: str,
    cookies: str,
    _whisper_model: str | None = None,
    _whisper_language: str | None = None,
) -> tuple[str, str, str, str]:
    """
    确定字幕来源。
    auto：优先 YouTube 字幕，没有则 Whisper。
    none：不生成字幕/文本。
    返回 (subtitle_source, subtitle_label, whisper_model, whisper_language)
    """
    # 不需要字幕/文本
    if not generate_subtitle and not generate_md:
        return "none", "无", "tiny", ""

    # auto：先探测 YouTube 字幕，没有则用 Whisper
    print()
    print("正在获取视频字幕...")
    probe_dir = tempfile.mkdtemp(prefix="ytsub_probe_")
    output_base = f"{probe_dir}/probe"
    try:
        subs = download_youtube_subtitles(url, output_base, cookies_method=cookies)
    finally:
        shutil.rmtree(probe_dir, ignore_errors=True)

    if subs:
        langs = ",".join(sorted(subs.keys()))
        return "youtube", f"YouTube 内置字幕（{langs}）", "tiny", ""

    # 没有 YouTube 字幕，用 Whisper
    model = _whisper_model if _whisper_model else ask_whisper_model()
    language = _whisper_language if _whisper_language else ask_whisper_language()
    return "whisper", f"Whisper {model}（{language}）", model, language


# ============================================================================
# 采集摘要
# ============================================================================

def print_summary(info: dict, mode_label: str, quality_label: str,
                  do_hevc: bool, generate_srt: bool, generate_md: bool,
                  subtitle_label: str, keep_audio: bool, audio_format: str,
                  output_dir: Path) -> None:
    """打印采集摘要"""
    if mode_label == "音频":
        transcode_label = "不适用"
    elif do_hevc:
        h = int(quality_label.rstrip("p")) if quality_label.rstrip("p").isdigit() else 0
        transcode_label = "H.265" if h >= 1440 else "H.264"
    else:
        transcode_label = "仅 remux mp4"

    if mode_label == "音频":
        parts = ["音频"]
        if generate_srt: parts.append("srt")
        if generate_md: parts.append("md")
        gen_label = " + ".join(parts) if parts else "音频"
    else:
        parts = ["视频"]
        if keep_audio: parts.append(f"分离音频{audio_format}")
        if generate_srt: parts.append("srt")
        if generate_md: parts.append("md")
        gen_label = " + ".join(parts)

    print()
    print("=" * 50)
    print("📋 采集摘要")
    print("=" * 50)
    print(f"  标题: {info.get('title', '未知')}")
    print(f"  频道: {info.get('channel', '未知')}")
    print(f"  时长: {format_duration(info.get('duration', 0))}")
    print(f"  提取: {mode_label}")
    if mode_label == "视频":
        print(f"  画质: {quality_label}")
        print(f"  转码: {transcode_label}")
    else:
        print(f"  格式: {audio_format.upper()}")
    print(f"  生成: {gen_label}")
    print(f"  字幕: {subtitle_label}")
    print(f"  输出: {output_dir}")
    print("=" * 50)


# ============================================================================
# 画质解析（命令行模式：找不到最接近的级别）
# ============================================================================


# ============================================================================
# 主函数
# ============================================================================

def main() -> None:
    args = parse_args()

    # ============================================================
    # 判断是否非交互模式：提供了 URL 或任意参数即为非交互
    # ============================================================
    url_provided = args.url is not None
    has_option = any(
        arg.startswith(("--", "-"))
        for arg in sys.argv[1:]
    )
    is_noninteractive = url_provided or has_option

    # ============================================================
    # URL 处理
    # ============================================================
    if not args.url:
        if is_noninteractive:
            # 提供了参数但没有 URL → 报错
            print("❌ URL 不能为空")
            sys.exit(1)
        # 交互模式：询问 URL
        args.url = input("请输入 YouTube 视频链接: ").strip()
        if not args.url:
            print("❌ 未提供链接")
            sys.exit(1)

    cookies = args.cookies
    if cookies == "auto":
        cookies = detect_youtube_browser() or config_defaults().get("cookies_fallback")

    print()
    print(f"🔍 正在获取视频信息: {args.url}")
    info = get_video_info(args.url, cookies_method=cookies)
    if not info:
        print("❌ 无法获取视频信息，请检查链接是否正确")
        sys.exit(1)

    print()
    print(f"✅ 获取成功!")
    print(f"  标题: {info['title']}")
    print(f"  频道: {info['channel']}")
    print(f"  时长: {format_duration(info['duration'])}")

    if is_noninteractive:
        cfg = _cfg()
        # 媒体类型
        media_type = args.media_type or cfg.get("media_type")
        is_audio = media_type == "audio"
        # 画质
        requested_quality = args.quality or cfg.get("quality")
        if is_audio:
            quality, quality_label = "audio", "音频"
        else:
            quality, quality_label = resolve_quality(requested_quality, args.url, cookies)
        mode_label = "音频" if is_audio else "视频"
        # 转码
        do_hevc = str2bool(args.code_convert, cfg.get("code_convert"))
        # 字幕/文本
        generate_subtitle = str2bool(args.srt, cfg.get("srt"))
        generate_md       = str2bool(args.md,   cfg.get("md"))
        # Whisper
        whisper_model = args.whisper_model or cfg.get("whisper_model")
        whisper_language = args.whisper_language or cfg.get("whisper_language")
        # 音频分离（音频模式自动 True）
        if is_audio:
            keep_audio = True
        else:
            keep_audio = str2bool(args.separate_audio, cfg.get("separate_audio"))
        # 音频格式
        audio_format = args.audio_format or cfg.get("audio_format")
        # 输出目录
        output_dir = resolve_output_dir(args.output_dir) if args.output_dir else resolve_output_dir(cfg.get("output_dir"))
        # 字幕来源（优先 YouTube，没有则 Whisper）
        subtitle_label = "auto"
        subtitle_source = "auto"
        if not is_audio and (generate_subtitle or generate_md):
            subtitle_source, subtitle_label, _wm, _wl = resolve_subtitle_source(
                generate_subtitle,
                generate_md,
                args.url,
                cookies,
                whisper_model,
                whisper_language,
            )

    else:
        # ============================================================
        # 交互模式（完整 8 问题流程）
        # ============================================================
        # 问题 1：视频 or 音频
        mode_label, is_audio = ask_mode()

        # 问题 2：画质（仅视频，动态获取可用画质）
        if not is_audio:
            quality, quality_label = ask_video_quality(args.url, cookies)
        else:
            quality, quality_label = "audio", "音频"

        # 问题 3：转码（仅视频）
        do_hevc = ask_transcode(is_audio)

        # 问题 4+5：srt 和 md（两个独立问题）
        generate_subtitle, generate_md = ask_subtitle()

        # 问题 6+7：字幕来源（auto 模式探测，失败则问 Whisper 精度）
        subtitle_source, subtitle_label, whisper_model, whisper_language = resolve_subtitle_source(
            generate_subtitle,
            generate_md,
            args.url,
            cookies,
        )

        # 问题 8：分离音频（仅视频）
        keep_audio = ask_separate_audio(is_audio)

        # 问题 9：音频格式
        audio_format = ask_audio_format(is_audio, keep_audio)

        # 问题 10：输出目录
        cfg = _cfg()
        default_dir = resolve_output_dir(cfg.get("output_dir"))
        output_dir_input = input(f"10. 输出目录（输入只支持绝对目录，默认使用 [{default_dir}]）: ").strip()
        output_dir = resolve_output_dir(output_dir_input) if output_dir_input else default_dir

    # 确认并执行
    print_summary(info, mode_label, quality_label, do_hevc,
                  generate_subtitle, generate_md, subtitle_label,
                  keep_audio, audio_format, output_dir)

    # 交互模式：必须确认
    if not is_noninteractive:
        ok = input("确认开始采集? [Y/n]: ").strip().lower()
        if ok and ok != "y":
            print("已取消")
            return

    print()
    try:
        result = collect(
            url=args.url,
            output_dir=str(output_dir),
            quality=quality,
            audio_only=is_audio,
            generate_subtitle=generate_subtitle,
            generate_md=generate_md,
            whisper_model=whisper_model,
            whisper_language=whisper_language,
            cookies_method=cookies,
            extract_audio_separate=keep_audio,
            audio_format=audio_format,
            hevc=do_hevc,
            subtitle_source=subtitle_source,
            verbose=True,
        )
        print()
        print("=" * 50)
        print("✅ 采集完成!")
        print("=" * 50)
        downloaded = result.get("downloaded_file", "")
        audio_file = result.get("audio_file", "")
        transcript = result.get("transcript", {})
        if downloaded:
            print(f"🎬 视频: {downloaded}")
        if audio_file:
            print(f"🎵 音频: {audio_file}")
        if transcript:
            for k, v in transcript.items():
                print(f"📝 {k}: {v}")
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
