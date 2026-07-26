$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$Wrapper = Join-Path $Root "gradlew.bat"
if (Test-Path $Wrapper) {
    $GradleCommand = $Wrapper
} else {
    $Gradle = Get-Command gradle -ErrorAction SilentlyContinue
    if (-not $Gradle) {
        throw "未找到 gradlew.bat 或 Gradle。请先运行 .\初始化GradleWrapper.ps1，或安装 Gradle 8.7。"
    }
    $GradleCommand = $Gradle.Source
}


$PrivateProperties = Join-Path $Root "private.properties"
if ([string]::IsNullOrWhiteSpace($env:JIANG_LAB_PASSPHRASE_SHA256) -and (Test-Path $PrivateProperties)) {
    $Line = Get-Content $PrivateProperties -Encoding UTF8 |
        Where-Object { $_ -match '^\s*JIANG_LAB_PASSPHRASE_SHA256\s*=' } |
        Select-Object -First 1
    if ($Line) {
        $env:JIANG_LAB_PASSPHRASE_SHA256 = ($Line -split '=', 2)[1].Trim()
    }
}
if ($env:JIANG_LAB_PASSPHRASE_SHA256 -notmatch '^[0-9a-fA-F]{64}$') {
    throw "姜Lab 首次验证哈希未配置。先运行 python scripts/generate_jianglab_passphrase_hash.py，并把结果写入 private.properties。"
}

$Log = Join-Path $Root "四品牌构建.log"
$Output = Join-Path $Root "本地构建输出"
New-Item -ItemType Directory -Force -Path $Output | Out-Null

$Arguments = @(
    "--no-daemon",
    "assembleBabywifeclassicDebug",
    "assembleLidacaizhuDebug",
    "assembleJianglabDebug",
    "assembleNiubiDebug"
)

$Process = Start-Process -FilePath $GradleCommand -ArgumentList $Arguments -NoNewWindow -PassThru `
    -RedirectStandardOutput $Log -RedirectStandardError "$Log.err"

$LastLength = -1
$IdleMinutes = 0
while (-not $Process.HasExited) {
    Start-Sleep -Seconds 60
    $Length = 0
    if (Test-Path $Log) { $Length += (Get-Item $Log).Length }
    if (Test-Path "$Log.err") { $Length += (Get-Item "$Log.err").Length }
    if ($Length -eq $LastLength) { $IdleMinutes++ } else { $IdleMinutes = 0; $LastLength = $Length }
    Write-Host "构建检查：已连续 $IdleMinutes 分钟无新增日志"
    if ($IdleMinutes -ge 5) {
        Stop-Process -Id $Process.Id -Force
        throw "构建连续五分钟没有新增日志，已停止。请查看四品牌构建.log和四品牌构建.log.err。"
    }
}

if ($Process.ExitCode -ne 0) {
    throw "Gradle 构建失败，退出码：$($Process.ExitCode)。请查看构建日志。"
}

$Mapping = @{
    "app\build\outputs\apk\babywifeclassic\debug\app-babywifeclassic-debug.apk" = "大宝贝儿老婆.apk"
    "app\build\outputs\apk\lidacaizhu\debug\app-lidacaizhu-debug.apk" = "李大财主.apk"
    "app\build\outputs\apk\jianglab\debug\app-jianglab-debug.apk" = "姜Lab.apk"
    "app\build\outputs\apk\niubi\debug\app-niubi-debug.apk" = "牛逼.apk"
}

foreach ($Source in $Mapping.Keys) {
    if (-not (Test-Path $Source)) { throw "缺少构建产物：$Source" }
    Copy-Item $Source (Join-Path $Output $Mapping[$Source]) -Force
}

Get-ChildItem $Output -Filter *.apk | Get-FileHash -Algorithm SHA256 |
    Format-Table Path, Hash -AutoSize | Out-String | Set-Content (Join-Path $Output "SHA256.txt") -Encoding UTF8

Write-Host "四个 APK 已生成：$Output"
