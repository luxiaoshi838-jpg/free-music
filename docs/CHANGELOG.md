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
- Fixed local Gradle availability by adding the project Gradle wrapper, pinning Gradle 8.7 to an Aliyun mirror, adding Aliyun Maven mirrors, enabling Android's Windows non-ASCII path override for this Chinese-path workspace, selecting the installed Build Tools 37.0.0, and verifying `assembleDebug` for all four APK flavors.

## Pending

- Add configurable playlist cache root folder:
  - per-playlist cache subfolders;
  - shared `缓存` folder for search and replacement cache;
  - clear-cache action should clean that transient folder.
- Remove the visible “设置” title from the settings drawer while preserving layout positions.

## 2026-07-26.2

- Completed the cache and playback-context revision for all four brands.
- Added selectable cache-root storage with per-playlist folders and a shared `缓存` transient folder.
- Added transient-cache cleanup, playlist-cache promotion, and cache-folder rename support.
- Relaxed replacement matching and required real playability verification before manual replacement.
- Changed unavailable marking to require both automatic and exhaustive manual replacement failure.
- Completed backward-compatible CSV import/export round trips with optional state-preserving columns.
- Removed the visible settings title while keeping the drawer header spacing.
- Added JiangLab-only first-launch verification with a privately injected SHA-256 digest; no real passphrase or digest is committed.
- Added synchronized project logs, static feature checks, and a five-minute no-output build watchdog.
