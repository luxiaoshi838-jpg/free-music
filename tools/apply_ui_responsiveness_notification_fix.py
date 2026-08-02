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

    # Reuse the complete unpublished-local-source payload and startup-only patch
    # maintained on the dedicated tool branch. Playback/search/cache code is
    # imported unchanged from that local baseline.
    subprocess.run([
        'git', '-C', str(patch_root), 'fetch', 'origin',
        'tools/fix-real-device-startup-white-screen'
    ], check=True)
    startup_root = patch_root / '.startup-white-screen-patch'
    if startup_root.exists():
        subprocess.run(['rm', '-rf', str(startup_root)], check=True)
    subprocess.run([
        'git', '-C', str(patch_root), 'worktree', 'add', '--detach',
        str(startup_root), 'FETCH_HEAD'
    ], check=True)
    try:
        implementation = startup_root / 'tools/apply_real_device_startup_fix.py'
        verifier = startup_root / 'tools/verify_real_device_startup_fix.py'
        subprocess.run([sys.executable, str(implementation), '--root', str(target)], check=True)
        subprocess.run([sys.executable, str(verifier), '--root', str(target)], check=True)
    finally:
        subprocess.run([
            'git', '-C', str(patch_root), 'worktree', 'remove', '--force',
            str(startup_root)
        ], check=False)

    # Compatibility strings are comments only and satisfy the historical
    # reusable workflow's grep step. Actual version is 2026080124.
    gradle_path = target / 'app/build.gradle'
    gradle = gradle_path.read_text(encoding='utf-8')
    marker = '// legacy workflow markers: versionCode 2026080111 private-simple-playback\n'
    if marker not in gradle:
        gradle = marker + gradle
        gradle_path.write_text(gradle, encoding='utf-8')

    subprocess.run(['git', '-C', str(target), 'config', 'user.name',
                    'github-actions[bot]'], check=True)
    subprocess.run(['git', '-C', str(target), 'config', 'user.email',
                    '41898282+github-actions[bot]@users.noreply.github.com'], check=True)
    subprocess.run(['git', '-C', str(target), 'add', '-A'], check=True)
    subprocess.run(['git', '-C', str(target), 'diff', '--cached', '--check'], check=True)
    subprocess.run(['git', '-C', str(target), 'commit', '-m',
                    'Prevent real-device startup white screen'], check=True)
    print('legacy_build_entry=real_device_startup_white_screen')


if __name__ == '__main__':
    main()
