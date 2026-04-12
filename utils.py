# -*- coding: utf-8 -*-
"""
工具函数
跨平台路径、浏览器 Cookie 检测、ffmpeg/Node 路径等可独立测试的工具。
"""
from __future__ import annotations

import os
import sys
import sqlite3
import shutil
import tempfile
from pathlib import Path

from config import supported_browsers as _supported_browsers


def resolve_quality(requested: str, url: str, cookies: str) -> tuple[str, str]:
    """
    将用户请求的画质解析为实际可用的画质。
    找不到请求的画质时，向下找次一级，没有则向上找。
    返回 (quality, quality_label)
    """
    if requested == "audio" or requested == "best":
        return requested, ("音频" if requested == "audio" else "最佳画质")

    # 延迟导入避免循环依赖
    from collector import get_available_formats
    formats = get_available_formats(url, cookies_method=cookies)
    seen = set()
    available = []
    for f in formats:
        h = f.get("height", 0)
        if h and h not in seen:
            seen.add(h)
            available.append(h)
    available.sort(reverse=True)

    target = int(requested.rstrip("p"))

    # 向下找
    for h in available:
        if h <= target:
            return f"{h}p", f"{h}p"

    # 向下找不到，向上找
    for h in sorted(available, reverse=False):
        if h > target:
            return f"{h}p", f"{h}p"

    # 完全没有可用画质，用 best
    return "best", "最佳画质"

def str2bool(val: str | bool | None, default: bool) -> bool:
    """将 "true"/"false"/bool/None 转为 bool，None 时用 default"""
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    return val.lower() == "true"

# ============================================================================
# 可执行文件查找
# ============================================================================

def find_executable(name: str, extra_paths: list[str] | None = None) -> str:
    """
    查找可执行文件路径，优先在 extra_paths 和常见平台路径中查找，
    都找不到时返回 name 本身（由 shutil.which() 从 PATH 中寻找）。
    """
    candidates = []

    # 用户指定的额外路径（优先级最高）
    if extra_paths:
        for p in extra_paths:
            base = Path(p).expanduser()
            candidates.extend([
                base / name,
                base / "bin" / name,
                base / f"{name}.exe",
                base / "bin" / f"{name}.exe",
            ])

    # 平台相关搜索路径
    home = Path.home()
    if sys.platform == "darwin":
        candidates.extend([
            home / "Library" / "Application Support" / name / "bin" / name,
        ])
    elif sys.platform == "win32":
        candidates.extend([
            Path(os.environ.get("PROGRAMFILES", "")) / name / f"{name}.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / name / f"{name}.exe",
        ])
    else:
        # Linux
        candidates.extend([
            home / ".local" / "bin" / name,
            Path("/usr/local/bin") / name,
            Path("/usr/bin") / name,
        ])

    for c in candidates:
        if c.exists():
            return str(c)

    # 最后 fallback：让 shutil.which() 查找 PATH
    return name


def get_ffmpeg() -> str:
    """查找 ffmpeg 路径"""
    return find_executable("ffmpeg", extra_paths=[
        str(Path.home() / ".local" / "bin"),
    ])


def get_js_runtime() -> str:
    """查找 Node.js 运行时路径"""
    return find_executable("node", extra_paths=[
        str(Path.home() / ".nvm" / "versions" / "node" / "v24.14.1" / "bin"),
    ])


# ============================================================================
# 工具函数
# ============================================================================

def format_duration(seconds: int | float) -> str:
    """将秒数格式化为人类可读时长字符串"""
    if not seconds:
        return "未知"
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h}h {m}m {s}s"
    return f"{m}m {s}s"


# ============================================================================
# 浏览器 Cookie 自动检测
# ============================================================================

def _get_cookie_db_path(browser: str) -> Path | None:
    """
    获取浏览器 Cookie SQLite 数据库文件路径。
    返回 None 表示该浏览器未安装或路径不可访问。
    """
    home = Path.home()

    if sys.platform == "darwin":
        base = home / "Library" / "Application Support"
        if browser == "firefox":
            ff_base = base / "Firefox" / "Profiles"
            if ff_base.exists():
                for p in ff_base.glob("*"):
                    if p.is_dir():
                        return p / "cookies.sqlite"
        elif browser == "chrome":
            return base / "Google" / "Chrome" / "Default" / "Cookies"
        elif browser == "edge":
            return base / "Microsoft Edge" / "Default" / "Cookies"
        elif browser == "brave":
            return base / "BraveSoftware" / "Brave-Browser" / "Default" / "Cookies"

    elif sys.platform == "win32":
        local = Path(os.environ.get("LOCALAPPDATA", ""))
        appdata = Path(os.environ.get("APPDATA", ""))
        if browser == "firefox":
            ff_base = appdata / "Mozilla" / "Firefox"
            for p in ff_base.glob("Profiles/*/"):
                if p.is_dir():
                    return p / "cookies.sqlite"
        elif browser == "chrome":
            return local / "Google" / "Chrome" / "User Data" / "Default" / "Cookies"
        elif browser == "edge":
            return local / "Microsoft" / "Edge" / "User Data" / "Default" / "Cookies"
        elif browser == "brave":
            return local / "BraveSoftware" / "Brave-Browser" / "User Data" / "Default" / "Cookies"

    else:
        # Linux
        config = home / ".config"
        if browser == "firefox":
            ff_base = config / "firefox"
            if ff_base.exists():
                for p in ff_base.glob("Profiles/*/"):
                    cookies = p / "cookies.sqlite"
                    if cookies.exists():
                        return cookies
                for p in ff_base.glob("*/cookies.sqlite"):
                    return p
        elif browser == "chrome":
            p = config / "google-chrome" / "Default" / "Cookies"
            if p.exists():
                return p
        elif browser == "chromium":
            p = config / "chromium" / "Default" / "Cookies"
            if p.exists():
                return p
        elif browser == "edge":
            p = config / "microsoft-edge" / "Default" / "Cookies"
            if p.exists():
                return p
        elif browser == "brave":
            p = config / "BraveSoftware" / "Brave-Browser" / "Default" / "Cookies"
            if p.exists():
                return p

    return None


def _has_youtube_cookies(browser: str) -> bool:
    """
    检测某个浏览器是否有 YouTube 登录 Cookie。
    """
    db_path = _get_cookie_db_path(browser)
    if not db_path:
        return False

    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        shutil.copy2(db_path, tmp.name)

        conn = sqlite3.connect(tmp.name)
        cursor = conn.cursor()

        for table in ("moz_cookies", "cookies"):
            try:
                cursor.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE host LIKE '%youtube%'"
                )
                count = cursor.fetchone()[0]
                conn.close()
                os.unlink(tmp.name)
                return count > 0
            except sqlite3.OperationalError:
                continue

        conn.close()
        os.unlink(tmp.name)
    except Exception:
        pass

    return False


def detect_youtube_browser() -> str | None:
    """
    自动检测已登录 YouTube 的浏览器。
    按优先级顺序遍历支持的浏览器，返回第一个找到有 YouTube Cookie 的。
    """
    for browser in _supported_browsers():
        if _has_youtube_cookies(browser):
            return browser
    return None
