#!/bin/bash
#
# YouTube 脚本采集器 - 安装脚本
# 支持 Linux / macOS
# 用法:
#   bash install.sh        # 安装
#   bash install.sh -u     # 卸载
#   bash install.sh --uninstall  # 同上
#
# Windows 用户请使用 install.ps1:
#   powershell -ExecutionPolicy Bypass -File install.ps1
#

set -e

TOOL_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="${TOOL_DIR}/.venv"
BIN_DIR="${HOME}/.local/bin"

# ──────────────────────────────────────────────
# 颜色
# ──────────────────────────────────────────────
if [[ -t 1 ]] && command -v tput > /dev/null 2>&1; then
  BOLD="$(tput bold)"
  GREEN="${BOLD}$(tput setaf 2)"
  YELLOW="${BOLD}$(tput setaf 3)"
  RED="${BOLD}$(tput setaf 1)"
  RESET="$(tput sgr0)"
else
  BOLD=""; GREEN=""; YELLOW=""; RED=""; RESET=""
fi

info()    { echo "   ${GREEN}✅${RESET} $1"; }
warn()    { echo "   ${YELLOW}⚠️${RESET} $1"; }
error()   { echo "   ${RED}❌${RESET} $1"; }

# ──────────────────────────────────────────────
# 卸载
# ──────────────────────────────────────────────
if [[ "$1" == "-u" || "$1" == "--uninstall" ]]; then
  echo "=================================="
  echo "YouTube 脚本采集器 - 卸载"
  echo "=================================="
  echo ""
  for name in ytdl-cli ytdl-aicli ytdl-webui; do
    rm -f "${BIN_DIR}/${name}"
    echo "  删除: ${BIN_DIR}/${name}"
  done
  echo ""
  echo "  删除项目数据:"
  rm -rf "${TOOL_DIR}/.venv" && echo "  删除: ${TOOL_DIR}/.venv"
  rm -rf "${TOOL_DIR}/.node"  && echo "  删除: ${TOOL_DIR}/.node"
  rm -rf "${TOOL_DIR}/.ffmpeg" && echo "  删除: ${TOOL_DIR}/.ffmpeg"
  echo ""
  info "命令和数据已删除"
  echo ""
  echo "提示: 如需彻底删除工具，请手动删除目录:"
  echo "  rm -rf ${TOOL_DIR}"
  echo ""
  echo "重新安装: bash install.sh"
  exit 0
fi

# ──────────────────────────────────────────────
# Banner
# ──────────────────────────────────────────────
echo "=================================="
echo "YouTube 脚本采集器 - 安装程序"
echo "=================================="
echo ""
echo "  工具目录: ${TOOL_DIR}"
echo "  命令目录: ${BIN_DIR}"
echo ""

# ──────────────────────────────────────────────
# Step 1: 创建命令目录
# ──────────────────────────────────────────────
echo "[1/8] 创建命令目录..."
mkdir -p "${BIN_DIR}"
info "命令目录就绪"
echo ""

# ──────────────────────────────────────────────
# Step 2: 检查工具文件
# ──────────────────────────────────────────────
echo "[2/8] 检查工具文件..."
MISSING_FILES=0
for f in cli.py collector.py; do
  if [[ ! -f "${TOOL_DIR}/${f}" ]]; then
    error "未找到: ${f}"
    MISSING_FILES=1
  fi
done
if [[ ${MISSING_FILES} -eq 1 ]]; then
  exit 1
fi
info "工具文件就绪"
echo ""

# ──────────────────────────────────────────────
# Step 3: 查找系统 Python（用于创建 venv）
# 优先 mise shims（版本管理器），再找系统 Python
# ──────────────────────────────────────────────
echo "[3/8] 查找系统 Python（用于创建虚拟环境）..."

# 确保 mise shims 在 PATH 前列（mise / pyenv / nvm 等）
export PATH="${HOME}/.local/share/mise/shims:${HOME}/.local/bin:${PATH}"

find_python() {
  # Linux / macOS: python3; Windows: python / py
  command -v python3 2>/dev/null && return 0
  command -v python  2>/dev/null && return 0
  command -v py      2>/dev/null && return 0
  return 1
}

SYSTEM_PYTHON=""
if find_python; then
  SYSTEM_PYTHON="$(find_python)"
fi

if [[ -z "${SYSTEM_PYTHON}" ]]; then
  error "未找到 Python3，请先安装 Python >= 3.9"
  echo "  下载: https://www.python.org/downloads"
  exit 1
fi

# 版本检查
PY_MAJOR=$("${SYSTEM_PYTHON}" -c 'import sys; print(sys.version_info[0])')
PY_MINOR=$("${SYSTEM_PYTHON}" -c 'import sys; print(sys.version_info[1])')
if [[ "${PY_MAJOR}" -lt 3 ]] || [[ "${PY_MAJOR}" -eq 3 && "${PY_MINOR}" -lt 9 ]]; then
  error "Python 版本过低（需要 >= 3.9）"
  exit 1
fi

info "系统 Python: $("${SYSTEM_PYTHON}" --version 2>&1)"
echo ""

# ──────────────────────────────────────────────
# Step 4: 处理 .venv（存在则检查，损坏则重建）
# ──────────────────────────────────────────────
echo "[4/8] 处理虚拟环境 .venv ..."

check_venv() {
  local py="${VENV_DIR}/bin/python"
  [[ -f "${VENV_DIR}/Scripts/python.exe" ]] && py="${VENV_DIR}/Scripts/python.exe"
  if [[ -f "${py}" ]] && "${py}" --version > /dev/null 2>&1; then
    return 0
  fi
  return 1
}

if [[ -d "${VENV_DIR}" ]]; then
  if check_venv; then
    info "虚拟环境已存在且可用: ${VENV_DIR}"
  else
    warn "虚拟环境损坏，删除并重新创建..."
    rm -rf "${VENV_DIR}"
    VENV_RECREATE=1
  fi
fi

if [[ ! -d "${VENV_DIR}" ]] || [[ "${VENV_RECREATE}" == "1" ]]; then
  if command -v uv > /dev/null 2>&1; then
    info "使用 uv 创建虚拟环境"
    uv venv "${VENV_DIR}" --python "${SYSTEM_PYTHON}" 2>/dev/null || uv venv "${VENV_DIR}" 2>/dev/null
  elif [[ -f "${SYSTEM_PYTHON}" ]] && "${SYSTEM_PYTHON}" -m venv --help > /dev/null 2>&1; then
    info "使用 python3 -m venv 创建虚拟环境"
    "${SYSTEM_PYTHON}" -m venv "${VENV_DIR}"
  else
    error "无法创建虚拟环境（请安装 uv 或确保 python3 -m venv 可用）"
    exit 1
  fi

  if ! check_venv; then
    error "虚拟环境创建失败"
    exit 1
  fi
  info "虚拟环境创建成功: ${VENV_DIR}"
fi
echo ""

# ──────────────────────────────────────────────
# Step 5: 处理 Node.js（存在则检查可用性，缺失则安装）
# ──────────────────────────────────────────────
echo "[5/8] 处理 Node.js ..."
NODE_DIR="${TOOL_DIR}/.node"

NODE_OK=0
if [[ -d "${NODE_DIR}/installs/node" ]]; then
  NODE_BIN=$(find "${NODE_DIR}/installs/node" -type d -name 'bin' 2>/dev/null | head -1)
  if [[ -n "${NODE_BIN}" ]] && "${NODE_BIN}/node" --version > /dev/null 2>&1; then
    info "Node.js 已安装: ${NODE_BIN}/node $("${NODE_BIN}/node" --version 2>&1)"
    NODE_OK=1
  fi
fi

if [[ "${NODE_OK}" == "0" ]]; then
  if command -v mise > /dev/null 2>&1; then
    info "安装 Node.js 到项目本地..."
    if MISE_DATA_DIR="${NODE_DIR}" mise install node@22 2>/dev/null; then
      NODE_BIN=$(find "${NODE_DIR}/installs/node" -type d -name 'bin' 2>/dev/null | head -1)
      info "Node.js 安装成功: ${NODE_BIN}/node $("${NODE_BIN}/node" --version 2>&1)"
      NODE_OK=1
    else
      warn "Node.js 安装失败，yt-dlp 可能无法解密部分视频"
    fi
  else
    warn "未找到 mise，跳过 Node.js 安装"
  fi
fi
echo ""

# ──────────────────────────────────────────────
# Step 6: 安装 ffmpeg + ffprobe 到项目本地 .ffmpeg/
# ──────────────────────────────────────────────
echo "[6/8] 安装 ffmpeg + ffprobe ..."
FFMPEG_DIR="${TOOL_DIR}/.ffmpeg"
mkdir -p "${FFMPEG_DIR}/bin"

# 优先用系统已有的
check_ffmpeg() {
  local name="$1"
  if command -v "${name}" > /dev/null 2>&1; then
    info "${name} 已安装: $(command -v "${name}")"
    return 0
  fi
  if [[ -x "${FFMPEG_DIR}/bin/${name}" ]]; then
    info "${name} 已安装: ${FFMPEG_DIR}/bin/${name}"
    return 0
  fi
  return 1
}

download_ffmpeg_pkg() {
  local name="$1"

  check_ffmpeg "${name}" && return 0

  case "$(uname -s)" in
    Darwin)
      local url="https://evermeet.cx/ffmpeg/getrelease/${name}/zip"
      local dest="${FFMPEG_DIR}/${name}.zip"
      info "下载 macOS 版 ${name}..."
      if command -v curl > /dev/null 2>&1; then
        if curl -sL "${url}" -o "${dest}" 2>/dev/null; then
          unzip -o "${dest}" -d "${FFMPEG_DIR}/bin/" 2>/dev/null
          chmod +x "${FFMPEG_DIR}/bin/${name}"
          rm -f "${dest}"
          info "${name} 安装成功"
          return 0
        fi
      fi
      ;;

    Linux)
      # 静态构建 from johnvansickle.com（包含 ffmpeg ffprobe）
      local url="https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-64-static.tar.xz"
      info "下载 Linux 版 ${name} (静态构建)..."
      if command -v curl > /dev/null 2>&1 && command -v tar > /dev/null 2>&1; then
        local tarball="${FFMPEG_DIR}/ffmpeg-static.tar.xz"
        if curl -sL "${url}" -o "${tarball}" 2>/dev/null; then
          tar -xJf "${tarball}" --wildcards "*/${name}" --strip-components=1 -C "${FFMPEG_DIR}/bin/" 2>/dev/null
          chmod +x "${FFMPEG_DIR}/bin/${name}"
          rm -f "${tarball}"
          info "${name} 安装成功"
          return 0
        fi
      fi
      ;;

    CYGWIN*|MINGW*|MSYS*|Windows*)
      if command -v winget > /dev/null 2>&1; then
        info "使用 winget 安装 ffmpeg ..."
        winget install --id=Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements 2>/dev/null && return 0
      fi
      warn "Windows 建议手动安装: https://github.com/BtbN/FFmpeg-Builds"
      ;;
  esac

  warn "${name} 下载失败，yt-dlp 仍可尝试使用系统命令"
  return 1
}

download_ffmpeg_pkg ffmpeg
download_ffmpeg_pkg ffprobe
echo ""

# ──────────────────────────────────────────────
# Step 7: 安装 Python 依赖到 .venv
# ──────────────────────────────────────────────
echo "[7/8] 安装 Python 依赖..."

VENV_PY="${VENV_DIR}/bin/python"

# uv pip 更快，且用 --no-build-isolation 避免源码编译 llvmlite
if command -v uv > /dev/null 2>&1; then
  info "使用 uv 安装依赖..."
  # 核心依赖组合：torch/llvmlite/numba 版本约束避免源码编译
  if uv pip install --python "${VENV_PY}" \
    "torch<2.3.0" "llvmlite<0.44.0" "numba<0.60.0" \
    yt-dlp yt-dlp-ejs pyyaml openai-whisper \
    --no-build-isolation 2>/dev/null; then
    info "所有依赖安装成功"
  else
    warn "部分依赖安装失败，请手动检查"
  fi
else
  # 传统 pip（无 uv 时）
  VENV_PIP="${VENV_DIR}/bin/pip"
  "${VENV_PIP}" install --upgrade pip setuptools wheel 2>/dev/null || true
  if "${VENV_PIP}" install \
    "torch<2.3.0" "llvmlite<0.44.0" "numba<0.60.0" \
    yt-dlp yt-dlp-ejs pyyaml openai-whisper \
    --no-build-isolation 2>/dev/null; then
    info "所有依赖安装成功"
  else
    warn "部分依赖安装失败，请手动检查"
  fi
fi
echo ""

# ──────────────────────────────────────────────
# Step 8: 生成 launcher 脚本（指向 .venv，带本地 Node.js + ffprobe）
# ──────────────────────────────────────────────
echo "[8/8] 安装命令..."

# .venv python 固定路径（各平台通用写法，最可靠）
# Windows: VENV_DIR/Scripts/python.exe
# Linux/macOS: VENV_DIR/bin/python
case "$(uname -s)" in
  CYGWIN*|MINGW*|MSYS*|Windows*)  VENV_PYTHON="${VENV_DIR}/Scripts/python.exe" ;;
  *)                              VENV_PYTHON="${VENV_DIR}/bin/python" ;;
esac

info "虚拟环境 Python: ${VENV_PYTHON}"

for name in ytdl-cli ytdl-aicli ytdl-webui; do
  case "${name}" in
    ytdl-cli)   script="cli.py" ;;
    ytdl-aicli) script="aicrobot.py" ;;
    ytdl-webui) script="web_ui.py" ;;
  esac

  # 动态查找 .node 目录中实际安装的 node 版本（不用 mise shim）
  # 并将 .ffmpeg/bin 加入 PATH（ffprobe 所在）
  cat > "${BIN_DIR}/${name}" << EOF
#!/bin/bash
# 启用项目本地的 Node.js 和 FFmpeg（yt-dlp EJS 解密 + 音视频处理）
NODE_BIN_DIR="\$(find "${TOOL_DIR}/.node/installs/node" -type d -name 'bin' 2>/dev/null | head -1)"
FFMPEG_BIN_DIR="${TOOL_DIR}/.ffmpeg/bin"
if [[ -n "\${NODE_BIN_DIR}" ]]; then
  export PATH="\${NODE_BIN_DIR}:\${FFMPEG_BIN_DIR}:\${PATH}"
else
  export PATH="\${FFMPEG_BIN_DIR}:\${PATH}"
fi
exec "${VENV_PYTHON}" "${TOOL_DIR}/${script}" "\$@"
EOF
  chmod +x "${BIN_DIR}/${name}"
  info "  安装: ${name}"
done

echo ""

# ──────────────────────────────────────────────
# 完成
# ──────────────────────────────────────────────
echo "=================================="
echo "${GREEN}✅ 安装完成!${RESET}"
echo "=================================="
echo ""
echo "命令:"
echo "  ytdl-cli   URL   # 交互式 CLI"
echo "  ytdl-aicli URL   # AI 模式"
echo "  ytdl-webui       # Web UI"
echo ""
echo "虚拟环境: ${VENV_DIR}"
echo "  • 不依赖系统 Python，跨系统兼容"
echo "  • 再次运行 install.sh 会自动检查并跳过可用环境"
echo "  • 如需重装依赖: ${VENV_DIR}/bin/pip install -r requirements.txt"
echo ""
echo "Node.js: ${NODE_DIR}/installs/node/22.22.2/"
echo "  • 项目本地携带，不依赖系统 Node.js"
echo ""
echo "ffprobe: ${FFMPEG_DIR}/bin/ffprobe"
echo "  • 项目本地携带，解决 whisper 音视频处理依赖"
echo ""
echo "卸载: bash install.sh --uninstall"
