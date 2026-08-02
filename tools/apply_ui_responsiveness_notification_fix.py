#!/usr/bin/env python3
from pathlib import Path
import argparse
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='.')
    args = parser.parse_args()
    patch_root = Path(__file__).resolve().parents[1]
    target = Path(args.root).resolve()
    implementation = patch_root / 'tools/apply_startup_anr_ui_feedback_fix.py'
    subprocess.run([sys.executable, str(implementation), '--root', str(target)], check=True)
    print('legacy_build_entry=startup_anr_ui_feedback')


if __name__ == '__main__':
    main()
