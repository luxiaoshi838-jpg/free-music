#!/usr/bin/env python3
from pathlib import Path
import argparse

# This helper rewrites only the ambiguous patch-script anchor before the build.

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--script', required=True)
    path = Path(parser.parse_args().script)
    text = path.read_text(encoding='utf-8')
    old = '''    text = replace_once(
        text,
        \'\'\'        PlaylistBatchCacheService.TaskState state = PlaylistBatchCacheService.readState(this);
        boolean samePlaylist = state.belongsTo(currentPlaylistIndex);
\'\'\',
        \'\'\'        PlaylistBatchCacheService.TaskState state = cachedBatchTaskState;
        if (state == null) {
            cachePlaylistButton.setEnabled(true);
            cachePlaylistButton.setText("一键缓存未缓存歌曲（" + count + "首）");
            requestBatchCacheSync(false);
            return;
        }
        boolean samePlaylist = state.belongsTo(currentPlaylistIndex);
\'\'\',
        'cached button task state'
    )
'''
    new = '''    text = replace_once(
        text,
        \'\'\'        PlaylistBatchCacheService.TaskState state = PlaylistBatchCacheService.readState(this);
        boolean samePlaylist = state.belongsTo(currentPlaylistIndex);
        cachePlaylistButton.setVisibility(View.VISIBLE);
\'\'\',
        \'\'\'        PlaylistBatchCacheService.TaskState state = cachedBatchTaskState;
        if (state == null) {
            cachePlaylistButton.setEnabled(true);
            cachePlaylistButton.setText("一键缓存未缓存歌曲（" + count + "首）");
            requestBatchCacheSync(false);
            return;
        }
        boolean samePlaylist = state.belongsTo(currentPlaylistIndex);
        cachePlaylistButton.setVisibility(View.VISIBLE);
\'\'\',
        'cached button task state'
    )
'''
    if old not in text:
        raise RuntimeError('ambiguous task-state anchor block not found')
    path.write_text(text.replace(old, new, 1), encoding='utf-8')
    print('ui_patch_anchor=fixed')


if __name__ == '__main__':
    main()
