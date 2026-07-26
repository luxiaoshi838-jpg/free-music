$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$Gradle = Get-Command gradle -ErrorAction SilentlyContinue
if (-not $Gradle) {
    throw "首次初始化需要安装 Gradle 8.7 并加入 PATH。完成后再次运行本脚本。"
}
& $Gradle.Source wrapper --gradle-version 8.7 --distribution-type bin
if ($LASTEXITCODE -ne 0) { throw "Gradle Wrapper 初始化失败。" }
Write-Host "已生成 gradlew、gradlew.bat 和 gradle/wrapper 文件。"
