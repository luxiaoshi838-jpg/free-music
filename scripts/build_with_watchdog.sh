#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "Usage: $0 LOG_FILE COMMAND [ARG...]" >&2
  exit 2
fi

log_file=$1
shift
mkdir -p "$(dirname "$log_file")"
: > "$log_file"

# Run in its own process group so a stalled Gradle daemon and children can be stopped together.
setsid "$@" > >(tee -a "$log_file") 2>&1 &
pid=$!
last_size=0
unchanged_checks=0

while kill -0 "$pid" 2>/dev/null; do
  sleep 30
  current_size=$(stat -c %s "$log_file" 2>/dev/null || echo 0)
  if [ "$current_size" -gt "$last_size" ]; then
    last_size=$current_size
    unchanged_checks=0
  else
    unchanged_checks=$((unchanged_checks + 1))
  fi

  if [ "$unchanged_checks" -ge 10 ]; then
    echo "ERROR: no new build log for five minutes; stopping stalled step." | tee -a "$log_file"
    kill -TERM -- "-$pid" 2>/dev/null || true
    sleep 5
    kill -KILL -- "-$pid" 2>/dev/null || true
    wait "$pid" || true
    exit 124
  fi
done

wait "$pid"
