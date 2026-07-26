$ErrorActionPreference = "Stop"

$SourceProject = Split-Path -Parent $MyInvocation.MyCommand.Path
$WorkRoot = Join-Path $env:TEMP "babywife_apk_manual_build"
$Project = Join-Path $WorkRoot "project"
$Sdk = "D:\software\SDK"
$JavaHome = "D:\software\Andriod Studio\jbr"
$BuildTools = Join-Path $Sdk "build-tools\36.1.0"
$PlatformJar = Join-Path $Sdk "platforms\android-36.1\android.jar"
$App = Join-Path $Project "app"
$Build = Join-Path $Project "manual-build"
$CompiledRes = Join-Path $Build "compiled-res.zip"
$Gen = Join-Path $Build "generated"
$Classes = Join-Path $Build "classes"
$Dex = Join-Path $Build "dex"
$Out = Join-Path $App "build\outputs\apk\debug"
$Unsigned = Join-Path $Build "app-debug-unsigned.apk"
$Aligned = Join-Path $Build "app-debug-aligned.apk"
$Final = Join-Path $Out "app-debug.apk"
$Keystore = Join-Path $SourceProject "debug.keystore"
$SourceFinalDir = Join-Path $SourceProject "app\build\outputs\apk\debug"
$SourceFinal = Join-Path $SourceFinalDir "app-debug.apk"
$OutputDir = Join-Path $SourceProject "apk-output"

$env:JAVA_HOME = $JavaHome
$env:Path = (Join-Path $JavaHome "bin") + ";" + $env:Path

function Assert-LastExit([string] $Step) {
  if ($LASTEXITCODE -ne 0) {
    throw "$Step failed with exit code $LASTEXITCODE"
  }
}

if (Test-Path -LiteralPath $WorkRoot) {
  Remove-Item -LiteralPath $WorkRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $Project | Out-Null
Copy-Item -LiteralPath (Join-Path $SourceProject "app") -Destination $Project -Recurse -Force

New-Item -ItemType Directory -Force -Path $Build, $Gen, $Classes, $Dex, $Out | Out-Null
Remove-Item -LiteralPath $CompiledRes, $Unsigned, $Aligned, $Final -Force -ErrorAction SilentlyContinue
Get-ChildItem -LiteralPath $Classes -Recurse -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
Get-ChildItem -LiteralPath $Dex -Recurse -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force

& (Join-Path $BuildTools "aapt2.exe") compile --dir (Join-Path $App "src\main\res") -o $CompiledRes
Assert-LastExit "aapt2 compile"
& (Join-Path $BuildTools "aapt2.exe") link `
  -o $Unsigned `
  -I $PlatformJar `
  --manifest (Join-Path $App "src\main\AndroidManifest.xml") `
  -R $CompiledRes `
  --java $Gen `
  --min-sdk-version 23 `
  --target-sdk-version 35 `
  --version-code 1 `
  --version-name "1.0" `
  --auto-add-overlay
Assert-LastExit "aapt2 link"

$JavaSources = @(
  Join-Path $App "src\main\java\com\jianglab\babywife\MainActivity.java"
)
$GeneratedSources = Get-ChildItem -LiteralPath $Gen -Recurse -Filter *.java | ForEach-Object { $_.FullName }
$SourceList = Join-Path $Build "java-sources.txt"
($JavaSources + $GeneratedSources) | Set-Content -LiteralPath $SourceList -Encoding ASCII
& (Join-Path $JavaHome "bin\javac.exe") -encoding UTF-8 -source 17 -target 17 -classpath $PlatformJar -d $Classes "@$SourceList"
Assert-LastExit "javac"
$ClassFiles = @(Get-ChildItem -LiteralPath $Classes -Recurse -Filter *.class | ForEach-Object { $_.FullName })
if (!$ClassFiles.Count) {
  throw "javac produced no .class files"
}
& (Join-Path $BuildTools "d8.bat") --lib $PlatformJar --min-api 23 --output $Dex $ClassFiles
Assert-LastExit "d8"
& (Join-Path $JavaHome "bin\jar.exe") uf $Unsigned -C $Dex classes.dex
Assert-LastExit "jar update"
& (Join-Path $BuildTools "zipalign.exe") -f 4 $Unsigned $Aligned
Assert-LastExit "zipalign"

if (!(Test-Path -LiteralPath $Keystore)) {
  & (Join-Path $JavaHome "bin\keytool.exe") -genkeypair -v `
    -keystore $Keystore `
    -storepass android `
    -keypass android `
    -alias androiddebugkey `
    -keyalg RSA `
    -keysize 2048 `
    -validity 10000 `
    -dname "CN=Android Debug,O=Android,C=US"
  Assert-LastExit "keytool"
}

& (Join-Path $BuildTools "apksigner.bat") sign `
  --ks $Keystore `
  --ks-pass pass:android `
  --key-pass pass:android `
  --out $Final `
  $Aligned
Assert-LastExit "apksigner sign"

& (Join-Path $BuildTools "apksigner.bat") verify --verbose $Final
Assert-LastExit "apksigner verify"
New-Item -ItemType Directory -Force -Path $SourceFinalDir | Out-Null
Copy-Item -LiteralPath $Final -Destination $SourceFinal -Force
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$NamedOutput = Join-Path $OutputDir "babywife-$Timestamp.apk"
$LatestOutput = Join-Path $OutputDir "babywife-latest.apk"
Copy-Item -LiteralPath $Final -Destination $NamedOutput -Force
Copy-Item -LiteralPath $Final -Destination $LatestOutput -Force
Get-Item -LiteralPath $SourceFinal
Get-Item -LiteralPath $NamedOutput
