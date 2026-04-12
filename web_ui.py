#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web UI 服务器
直接调用 collect()，不通过 subprocess。
用法: python3 web_ui.py [端口]
"""
import http.server
import socketserver
import json
import sys
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

# 超时配置（秒），可按需修改
sys.path.insert(0, str(Path(__file__).parent))
from collector import collect, get_video_info, get_available_formats, detect_youtube_browser
from utils import format_duration, str2bool, resolve_quality
from config import (
    defaults as config_defaults,
    resolve_output_dir,
    qualities,
    media_types,
    audio_formats,
    whisper_models,
    subtitle_languages,
    supported_browsers,
    port,
    timeout_seconds,
)

WEB_DIR = Path(__file__).parent / "web_ui"


def _run_collect(params: dict) -> dict:
    """
    在线程中执行 collect()，返回结果字典或抛出异常。
    不写 result.json。
    """
    result = collect(
        url=params["url"],
        output_dir=params["output_dir"],
        quality=params["quality"],
        audio_only=params["audio_only"],
        generate_subtitle=params["generate_subtitle"],
        generate_md=params["generate_md"],
        whisper_model=params["whisper_model"],
        whisper_language=params["whisper_language"],
        cookies_method=params["cookies_method"],
        extract_audio_separate=params["extract_audio_separate"],
        audio_format=params["audio_format"],
        hevc=params["hevc"],
        subtitle_source="auto",
        verbose=False,
    )
    return result


class Handler(http.server.BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {args[0]}")

    def send_json(self, data: dict, status: int = 200) -> None:
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
        except BrokenPipeError:
            pass

    def send_text(self, text: str, status: int = 200) -> None:
        try:
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(text.encode("utf-8"))
        except BrokenPipeError:
            pass

    # ---- 路由 ---------------------------------------------------------------

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.serve_index()
        elif self.path == "/api/defaults":
            self.api_defaults()
        elif self.path == "/api/options":
            self.api_options()
        elif self.path in ("/style.css", "/style-light.css", "/app.js"):
            self.serve_static(self.path)
        else:
            self.send_error(404)

    def serve_static(self, path: str) -> None:
        """返回静态文件（CSS/JS）"""
        filename = WEB_DIR / path.lstrip("/")
        if not filename.exists():
            self.send_error(404)
            return
        try:
            content = filename.read_bytes()
            ext = filename.suffix
            if ext == ".css":
                content_type = "text/css"
            elif ext == ".js":
                content_type = "application/javascript"
            else:
                content_type = "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(content)
        except Exception:
            self.send_error(500)

    def do_POST(self):
        parsed = Path(self.path)
        if str(parsed) == "/api/collect":
            self.api_collect()
        else:
            self.send_error(404)

    # ---- 页面 ---------------------------------------------------------------

    def serve_index(self):
        html_path = WEB_DIR / "index.html"
        if not html_path.exists():
            self.send_error(404, "index.html not found")
            return
        try:
            content = html_path.read_text(encoding="utf-8")
        except Exception:
            self.send_error(500, "cannot read index.html")
            return
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(content.encode("utf-8"))
        except BrokenPipeError:
            pass

    # ---- API ----------------------------------------------------------------

    def api_defaults(self):
        """返回默认配置"""
        cfg = config_defaults()
        self.send_json({
            "quality":          cfg.get("quality"),
            "whisper_model":    cfg.get("whisper_model"),
            "whisper_language": cfg.get("whisper_language"),
            "cookies_method":   cfg.get("cookies_method"),
            "media_type":       cfg.get("media_type"),
            "audio_format":     cfg.get("audio_format"),
            "separate_audio":  cfg.get("separate_audio"),
            "srt":              cfg.get("srt"),
            "md":               cfg.get("md"),
            "code_convert":     cfg.get("code_convert"),
            "output_dir":       str(resolve_output_dir(cfg.get("output_dir"))),
        })

    def api_options(self):
        """返回所有表单选项（动态从 config 读取）"""
        langs = subtitle_languages()
        subtitle_langs = [l for l in langs if l != "all"]
        self.send_json({
            "qualities":         qualities(),
            "media_types":       media_types(),
            "audio_formats":     audio_formats(),
            "whisper_models":    whisper_models(),
            "subtitle_languages": subtitle_langs,
            "browsers":          supported_browsers() + ["auto"],
        })

    def api_collect(self):
        """
        接收表单/JSON，调用 collect()。
        - JSON 请求（Content-Type: application/json）：返回结构化 JSON
        - 其他：返回纯文本摘要（供前端 alert 使用）
        不写 result.json。
        """
        is_json_request = "application/json" in self.headers.get("Content-Type", "")

        # ---- 读取请求体 ----
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            self._respond_error(is_json_request, "请求格式错误", 400)
            return

        url = data.get("url", "").strip()
        if not url:
            self._respond_error(is_json_request, "URL 不能为空", 400)
            return

        cfg = config_defaults()

        # ---- preview 模式 ----
        if data.get("preview"):
            preview_cookies = data.get("cookies", cfg.get("cookies_method"))
            self._handle_preview(url, is_json_request, preview_cookies)
            return

        # ---- 完整采集 ----
        cookies = data.get("cookies", cfg.get("cookies_method"))
        if cookies == "auto":
            cookies = detect_youtube_browser() or cfg.get("cookies_fallback")

        # 参数解析
        media_type = data.get("media_type", cfg.get("media_type", "video"))
        audio_only = (media_type == "audio")
        quality = data.get("quality", cfg.get("quality", "360p"))
        if not audio_only:
            quality, _ = resolve_quality(quality, url, cookies)
        else:
            quality = "audio"

        generate_subtitle = str2bool(data.get("srt"), cfg.get("srt", True))
        generate_md       = str2bool(data.get("md"),   cfg.get("md",   True))
        extract_audio     = str2bool(data.get("separate_audio"), cfg.get("separate_audio", False))
        hevc              = str2bool(data.get("code_convert"),   cfg.get("code_convert", False))
        whisper_model     = data.get("whisper_model", cfg.get("whisper_model", "tiny"))
        whisper_language  = data.get("whisper_language", cfg.get("whisper_language", "zh"))
        audio_format      = data.get("audio_format", cfg.get("audio_format", "mp3"))
        output_dir = data.get("output_dir") or str(resolve_output_dir(cfg.get("output_dir")))

        params = {
            "url": url,
            "output_dir": output_dir,
            "quality": quality,
            "audio_only": audio_only,
            "generate_subtitle": generate_subtitle,
            "generate_md": generate_md,
            "whisper_model": whisper_model,
            "whisper_language": whisper_language,
            "cookies_method": cookies,
            "extract_audio_separate": extract_audio,
            "audio_format": audio_format,
            "hevc": hevc,
        }

        # ---- 在线程池中执行 collect()，带超时 ----
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_run_collect, params)
            try:
                result = future.result(timeout=timeout_seconds())
                self._respond_success(is_json_request, result)
            except FuturesTimeoutError:
                self._respond_error(
                    is_json_request,
                    f"采集超时（已超过 {timeout_seconds()} 秒）",
                    408
                )
            except RuntimeError as e:
                self._respond_error(is_json_request, str(e), 400)
            except Exception as e:
                self._respond_error(is_json_request, str(e), 500)

    def _handle_preview(self, url: str, is_json_request: bool, cookies: str = "auto"):
        """预览视频信息"""
        cfg = config_defaults()
        if cookies == "auto":
            cookies = detect_youtube_browser() or cfg.get("cookies_fallback")
        try:
            info = get_video_info(url, cookies_method=cookies)
            if not info:
                self._respond_error(is_json_request, "无法获取视频信息", 400)
                return

            formats = get_available_formats(url, cookies_method=cookies)
            seen = set()
            video_formats = []
            for f in formats:
                h = f.get("height", 0)
                if h and h not in seen:
                    seen.add(h)
                    video_formats.append({
                        "height":     h,
                        "resolution": f.get("resolution", ""),
                        "ext":        f.get("ext", ""),
                        "filesize":   f.get("filesize", ""),
                        "itag":       f.get("itag", ""),
                    })

            preview_result = {
                "title":        info.get("title", ""),
                "channel":      info.get("channel", ""),
                "duration":     info.get("duration", 0),
                "duration_str": format_duration(info.get("duration", 0)),
                "upload_date":  info.get("upload_date", ""),
            }

            if is_json_request:
                self.send_json({"ok": True, "result": preview_result, "formats": video_formats})
            else:
                lines = [
                    f"标题: {preview_result['title']}",
                    f"频道: {preview_result['channel']}",
                    f"时长: {preview_result['duration_str']}",
                    f"上传日期: {preview_result['upload_date']}",
                    "",
                    "可用画质:",
                ]
                for fmt in sorted(video_formats, key=lambda x: x["height"], reverse=True):
                    lines.append(f"  {fmt['height']}p {fmt['resolution']} ({fmt['ext']})")
                self.send_text("\n".join(lines))

        except Exception as e:
            self._respond_error(is_json_request, str(e), 400)

    def _respond_success(self, is_json_request: bool, result: dict):
        """处理采集成功结果"""
        # 提取关键字段组成摘要
        lines = [
            f"标题: {result.get('title', '未知')}",
            f"频道: {result.get('channel', '未知')}",
            f"时长: {result.get('duration', '未知')}",
            "",
            f"文件: {result.get('downloaded_file', '无')}",
        ]
        transcript = result.get("transcript", {})
        if transcript:
            lines.append(f"字幕/文本: {len(transcript)} 个文件")
            for k, v in transcript.items():
                lines.append(f"  {k}: {Path(v).name}")

        if is_json_request:
            self.send_json({
                "ok": True,
                "result": {
                    "url":             result.get("url"),
                    "title":           result.get("title"),
                    "channel":         result.get("channel"),
                    "duration":        result.get("duration"),
                    "downloaded_file": result.get("downloaded_file"),
                    "transcript":      result.get("transcript", {}),
                },
                "summary": "\n".join(lines),
            })
        else:
            self.send_text("\n".join(lines))

    def _respond_error(self, is_json_request: bool, message: str, status: int = 400):
        if is_json_request:
            self.send_json({"ok": False, "error": message}, status)
        else:
            self.send_text(f"❌ {message}", status)


# ============================================================================
# 启动
# ============================================================================

def run_server(_port: int | None = None) -> None:
    """供 entry point 和 run.py 调用的启动函数"""
    resolved_port = _port if _port is not None else port()
    print(f"启动 Web UI: http://localhost:{resolved_port}")
    print(f"按 Ctrl+C 停止")

    class ReusableTCPServer(socketserver.TCPServer):
        allow_reuse_address = True

    with ReusableTCPServer(("", resolved_port), Handler) as httpd:
        httpd.serve_forever()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_server(int(sys.argv[1]))
    else:
        run_server()
