#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import selectors
import signal
import subprocess
import sys
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stop a command after prolonged output silence.")
    parser.add_argument("--silence-seconds", type=int, default=300)
    parser.add_argument("--log", default="build/watchdog-command.log")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command and args.command[0] == "--":
        args.command = args.command[1:]
    if not args.command:
        parser.error("a command is required after --")
    return args


def terminate_tree(process: subprocess.Popen[bytes]) -> None:
    try:
        if os.name == "nt":
            process.terminate()
        else:
            os.killpg(process.pid, signal.SIGTERM)
    except Exception:
        pass
    try:
        process.wait(timeout=10)
    except Exception:
        try:
            if os.name == "nt":
                process.kill()
            else:
                os.killpg(process.pid, signal.SIGKILL)
        except Exception:
            pass


def main() -> int:
    args = parse_args()
    log_path = Path(args.log)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    process = subprocess.Popen(
        args.command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=0,
        start_new_session=os.name != "nt",
        creationflags=creationflags,
    )
    assert process.stdout is not None
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    last_output = time.monotonic()
    with log_path.open("wb") as log:
        while True:
            events = selector.select(timeout=1.0)
            if events:
                chunk = process.stdout.read1(65536) if hasattr(process.stdout, "read1") else process.stdout.read(65536)
                if chunk:
                    last_output = time.monotonic()
                    sys.stdout.buffer.write(chunk)
                    sys.stdout.buffer.flush()
                    log.write(chunk)
                    log.flush()
            exit_code = process.poll()
            if exit_code is not None:
                remainder = process.stdout.read()
                if remainder:
                    sys.stdout.buffer.write(remainder)
                    sys.stdout.buffer.flush()
                    log.write(remainder)
                return exit_code
            silence = time.monotonic() - last_output
            if silence >= args.silence_seconds:
                message = (
                    f"\nWATCHDOG_STOP: command produced no output for "
                    f"{args.silence_seconds} seconds: {' '.join(args.command)}\n"
                ).encode("utf-8")
                sys.stderr.buffer.write(message)
                log.write(message)
                terminate_tree(process)
                return 124


if __name__ == "__main__":
    raise SystemExit(main())
