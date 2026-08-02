#!/usr/bin/env python3
# Build trigger: remove the remaining pre-download playback gate.
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
    implementation = patch_root / 'tools/apply_instant_stream_playback_fix.py'
    subprocess.run([sys.executable, str(implementation), '--root', str(target)], check=True)

    subprocess.run(['git', '-C', str(target), 'config', 'user.name',
                    'github-actions[bot]'], check=True)
    subprocess.run(['git', '-C', str(target), 'config', 'user.email',
                    '41898282+github-actions[bot]@users.noreply.github.com'], check=True)
    code_paths = [
        'app/build.gradle',
        'app/src/main/java/com/jianglab/babywife/CatalogSearch.java',
        'app/src/main/java/com/jianglab/babywife/MainActivity.java',
        'app/src/main/java/com/jianglab/babywife/NetworkMediaCache.java',
        'scripts/check_feature_requirements.py',
        'PROJECT_LOG.md',
        'docs/CHANGELOG.md',
    ]
    subprocess.run(['git', '-C', str(target), 'add', *code_paths], check=True)
    subprocess.run(['git', '-C', str(target), 'diff', '--cached', '--check'], check=True)
    subprocess.run(['git', '-C', str(target), 'commit', '-m',
                    'Start network playback before full caching'], check=True)
    print('legacy_build_entry=instant_stream_playback')


if __name__ == '__main__':
    main()
