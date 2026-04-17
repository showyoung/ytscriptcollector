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

$GREEN  = if ($Host.Name -eq "ConsoleHost") { "`e[92m" } else { "" }
$YELLOW = if ($Host.Name -eq "ConsoleHost") { "`e[93m" } else { "" }
$RED    = if ($Host.Name -eq "ConsoleHost") { "`e[91m" } else { "" }
$RESET  = if ($Host.Name -eq "ConsoleHost") { "`e[0m" } else { "" }

function Write-Info  { Write-Host "   ${GREEN}OK${RESET} $args" }
function Write-Warn  { Write-Host "   ${YELLOW}WARN${RESET} $args" }
function Write-Error { Write-Host "   ${RED}FAIL${RESET} $args" }

# ------------------------------------------------------------
# 卸载
# ------------------------------------------------------------
if ($Uninstall) {
    Write-Host "=================================="
    Write-Host "YouTube 脚本采集器 - 卸载"
    Write-Host "=================================="
    Write-Host ""

    foreach ($name in @("ytdl-cli", "ytdl-aicli", "ytdl-webui")) {
        $bat = Join-Path $BinDir "$name.bat"
        if (Test-Path $bat) {
            Remove-Item $bat -Force
            Write-Host "  Delete: $bat"
        }
    }

    Write-Host ""
    Write-Host "  Delete project data:"

    if (Test-Path $VenvDir) {
        Remove-Item $VenvDir -Recurse -Force
        Write-Host "  Delete: $VenvDir"
    }

    $nodeDir = Join-Path $ToolDir ".node"
    if (Test-Path $nodeDir) {
        Remove-Item $nodeDir -Recurse -Force
        Write-Host "  Delete: $nodeDir"
    }

    if (Test-Path $FfmpegDir) {
        Remove-Item $FfmpegDir -Recurse -Force
        Write-Host "  Delete: $FfmpegDir"
    }

    Write-Info "Done"
    exit 0
}

# ------------------------------------------------------------
# Banner
# ------------------------------------------------------------
Write-Host "=================================="
Write-Host "YouTube 脚本采集器 - 安装程序 (Windows)"
Write-Host "=================================="
Write-Host ""
Write-Host "  Tool dir: $ToolDir"
Write-Host "  Bin dir: $BinDir"
Write-Host ""

# ------------------------------------------------------------
# Step 1: 创建命令目录 + 设置 PATH
# ------------------------------------------------------------
Write-Host "[1/7] Create bin dir & set PATH..."
New-Item -ItemType Directory -Path $BinDir -Force | Out-Null

# 把 ~/.local/bin 加入用户 PATH（永久有效）
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$BinDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$BinDir", "User")
    Write-Info "Added $BinDir to user PATH (needs new terminal to take effect)"
} else {
    Write-Info "PATH already contains bin dir"
}
# 当前 session 也加上（安装完立即可用）
$env:Path = "$BinDir;$env:Path"
Write-Info "Done"
Write-Host ""

# ------------------------------------------------------------
# Step 2: 检查工具文件
# ------------------------------------------------------------
Write-Host "[2/7] Check tool files..."
foreach ($f in @("cli.py", "collector.py")) {
    $path = Join-Path $ToolDir $f
    if (-not (Test-Path $path)) {
        Write-Error "Not found: $f"
        exit 1
    }
}
Write-Info "Done"
Write-Host ""

# ------------------------------------------------------------
# Step 3: 查找系统 Python
# ------------------------------------------------------------
Write-Host "[3/7] Find Python..."

$python = $null
foreach ($cmd in @("python3", "python", "py")) {
    try {
        $output = & $cmd --version 2>&1
        if ($LASTEXITCODE -eq 0 -and $output -match "Python (\d+)\.(\d+)") {
            $python = $cmd
            break
        }
    } catch { continue }
}

if (-not $python) {
    Write-Error "Python 3.9+ not found. Download: https://www.python.org/downloads"
    exit 1
}

$ver = & $python --version 2>&1
if ($ver -match "Python (\d+)\.(\d+)" -and ([int]$Matches[1] -lt 3 -or ([int]$Matches[1] -eq 3 -and [int]$Matches[2] -lt 9))) {
    Write-Error "Python too old (need >= 3.9): $ver"
    exit 1
}

Write-Info "Found: $ver"
Write-Host ""

# ------------------------------------------------------------
# Step 4: 处理 .venv
# ------------------------------------------------------------
Write-Host "[4/7] Handle .venv..."

$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

function Test-Venv {
    if (Test-Path $VenvPython) {
        try {
            $null = & $VenvPython --version 2>&1
            if ($LASTEXITCODE -eq 0) { return $true }
        } catch { }
    }
    return $false
}

$recreate = $false
if (Test-Path $VenvDir) {
    if (Test-Venv) {
        Write-Info ".venv OK, skip"
    } else {
        Write-Warn ".venv broken, recreate..."
        Remove-Item $VenvDir -Recurse -Force
        $recreate = $true
    }
} else {
    $recreate = $true
}

if ($recreate) {
    try {
        & $python -m venv $VenvDir
        if (-not (Test-Venv)) {
            Write-Error ".venv create failed"
            exit 1
        }
        Write-Info ".venv created"
    } catch {
        Write-Error ".venv create failed: $_"
        exit 1
    }
}
Write-Host ""

# ------------------------------------------------------------
# Step 5: 处理 ffmpeg
# ------------------------------------------------------------
Write-Host "[5/7] Handle ffmpeg..."
$FfmpegBin = Join-Path $FfmpegDir "bin"
New-Item -ItemType Directory -Path $FfmpegBin -Force | Out-Null

function Test-Binary {
    param([string]$name)
    if (Get-Command $name -ErrorAction SilentlyContinue) { return $true }
    $path = Join-Path $FfmpegBin "$name.exe"
    if ((Test-Path $path) -and (Get-Item $path).Length -gt 0) { return $true }
    return $false
}

# BtbN FFmpeg Builds (GitHub Actions, 包含 ffmpeg + ffprobe)
$ffmpegZipUrl = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"

foreach ($tool in @("ffmpeg", "ffprobe")) {
    if (Test-Binary $tool) {
        Write-Info "$tool OK"
        continue
    }

    Write-Info "Download $tool..."
    $zipPath = Join-Path $env:TEMP "ffmpeg.zip"

    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $ffmpegZipUrl -OutFile $zipPath -UseBasicParsing
        Expand-Archive -Path $zipPath -DestinationPath $FfmpegBin -Force

        # BtbN zip 结构: ffmpeg-master-latest-win64-gpl/bin/ffmpeg.exe
        Get-ChildItem $FfmpegBin -Recurse -Filter "$tool.exe" |
            Move-Item -Destination $FfmpegBin -Force

        Remove-Item $zipPath -Force
        Write-Info "$tool installed"
    } catch {
        Write-Warn "$tool download failed: $_"
    }
}
Write-Host ""

# ------------------------------------------------------------
# Step 6: 安装 Python 依赖
# ------------------------------------------------------------
Write-Host "[6/7] Install Python packages..."

$VenvPip = Join-Path $VenvDir "Scripts\pip.exe"

Write-Info "Upgrade pip/setuptools/wheel..."
& $VenvPip install --upgrade pip setuptools wheel

Write-Info "Install packages..."
& $VenvPip install `
    "torch<2.3.0" "llvmlite<0.44.0" "numba<0.60.0" `
    "yt-dlp>=2024.1.1" "yt-dlp-ejs>=0.8.0" `
    "pyyaml>=6.0" "openai-whisper>=20231117" `
    --no-build-isolation

Write-Info "Done"
Write-Host ""

# ------------------------------------------------------------
# Step 7: 生成 launcher 脚本
# ------------------------------------------------------------
Write-Host "[7/7] Install commands..."

$VenvPy = $VenvPython

Write-Info "venv Python: $VenvPy"

$scripts = @{
    "ytdl-cli"   = "cli.py"
    "ytdl-aicli" = "aicrobot.py"
    "ytdl-webui" = "web_ui.py"
}

foreach ($name in $scripts.Keys) {
    $batPath = Join-Path $BinDir "$name.bat"
    $pyScript = $scripts[$name]

    $content = "@echo off`n"
    $content += "set PATH=$FfmpegBin;%PATH%`n"
    $content += """$VenvPy"" ""$ToolDir\$pyScript"" %*`n"

    Set-Content -Path $batPath -Value $content -Encoding ASCII
    Write-Info "  $batPath"
}
Write-Host ""

# ------------------------------------------------------------
# 完成
# ------------------------------------------------------------
Write-Host "=================================="
Write-Host "DONE"
Write-Host "=================================="
Write-Host ""
Write-Host "Commands (run anywhere):"
Write-Host "  ytdl-cli   <URL>   # CLI"
Write-Host "  ytdl-aicli <URL>   # AI mode"
Write-Host "  ytdl-webui        # Web UI"
Write-Host ""
Write-Host "NOTE: Open a NEW terminal window before using the commands."
Write-Host ""
Write-Host "Uninstall:"
Write-Host "  powershell -ExecutionPolicy Bypass -File `"$ToolDir\install.ps1`" -Uninstall"
