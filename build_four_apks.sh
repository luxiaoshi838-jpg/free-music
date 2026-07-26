#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [ -x ./gradlew ]; then
  gradle_cmd=./gradlew
elif command -v gradle >/dev/null 2>&1; then
  gradle_cmd=gradle
else
  echo "未找到 ./gradlew 或 Gradle。请先运行 ./init_gradle_wrapper.sh。" >&2
  exit 1
fi

log="四品牌构建.log"
err="四品牌构建.log.err"
: > "$log"
: > "$err"
"$gradle_cmd" --no-daemon \
  assembleBabywifeclassicDebug \
  assembleLidacaizhuDebug \
  assembleJianglabDebug \
  assembleNiubiDebug >"$log" 2>"$err" &
pid=$!
last=-1
idle=0
while kill -0 "$pid" 2>/dev/null; do
  sleep 60
  size=$(( $(wc -c < "$log") + $(wc -c < "$err") ))
  if [ "$size" -eq "$last" ]; then idle=$((idle+1)); else idle=0; last=$size; fi
  echo "构建检查：已连续 ${idle} 分钟无新增日志"
  if [ "$idle" -ge 5 ]; then
    kill "$pid" 2>/dev/null || true
    wait "$pid" || true
    echo "构建连续五分钟没有新增日志，已停止。" >&2
    exit 124
  fi
done
wait "$pid"

mkdir -p 本地构建输出
cp app/build/outputs/apk/babywifeclassic/debug/app-babywifeclassic-debug.apk 本地构建输出/大宝贝儿老婆.apk
cp app/build/outputs/apk/lidacaizhu/debug/app-lidacaizhu-debug.apk 本地构建输出/李大财主.apk
cp app/build/outputs/apk/jianglab/debug/app-jianglab-debug.apk 本地构建输出/姜Lab.apk
cp app/build/outputs/apk/niubi/debug/app-niubi-debug.apk 本地构建输出/牛逼.apk
sha256sum 本地构建输出/*.apk > 本地构建输出/SHA256.txt
echo "四个 APK 已生成：$(pwd)/本地构建输出"
