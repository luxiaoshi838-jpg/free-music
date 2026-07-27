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

## 2026-07-27

- Added one-folder cache storage with app-private default storage and a user-selectable persistent Android document-tree folder.
- Reused the former settings-title row as the cache-location control so the remaining settings layout stays in place.
- Kept the broom action reference-aware: playlist cache keys are preserved while non-playlist audio and lyric cache files are removed.
- Persisted whether the last playing item came from a playlist or search-only context and restored action-button visibility accordingly.
- Broadened automatic and manual replacement matching with title/artist similarity scoring and real source resolution.
- Changed unavailable highlighting so a playlist item turns red only after automatic resolution and manual replacement both fail.
- Kept CSV import aligned with the existing eight-column CSV export format.
- Added JiangLab-only first-launch verification derived from the final signing certificate CN; no real passphrase or passphrase hash is stored in the public source.
- Kept release signing keys outside the public repository.
