# YouTube 脚本采集器 - Windows 安装脚本
# 用法:
#   powershell -ExecutionPolicy Bypass -File install.ps1        # 安装
#   powershell -ExecutionPolicy Bypass -File install.ps1 -Uninstall  # 卸载

param(
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$ToolDir = $PSScriptRoot
$VenvDir = Join-Path $ToolDir ".venv"
$BinDir = "$env:USERPROFILE\.local\bin"
$FfmpegDir = Join-Path $ToolDir ".ffmpeg"

function Get-CdpColor {
    param([string]$Name)
    if ($Host.Name -eq "ConsoleHost") {
        $map = @{
            "GREEN"  = "`e[92m"
            "YELLOW" = "`e[93m"
            "RED"    = "`e[91m"
            "RESET"  = "`e[0m"
        }
        return $map[$Name]
    }
    return ""
}

$GREEN  = Get-CdpColor "GREEN"
$YELLOW = Get-CdpColor "YELLOW"
$RED    = Get-CdpColor "RED"
$RESET  = Get-CdpColor "RESET"

function Write-Info  { Write-Host "   ${GREEN}✅${RESET} $args" }
function Write-Warn  { Write-Host "   ${YELLOW}⚠️${RESET} $args" }
function Write-Error { Write-Host "   ${RED}❌${RESET} $args" }

# ──────────────────────────────────────────────
# 卸载
# ──────────────────────────────────────────────
if ($Uninstall) {
    Write-Host "==================================" -ForegroundColor Cyan
    Write-Host "YouTube 脚本采集器 - 卸载"
    Write-Host "=================================="
    Write-Host ""

    foreach ($name in @("ytdl-cli", "ytdl-aicli", "ytdl-webui")) {
        $target = Join-Path $BinDir "$name.bat"
        if (Test-Path $target) {
            Remove-Item $target -Force
            Write-Host "  删除: $target"
        }
    }

    Write-Host ""
    Write-Host "  删除项目数据:"
    if (Test-Path $VenvDir) {
        Remove-Item $VenvDir -Recurse -Force
        Write-Host "  删除: $VenvDir"
    }
    if (Test-Path (Join-Path $ToolDir ".node")) {
        Remove-Item (Join-Path $ToolDir ".node") -Recurse -Force
        Write-Host "  删除: (Join-Path $ToolDir ".node")"
    }
    if (Test-Path $FfmpegDir) {
        Remove-Item $FfmpegDir -Recurse -Force
        Write-Host "  删除: $FfmpegDir"
    }

    Write-Info "命令和数据已删除"
    Write-Host ""
    Write-Host "提示: 如需彻底删除工具，请手动删除目录:"
    Write-Host "  Remove-Item -Recurse '$ToolDir'"
    Write-Host ""
    exit 0
}

# ──────────────────────────────────────────────
# Banner
# ──────────────────────────────────────────────
Write-Host "==================================" -ForegroundColor Cyan
Write-Host "YouTube 脚本采集器 - 安装程序 (Windows)"
Write-Host "=================================="
Write-Host ""
Write-Host "  工具目录: $ToolDir"
Write-Host "  命令目录: $BinDir"
Write-Host ""

# ──────────────────────────────────────────────
# Step 1: 创建命令目录
# ──────────────────────────────────────────────
Write-Host "[1/7] 创建命令目录..."
New-Item -ItemType Directory -Path $BinDir -Force | Out-Null
Write-Info "命令目录就绪"
Write-Host ""

# ──────────────────────────────────────────────
# Step 2: 检查工具文件
# ──────────────────────────────────────────────
Write-Host "[2/7] 检查工具文件..."
foreach ($f in @("cli.py", "collector.py")) {
    $path = Join-Path $ToolDir $f
    if (-not (Test-Path $path)) {
        Write-Error "未找到: $f"
        exit 1
    }
}
Write-Info "工具文件就绪"
Write-Host ""

# ──────────────────────────────────────────────
# Step 3: 查找系统 Python
# ──────────────────────────────────────────────
Write-Host "[3/7] 查找系统 Python..."

$python = $null
foreach ($cmd in @("python3", "python", "py")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($LASTEXITCODE -eq 0 -and $ver -match "Python (\d+)\.(\d+)") {
            $python = $cmd
            break
        }
    } catch { continue }
}

if (-not $python) {
    Write-Error "未找到 Python3，请先安装 Python >= 3.9"
    Write-Host "  下载: https://www.python.org/downloads"
    exit 1
}

$ver = & $python --version 2>&1
if ($ver -match "Python (\d+)\.(\d+)" -and ([int]$Matches[1] -lt 3 -or ([int]$Matches[1] -eq 3 -and [int]$Matches[2] -lt 9))) {
    Write-Error "Python 版本过低（需要 >= 3.9）: $ver"
    exit 1
}

Write-Info "系统 Python: $ver"
Write-Host ""

# ──────────────────────────────────────────────
# Step 4: 处理 .venv
# ──────────────────────────────────────────────
Write-Host "[4/7] 处理虚拟环境 .venv..."

$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

function Test-Venv {
    if (Test-Path $VenvPython) {
        try {
            $result = & $VenvPython --version 2>&1
            if ($LASTEXITCODE -eq 0) { return $true }
        } catch { }
    }
    return $false
}

if (Test-Path $VenvDir) {
    if (Test-Venv) {
        Write-Info "虚拟环境已存在且可用: $VenvDir"
    } else {
        Write-Warn "虚拟环境损坏，删除并重新创建..."
        Remove-Item $VenvDir -Recurse -Force
        $recreate = $true
    }
} else {
    $recreate = $true
}

if ($recreate) {
    Write-Info "创建虚拟环境..."
    try {
        & $python -m venv $VenvDir
        if (-not (Test-Venv)) {
            Write-Error "虚拟环境创建失败"
            exit 1
        }
        Write-Info "虚拟环境创建成功: $VenvDir"
    } catch {
        Write-Error "虚拟环境创建失败: $_"
        exit 1
    }
}
Write-Host ""

# ──────────────────────────────────────────────
# Step 5: 处理 ffmpeg
# ──────────────────────────────────────────────
Write-Host "[5/7] 处理 ffmpeg..."
$ffmpegBin = Join-Path $FfmpegDir "bin"
New-Item -ItemType Directory -Path $ffmpegBin -Force | Out-Null

function Test-Binary {
    param([string]$name)
    if (Get-Command $name -ErrorAction SilentlyContinue) { return $true }
    $path = Join-Path $ffmpegBin $name
    if ((Test-Path $path) -and (Get-Item $path).Length -gt 0) { return $true }
    return $false
}

$ffmpegUrl = "https://github.com/GyanD/codexffmpeg/releases/download/refs/heads/master/ffmpeg-master-latest-win64-gpl.zip"
$ffprobeUrl = "https://github.com/GyanD/codexffmpeg/releases/download/refs/heads/master/ffprobe-master-latest-win64-gpl.zip"

foreach ($tool in @("ffmpeg", "ffprobe")) {
    if (Test-Binary $tool) {
        Write-Info "$tool 已安装"
        continue
    }

    Write-Info "下载 $tool..."
    $zipPath = Join-Path $env:TEMP "$tool.zip"
    $apiUrl = if ($tool -eq "ffmpeg") { $ffmpegUrl } else { $ffprobeUrl }

    try {
        # 尝试 BtbN GitHub Actions 构建（更小）
        $ghUrl = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $ghUrl -OutFile $zipPath -UseBasicParsing 2>$null

        if ((Test-Path $zipPath) -and (Get-Item $zipPath).Length -gt 0) {
            Expand-Archive -Path $zipPath -DestinationPath $ffmpegBin -Force
            # 解压后结构是 ffmpeg-master-latest-win64-gpl/bin/ffmpeg.exe
            Get-ChildItem $ffmpegBin -Recurse -Filter "$tool.exe" | Move-Item -Destination $ffmpegBin -Force
            Remove-Item $zipPath -Force
            Write-Info "$tool 安装成功"
        } else {
            throw "下载失败"
        }
    } catch {
        Write-Warn "$tool 下载失败，whisper 音视频处理可能受影响"
    }
}
Write-Host ""

# ──────────────────────────────────────────────
# Step 6: 安装 Python 依赖
# ──────────────────────────────────────────────
Write-Host "[6/7] 安装 Python 依赖..."

$VenvPip = Join-Path $VenvDir "Scripts\pip.exe"
$VenvPythonExe = $VenvPython

Write-Info "升级 pip..."
& $VenvPip install --upgrade pip setuptools wheel --quiet 2>$null

Write-Info "安装依赖（torch/llvmlite/numba 版本约束避免编译问题）..."
& $VenvPip install --quiet `
    "torch<2.3.0" "llvmlite<0.44.0" "numba<0.60.0" `
    "yt-dlp>=2024.1.1" "yt-dlp-ejs>=0.8.0" `
    "pyyaml>=6.0" "openai-whisper>=20231117" `
    --no-build-isolation 2>$null

Write-Info "所有依赖安装完成"
Write-Host ""

# ──────────────────────────────────────────────
# Step 7: 生成 launcher 脚本
# ──────────────────────────────────────────────
Write-Host "[7/7] 安装命令..."

$VenvPy = $VenvPythonExe

Write-Info "虚拟环境 Python: $VenvPy"

$scripts = @{
    "ytdl-cli"   = "cli.py"
    "ytdl-aicli" = "aicrobot.py"
    "ytdl-webui" = "web_ui.py"
}

foreach ($name in $scripts.Keys) {
    $batPath = Join-Path $BinDir "$name.bat"

    @"
@echo off
REM 启用项目本地的 FFmpeg（ffprobe 所在）
set "PATH=$ffmpegBin;%PATH%"
"$VenvPy" "$ToolDir\$($scripts[$name])" %*
"@ | Set-Content -Path $batPath -Encoding UTF8

    Write-Info "  安装: $batPath"
}

Write-Host ""

# ──────────────────────────────────────────────
# 完成
# ──────────────────────────────────────────────
Write-Host "==================================" -ForegroundColor Cyan
Write-Host "${GREEN}✅ 安装完成!${RESET}"
Write-Host "=================================="
Write-Host ""
Write-Host "命令（在任意目录运行）:"
Write-Host "  ytdl-cli   <URL>   # 交互式 CLI"
Write-Host "  ytdl-aicli <URL>   # AI 模式"
Write-Host "  ytdl-webui        # Web UI"
Write-Host ""
Write-Host "虚拟环境: $VenvDir"
Write-Host "  • 不依赖系统 Python"
Write-Host "  • 再次运行 install.ps1 会自动检查并跳过可用环境"
Write-Host ""
Write-Host "ffprobe: $ffmpegBin\ffprobe.exe"
Write-Host "  • 用于 whisper 音视频处理"
Write-Host ""
Write-Host "卸载: powershell -ExecutionPolicy Bypass -File `"$ToolDir\install.ps1`" -Uninstall"
