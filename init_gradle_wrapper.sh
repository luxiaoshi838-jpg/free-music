#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if ! command -v gradle >/dev/null 2>&1; then
  echo "首次初始化需要安装 Gradle 8.7。" >&2
  exit 1
fi
gradle wrapper --gradle-version 8.7 --distribution-type bin
echo "Gradle Wrapper 已生成。"
