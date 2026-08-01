#!/usr/bin/env python3
from pathlib import Path
import argparse
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='.')
    args = parser.parse_args()
    patch_repo = Path(__file__).resolve().parents[1]
    target_root = Path(args.root).resolve()
    implementation = patch_repo / 'tools/apply_low_priority_resilient_batch_fix.py'
    subprocess.run(
        [sys.executable, str(implementation), '--root', str(target_root)],
        check=True,
    )

    # The legacy workflow's explicit git-add list predates NetworkMediaCache.java.
    # Commit that one file locally here; the workflow will commit the remaining
    # verified files and push both commits only after checks and APK builds pass.
    subprocess.run(['git', '-C', str(target_root), 'config', 'user.name',
                    'github-actions[bot]'], check=True)
    subprocess.run(['git', '-C', str(target_root), 'config', 'user.email',
                    '41898282+github-actions[bot]@users.noreply.github.com'], check=True)
    subprocess.run(['git', '-C', str(target_root), 'add',
                    'app/src/main/java/com/jianglab/babywife/NetworkMediaCache.java'], check=True)
    subprocess.run(['git', '-C', str(target_root), 'diff', '--cached', '--check'], check=True)
    subprocess.run(['git', '-C', str(target_root), 'commit', '-m',
                    'Add foreground priority coordination for media cache'], check=True)
    print('legacy_build_entry=playback_priority_resilient_batch')


if __name__ == '__main__':
    main()
