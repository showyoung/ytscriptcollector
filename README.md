# YouTube 频道文字脚本采集器

跨平台工具，支持 Linux / macOS / Windows。

## 功能

- 🎬 下载 YouTube 视频（多种画质）
- 🎵 下载音频（MP3 / WAV）
- 📝 生成字幕文件（.srt，多语言）
- 📄 生成可读文本（.md）
- 🤖 AI 模式（JSON 输出）
- 🌐 Web UI 界面
- 🔍 自动检测已登录 YouTube 的浏览器

## 系统依赖

**只需要安装 bash（和 curl 用于下载 ffprobe）**，其他全部由安装脚本自动配置：

| 依赖             | 说明       | 安装方式           |
| ---------------- | ---------- | ------------------ |
| Python ≥ 3.9     | 运行本工具 | 自动（via mise）   |
| ffmpeg + ffprobe | 音视频处理 | 自动（via 静态包） |
| Node.js          | EJS 求解   | 自动（via mise）   |

## 安装

```bash
cd youtubeChannelScriptCollector
bash install.sh
```

安装脚本会自动：
1. 创建 Python 虚拟环境（`.venv/`）
2. 通过 mise 安装 Node.js（`.node/`）
3. 下载 ffmpeg + ffprobe（`.ffmpeg/bin/`）
4. 安装 Python 依赖
5. 注册命令：`ytdl-cli` / `ytdl-aicli` / `ytdl-webui`

**再次运行 install.sh 会自动跳过已就绪的组件**（venv / node / ffmpeg），只安装缺失或损坏的部分。

## 使用方式

### Web UI（推荐新手）

```bash
ytdl-webui
# 浏览器打开 http://localhost:8765
```

### 交互式 CLI

```bash
ytdl-cli "https://www.youtube.com/watch?v=..."
```

指定画质 / 转码 / 音频模式：

```bash
ytdl-cli "URL" -q 720p --code-convert --media-type audio
```

### AI 模式（JSON 输出）

```bash
ytdl-aicli "URL"
```

## CLI 选项

| 选项                 | 说明                                          | 默认           |
| -------------------- | --------------------------------------------- | -------------- |
| `url`                | YouTube 链接                                  | —              |
| `-o, --output DIR`   | 输出目录                                      | `~/downloads/` |
| `--cookies`          | chrome/firefox/edge/brave/opera/chromium/auto | auto           |
| `--media-type`       | video / audio                                 | video          |
| `-q, --quality`      | 144p/240p/360p/480p/720p/1080p/.../best       | 360p           |
| `--code-convert`     | HEVC/H.264 转码                               | false          |
| `--srt`              | 生成 .srt 字幕                                | true           |
| `--md`               | 生成 .md 文本                                 | true           |
| `--whisper-model`    | tiny/base/small/medium/large                  | tiny           |
| `--whisper-language` | ISO 639-1 语言代码                            | zh             |
| `--separate-audio`   | 分离音频文件                                  | false          |
| `--audio-format`     | mp3 / wav                                     | mp3            |

## Whisper 模型

| 模型   | 速度 | 准确度 | 推荐场景       |
| ------ | ---- | ------ | -------------- |
| tiny   | 最快 | 差     | 测试、批量预览 |
| base   | 快   | 较差   | **推荐首选**   |
| small  | 中等 | 一般   | 重要内容       |
| medium | 慢   | 较好   | 出版级精度     |
| large  | 最慢 | 好     | 最高精度       |

> 老机器建议用 `tiny` 或 `base`。

## Cookie 说明

工具自动检测已登录 YouTube 的浏览器，按优先级：
**Chrome → Firefox → Edge → Brave → Opera → Chromium**

需要浏览器**至少打开过一次 YouTube 并保持登录状态**。

## 常见问题

**Q: Whisper 转录很慢**
A: 使用 `--whisper-model tiny`（默认）。

**Q: ffprobe not found**
A: 确认 `bash install.sh` 已成功完成，`.ffmpeg/bin/` 目录存在。

**Q: 再次运行 install.sh 很慢**
A: 不会。已就绪的 `.venv/`、`.node/`、`.ffmpeg/` 会自动跳过，只检查可用性。

## 项目结构

```
youtubeChannelScriptCollector/
├── .venv/                 # Python 虚拟环境（隔离，不污染系统）
├── .node/                 # Node.js（mise 安装，项目本地）
│   └── installs/node/22.x.x/bin/node
├── .ffmpeg/bin/           # ffmpeg + ffprobe（静态包，项目本地）
├── __init__.py
├── utils.py               # 工具函数（路径查找、Cookie 检测）
├── collector.py           # 核心业务（下载 + 转录）
├── cli.py                 # 交互式 CLI
├── aicrobot.py            # AI 模式 CLI
├── web_ui.py              # Web UI 服务器
├── config.py              # 配置管理
├── config.yaml            # 用户配置
├── requirements.txt       # Python 依赖（含版本约束）
├── install.sh             # 一键安装/卸载
└── downloads/             # 下载目录（自动创建）
```

## 卸载

```bash
bash install.sh --uninstall
# 删除: ~/.local/bin/{ytdl-cli,ytdl-aicli,ytdl-webui}
# 删除: .venv/ .node/ .ffmpeg/
```

## 协议

MIT License
