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
    implementation = patch_root / 'tools/apply_private_exact_playable_search_fix.py'
    subprocess.run([sys.executable, str(implementation), '--root', str(target)], check=True)

    # The retained-result namespace is intentionally upgraded so fuzzy,
    # metadata-only v2 rows are not reused by the exact-playable picker.
    checks_path = target / 'scripts/check_feature_requirements.py'
    checks = checks_path.read_text(encoding='utf-8')
    checks = checks.replace(
        "and 'song_version_directory_v2' in picker",
        "and 'song_version_directory_v4_exact_playable' in picker",
    )
    checks_path.write_text(checks, encoding='utf-8')

    subprocess.run(['git', '-C', str(target), 'config', 'user.name',
                    'github-actions[bot]'], check=True)
    subprocess.run(['git', '-C', str(target), 'config', 'user.email',
                    '41898282+github-actions[bot]@users.noreply.github.com'], check=True)
    code_paths = [
        'app/build.gradle',
        'app/src/main/java/com/jianglab/babywife/CatalogSearch.java',
        'app/src/main/java/com/jianglab/babywife/MainActivity.java',
        'app/src/main/java/com/jianglab/babywife/NetworkMediaCache.java',
        'app/src/main/java/com/jianglab/babywife/PlaybackControlService.java',
        'app/src/main/java/com/jianglab/babywife/SearchPriorityCoordinator.java',
        'app/src/main/java/com/jianglab/babywife/SongVersionPicker.java',
        'scripts/check_feature_requirements.py',
        'PROJECT_LOG.md',
        'docs/CHANGELOG.md',
    ]
    subprocess.run(['git', '-C', str(target), 'add', *code_paths], check=True)
    subprocess.run(['git', '-C', str(target), 'diff', '--cached', '--check'], check=True)
    subprocess.run(['git', '-C', str(target), 'commit', '-m',
                    'Filter manual search to exact playable results'], check=True)
    print('legacy_build_entry=private_exact_playable_manual_search')


if __name__ == '__main__':
    main()
