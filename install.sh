#!/bin/bash
# YouTube 脚本采集器 - 安装脚本
# 支持 Linux / macOS / Windows (Git Bash / WSL)
# 用法:
#   bash install.sh        # 安装
#   bash install.sh -u     # 卸载命令
#   bash install.sh --uninstall  # 同上

TOOL_DIR="$(cd "$(dirname "$0")" && pwd)"
BIN_DIR="$HOME/.local/bin"

# === 卸载 ===
if [[ "$1" == "-u" || "$1" == "--uninstall" ]]; then
    echo "=================================="
    echo "YouTube 脚本采集器 - 卸载"
    echo "=================================="
    echo ""
    echo "删除命令: $BIN_DIR/{ytdl-cli,ytdl-aicli,ytdl-webui}"
    rm -f "$BIN_DIR/ytdl-cli" "$BIN_DIR/ytdl-aicli" "$BIN_DIR/ytdl-webui"
    echo "✅ 命令已删除"
    echo ""
    echo "提示: 如需彻底删除工具，请手动删除目录:"
    echo "  rm -rf $TOOL_DIR"
    echo ""
    echo "如需重新安装: bash install.sh"
    exit 0
fi

set -e

echo "=================================="
echo "YouTube 脚本采集器 - 安装程序"
echo "=================================="
echo ""
echo "工具目录: $TOOL_DIR"
echo "命令目录: $BIN_DIR"
echo ""

# 1. 创建目录
echo "[1/5] 创建命令目录..."
mkdir -p "$BIN_DIR"
echo "   ✅"

# 2. 检查工具文件
echo "[2/5] 检查工具文件..."
if [ ! -f "$TOOL_DIR/cli.py" ] || [ ! -f "$TOOL_DIR/collector.py" ]; then
    echo "错误: 未找到工具文件"
    exit 1
fi
echo "   ✅ 工具文件就绪"

# 3. 安装命令
echo "[3/5] 安装命令..."
# 查找 Python (用绝对路径，不依赖 PATH)
PYTHONS="/usr/bin/python3 /usr/local/bin/python3 $HOME/.local/bin/python3"
PYTHON_CMD=""
for p in $PYTHONS; do
    if [ -f "$p" ] && [ -x "$p" ]; then
        PYTHON_CMD="$p"
        break
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "   ⚠️  未找到 Python3，跳过命令安装"
    echo "   (其他步骤继续...)"
else
    echo "   Python: $PYTHON_CMD"
    # cli.py 必定存在，其他两个可能尚未重构
    for name in ytdl-cli ytdl-aicli ytdl-webui; do
        case $name in
            ytdl-cli)   script="cli.py" ;;
            ytdl-aicli) script="aicrobot.py" ;;
            ytdl-webui) script="web_ui.py" ;;
        esac
        cat > "$BIN_DIR/$name" << EOF
#!/bin/bash
exec $PYTHON_CMD "$TOOL_DIR/$script" "\$@"
EOF
        chmod +x "$BIN_DIR/$name"
        echo "   ✅ $name"
    done
fi

# 4. 安装 Python 依赖
echo "[4/5] 安装 Python 依赖..."
if [ -n "$PYTHON_CMD" ]; then
    $PYTHON_CMD -m pip install --user yt-dlp pyyaml openai-whisper 2>/dev/null || \
    $PYTHON_CMD -m pip install --user --break-system-packages yt-dlp pyyaml openai-whisper 2>/dev/null || \
    $PYTHON_CMD -m pip install --break-system-packages yt-dlp pyyaml openai-whisper 2>/dev/null || \
    echo "   ⚠️  安装失败，请手动执行:"
    echo "   pip install yt-dlp pyyaml openai-whisper"
fi

# 5. 检查依赖
echo "[5/5] 检查依赖..."
MISSING=()

# Node.js - 用绝对路径检测
NODE_FOUND=0
for p in /usr/bin/node /usr/local/bin/node "$HOME/.local/bin/node"; do
    if [ -f "$p" ] && [ -x "$p" ]; then
        NODE_FOUND=1
        break
    fi
done
if [ $NODE_FOUND -eq 0 ]; then
    MISSING+=("Node.js (https://nodejs.org)")
fi

# ffmpeg + ffprobe - 用绝对路径检测
FFMPEG_FOUND=0
FFPROBE_FOUND=0
for d in /usr/bin /usr/local/bin "$HOME/.local/bin" /opt/homebrew/bin "$HOME/.nvm/versions/node/v24.14.1/bin"; do
    if [ -f "$d/ffmpeg" ] && [ -x "$d/ffmpeg" ]; then FFMPEG_FOUND=1; fi
    if [ -f "$d/ffprobe" ] && [ -x "$d/ffprobe" ]; then FFPROBE_FOUND=1; fi
done
if [ $FFMPEG_FOUND -eq 0 ]; then
    MISSING+=("ffmpeg (Linux: apt install ffmpeg | macOS: brew install ffmpeg)")
fi
if [ $FFPROBE_FOUND -eq 0 ]; then
    MISSING+=("ffprobe (通常随 ffmpeg 一起装，部分系统需单独装)")
fi

if [ ${#MISSING[@]} -eq 0 ]; then
    echo "   ✅ 所有依赖已满足"
else
    echo "   ⚠️  缺少以下依赖，请手动安装:"
    for dep in "${MISSING[@]}"; do
        echo "     - $dep"
    done
fi

echo ""
echo "=================================="
echo "✅ 安装完成!"
echo "=================================="
echo ""
echo "命令:"
echo "  ytdl-cli \"URL\"   # 交互式 CLI"
echo "  ytdl-aicli  \"URL\"   # AI 模式"
echo "  ytdl-webui                # Web UI"
echo ""
echo "注意: 需要浏览器已登录 YouTube"
echo ""
echo "卸载: bash install.sh --uninstall"
