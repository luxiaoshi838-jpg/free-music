# Changelog

## 2026-07-26

- Restored the public `free-music` repository to a four-brand Android APK source tree.
- Added public repository checks for four-brand source completeness and private signing material exclusion.
- Added playlist playback context fixes:
  - playlist playback hides “add to current playlist”;
  - search playback hides song/lyric replacement actions;
  - adding the current search song to a playlist switches subsequent playback to that playlist.
- Added transient cache cleanup entry point with a broom button.
- Added persistent unavailable marking for playlist songs that fail playback/cache resolution.
- Relaxed manual song replacement matching so exact same-title/same-artist results rank first, while same-title cover versions can still appear.
- Improved CSV playlist import compatibility with the current CSV export format.
- Added mandatory logging rule: future changes must update both `PROJECT_LOG.md` and this changelog before commit.

## Pending

- Add configurable playlist cache root folder:
  - per-playlist cache subfolders;
  - shared `缓存` folder for search and replacement cache;
  - clear-cache action should clean that transient folder.
- Remove the visible “设置” title from the settings drawer while preserving layout positions.
