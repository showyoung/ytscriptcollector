# YouTube 频道文字脚本采集器

跨平台工具，支持 Linux / macOS / Windows。

## 功能

- 🎬 下载 YouTube 视频（多种画质，支持 HEVC/H.264 转码）
- 🎵 下载音频（MP3 / WAV）
- 📝 生成字幕文件（.srt，多语言）
- 📄 生成可读文本（.md）
- 🤖 AI 模式（JSON 输出）
- 🌐 Web UI 界面
- 🔍 自动检测已登录 YouTube 的浏览器

## 系统依赖

| 依赖         | 说明       | 安装方式                         |
| ------------ | ---------- | -------------------------------- |
| Python ≥ 3.8 | 运行本工具 | python.org                       |
| ffmpeg       | 音视频处理 | `apt/brew/winget install ffmpeg` |
| Node.js      | 解 JS 验证 | nodejs.org                       |

## 安装

```bash
# 1. 进入目录
cd youtubeChannelScriptCollector

# 2. 安装 Python 依赖
pip install yt-dlp pyyaml openai-whisper

# 3. 安装命令（可选）
bash install.sh
```

## 使用方式

### Web UI（推荐新手）

```bash
python3 web_ui.py
# 浏览器打开 http://localhost:8765
```

### 交互式 CLI

```bash
python3 cli.py "https://www.youtube.com/watch?v=..."
```

指定画质 / 转码 / 音频模式：

```bash
python3 cli.py "URL" -q 720p --code-convert --media-type audio
```

### AI 模式（JSON 输出）

```bash
python3 aicrobot.py "URL"
```

## CLI 选项

| 选项                 | 说明                                                  | 默认                         |
| -------------------- | ----------------------------------------------------- | ---------------------------- |
| `url`                | YouTube 链接                                          | —                            |
| `-o, --output DIR`   | 输出目录                                              | `~`（软件目录下 downloads/） |
| `--cookies`          | 浏览器: chrome/firefox/edge/brave/opera/chromium/auto | auto                         |
| `--media-type`       | video / audio                                         | video                        |
| `-q, --quality`      | 画质                                                  | 360p                         |
| `--code-convert`     | 是否转码: true/false                                  | false                        |
| `--srt`              | 生成 .srt 字幕: true/false                            | true                         |
| `--md`               | 生成 .md 文本: true/false                             | true                         |
| `--whisper-model`    | tiny/base/small/medium/large                          | tiny                         |
| `--whisper-language` | Whisper 转录语言，使用 ISO 639-1 语言代码             | zh                           |
| `--separate-audio`   | 分离音频文件: true/false                              | false                        |
| `--audio-format`     | mp3 / wav                                             | mp3                          |

## Whisper 模型

| 模型   | 速度 | 中文准确率 | 推荐场景       |
| ------ | ---- | ---------- | -------------- |
| tiny   | 最快 | 尚可       | 测试、批量预览 |
| base   | 快   | 更好       | **推荐首选**   |
| small  | 中等 | 好         | 重要内容       |
| medium | 慢   | 很高       | 出版级精度     |
| large  | 最慢 | 最高       | 最高精度       |

> Mac 老机器建议用 `tiny` 或 `base`。

## 字幕语言顺序

工具按以下优先级下载 YouTube 字幕：

`zh → en → de → ja → fr → ko → es → hi → pt → ar → nb → da → sv → nl → ru → vi → id`

可在 `config.yaml` 中修改 `subtitle_languages` 列表。

## Cookie 说明

工具自动检测已登录 YouTube 的浏览器，按优先级：
**Chrome → Firefox → Edge → Brave → Opera → Chromium**

也可手动指定：`--cookies chrome`

需要浏览器**至少打开过一次 YouTube 并保持登录状态**。

## 常见问题

**Q: yt-dlp 报 "EJS Challenge" 错误**
A: 确保 Node.js 已安装（`node --version`）。工具会自动使用 Node 解 JS 验证。

**Q: Whisper 转录很慢**
A: 使用 `--whisper-model tiny`（默认）。CPU 较弱时建议用 `tiny`。

**Q: 403 Forbidden / 无法获取视频信息**
A: Cookie 无效或过期。在浏览器重新登录 YouTube 后重试。

**Q: 找不到 ffmpeg / 转录失败**
A: 确认 ffmpeg 已安装且在 PATH 中：`ffmpeg -version`

**Q: 换机器后路径不同**
A: ffmpeg 和 Node.js 路径由工具自动搜索各平台常见安装位置，无需手动配置。

## 文件结构

```
youtubeChannelScriptCollector/
├── __init__.py          # 包入口，公开 API
├── utils.py             # 工具函数（浏览器检测、路径查找）
├── collector.py         # 核心业务（下载 + 转录）
├── cli.py               # 交互式 CLI
├── aicrobot.py          # AI 模式 CLI（JSON 输出）
├── web_ui.py            # Web UI 服务器
├── web_ui/              # Web UI 静态资源
│   ├── index.html       # 页面入口
│   ├── app.js           # 前端逻辑
│   ├── style.css        # 深色主题样式
│   └── style-light.css  # 浅色主题样式
├── config.py            # 配置管理
├── config.yaml          # 用户配置（可自行修改）
├── requirements.txt     # Python 依赖
├── install.sh           # 安装/卸载命令
└── downloads/           # 下载目录（自动创建）
```

## 卸载

```bash
bash install.sh --uninstall
# 删除命令: ~/.local/bin/{ytdl-cli,ytdl-aicli,ytdl-webui}
```

## 协议

MIT License
