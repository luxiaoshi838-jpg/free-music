#!/usr/bin/env python3
from pathlib import Path
import argparse


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    root = Path(parser.parse_args().root).resolve()

    compat = (root / "app/src/main/java/com/jianglab/babywife/PlaybackCompatibility.java").read_text(encoding="utf-8")
    gradle = (root / "app/build.gradle").read_text(encoding="utf-8")

    required = [
        "MediaCodec.createByCodecName",
        "dequeueOutputBuffer",
        "outputInfo.size > 0",
        "decodeProbe(extractor, audioFormat, decoderName, 0L)",
        "decodeProbe(extractor, audioFormat, decoderName, seekTargetUs)",
    ]
    missing = [item for item in required if item not in compat]
    if missing:
        raise RuntimeError("real decoder validation missing: " + ", ".join(missing))
    if "versionCode 2026080104" not in gradle:
        raise RuntimeError("versionCode 2026080104 missing")

    print("source_patch=no_changes")
    print("real_media_codec_output_probe=present")
    print("start_and_mid_decode_probe=present")
    print("version_code=2026080104")


if __name__ == "__main__":
    main()
