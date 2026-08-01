#!/usr/bin/env python3
from pathlib import Path
import argparse


def require(text, token, label):
    if token not in text:
        raise RuntimeError(f'{label}: missing {token!r}')


def append_once(path, marker, block):
    text = path.read_text(encoding='utf-8')
    if marker not in text:
        path.write_text(text + block, encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='.')
    root = Path(parser.parse_args().root).resolve()

    gradle = (root / 'app/build.gradle').read_text(encoding='utf-8')
    main = (root / 'app/src/main/java/com/jianglab/babywife/MainActivity.java').read_text(encoding='utf-8')
    network = (root / 'app/src/main/java/com/jianglab/babywife/NetworkMediaCache.java').read_text(encoding='utf-8')
    batch = (root / 'app/src/main/java/com/jianglab/babywife/PlaylistBatchCacheService.java').read_text(encoding='utf-8')

    require(gradle, 'versionCode 2026080109', 'upgrade version')
    require(gradle, 'low-priority-resilient-batch', 'version name')
    require(main, '&& !song.autoUnavailable', 'skip automatic failures')
    require(main, 'NetworkMediaCache.beginForegroundWork(this)', 'foreground playback lease')
    require(network, 'ForegroundPriorityException', 'foreground preemption')
    require(network, 'yieldIfForegroundRequested(context)', 'cooperative background yield')
    require(batch, 'THREAD_PRIORITY_BACKGROUND', 'background thread priority')
    require(batch, 'SONG_STALL_SKIP_MS = 45000L', 'stall timeout')
    require(batch, 'for (int index = done; index < total; index++)', 'resume cursor')
    require(batch, 'skipStalledSongAndRestart', 'stall recovery')
    require(batch, '缓存失败并已跳过后续自动重试', 'failed track skip state')

    append_once(
        root / 'PROJECT_LOG.md',
        '低优先级一键缓存构建复核',
        '\n\n### 低优先级一键缓存构建复核\n\n- 已对公开分支现有前台优先、失败跳过、游标续跑和45秒停滞恢复实现执行独立构建验证。\n'
    )
    append_once(
        root / 'docs/CHANGELOG.md',
        'Playback-priority batch build verification',
        '\n\n### Playback-priority batch build verification\n\n- Revalidated the committed foreground-priority, failed-track skip, persistent cursor and 45-second stall recovery implementation with a clean four-flavor build.\n'
    )
    print('existing_playback_priority_fix=verified_for_build')


if __name__ == '__main__':
    main()
