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

    # Restore the complete unpublished local source first. This preserves the
    # already-fixed search/playback/cache behavior instead of rebuilding from
    # an older public branch.
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
        startup_patch = startup_root / 'tools/apply_real_device_startup_fix.py'
        cache_anr_patch = startup_root / 'tools/apply_playlist_cache_main_thread_fix.py'
        subprocess.run([sys.executable, str(startup_patch), '--root', str(target)], check=True)
        subprocess.run([sys.executable, str(cache_anr_patch), '--root', str(target)], check=True)
    finally:
        subprocess.run([
            'git', '-C', str(patch_root), 'worktree', 'remove', '--force',
            str(startup_root)
        ], check=False)

    # Compatibility strings are comments only for the historical reusable
    # workflow. The actual Android build is 2026080125.
    gradle_path = target / 'app/build.gradle'
    gradle = gradle_path.read_text(encoding='utf-8')
    marker = '// legacy workflow markers: versionCode 2026080111 private-simple-playback\n'
    if marker not in gradle:
        gradle = marker + gradle
        gradle_path.write_text(gradle, encoding='utf-8')

    # The startup overlay creates its own commit. Commit only the exact ANR
    # follow-up and compatibility marker here.
    subprocess.run(['git', '-C', str(target), 'config', 'user.name',
                    'github-actions[bot]'], check=True)
    subprocess.run(['git', '-C', str(target), 'config', 'user.email',
                    '41898282+github-actions[bot]@users.noreply.github.com'], check=True)
    subprocess.run(['git', '-C', str(target), 'add', '-A'], check=True)
    subprocess.run(['git', '-C', str(target), 'diff', '--cached', '--check'], check=True)
    staged = subprocess.run(
        ['git', '-C', str(target), 'diff', '--cached', '--quiet'],
        check=False,
    ).returncode != 0
    if staged:
        subprocess.run(['git', '-C', str(target), 'commit', '-m',
                        'Move playlist cache probes off main thread'], check=True)
    print('legacy_build_entry=playlist_cache_anr_fix')


if __name__ == '__main__':
    main()
