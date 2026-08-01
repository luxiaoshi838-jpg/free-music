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

### CSV, legacy cache and cache-management follow-up

- Inspected the previously supplied `apk-output.zip` instead of inferring legacy behavior.
- Confirmed all four legacy APKs stored media under app-private `files/network_music`; those files were excluded from Android backup and are removed on uninstall.
- Fixed CSV header mapping so `歌曲ID` can no longer overwrite the `歌名` column.
- Replaced the colored broom emoji with a custom white line icon matching the settings control.
- Moved the cache-folder control into the lower settings actions directly above the background-image button.
- Added explicit legacy-default and current cache paths to the cache-location dialog.
- Added copy-first cache migration when changing folders or moving back to internal storage.
- Restricted cache migration and cleanup to recognized SHA256-named cache files so unrelated user files are never deleted.
- Added a default-off setting controlling whether deleting songs/playlists also removes unreferenced audio and lyric cache files.

### Uninstall cache, import menu and named media follow-up

- Removed the delete-entry cache switch. Deleting songs, clearing a playlist, or deleting a playlist now keeps audio, lyric, and metadata files until the reference-aware broom cleanup is run.
- Implemented a real uninstall-cleanup switch by migrating between app-private storage (Android clears it on uninstall) and a user-selected document-tree folder (persists after uninstall).
- Documented the Android platform limitation: an app cannot reliably receive its own uninstall callback to delete an arbitrary shared folder.
- Changed managed cache names to `title - artist [short-id].extension`, used the same title for `.lrc` files, and added one hidden JSON metadata record per track with title, artist, album, catalog data, and file mappings.
- Added ID3v2.3 title, artist, and album frames to newly downloaded MP3 files; all formats retain friendly names and JSON metadata.
- Added compatible normalization for existing legacy SHA256-named cache files when an actual cached playlist item is found.
- Merged local import into one button with file/folder choices and playlist import into one button with CSV/link choices.
- Moved the custom background button directly above the launcher-icon button.
- Moved the playlist-management drawer below the status bar with explicit top and bottom margins.
- Replaced the generated broom drawing with the user-supplied white broom artwork, converted to a transparent padded resource and centered inside the circular control.
- Bumped the Android version to `2026072702 / 2026.07.27.cache-uninstall-import-ui`.


### MP3 cache normalization and settings drawer follow-up

- Prefer MP3/320k resolution hints and skip transcoding when the downloaded content is already a real MP3.
- Detect actual audio content instead of trusting URL extensions; transcode non-MP3 sources to 192 kbps, 44.1 kHz stereo MP3 with FFmpegKit/libmp3lame.
- Use `io.github.jamaismagic.ffmpeg:ffmpeg-kit-lts-full-16kb:6.1.4` to retain Android API 23 compatibility without raising the app minimum SDK.
- Reject non-MP3 files at the managed-cache storage boundary.
- Write and read back ID3v2.3 title, artist and album frames before accepting a cached MP3; failed verification prevents the file from being stored.
- Reduced the settings drawer to 60% of screen width without moving the existing controls vertically.
- Extended the drawer's black appearance through the system status-bar area while the drawer is open, restoring the original status-bar color on close.
- Removed uninstall-behavior suffixes from the cache-folder button while keeping full behavior details in the dialog.
- Shortened playlist-manager labels to `新建` and `导出`.
- Bumped Android version to `2026072703 / 2026.07.27.mp3-cache-settings-ui`.

### Lightweight UI-only follow-up

- Removed the bundled FFmpegKit dependency after confirming it made each APK roughly 180 MB.
- Kept the settings drawer UI changes: 60% drawer width, black status-bar continuation while open, shorter cache-folder text, and shorter playlist-manager labels.
- Kept MP3-first resolution and ID3 verification for real MP3 downloads.
- Lightweight builds now reject non-MP3 network audio for managed cache instead of transcoding on-device or storing a renamed non-MP3 file.
- Local imported songs are not converted and continue to use their original local files.
- Bumped Android version to `2026072704 / 2026.07.27.light-ui-no-ffmpeg`.

### Source-format fallback and drawer-width follow-up

- Corrected the lightweight audio-cache rule from MP3-only to MP3-preferred.
- Network playlist tracks still request MP3 first; when the actual source is M4A, AAC, OGG, FLAC or WAV, the app now caches and plays the true source format instead of failing.
- MP3 files still receive verified ID3 title, artist and album tags; non-MP3 files keep friendly names and JSON metadata.
- Changed the settings drawer width from 60% to 70%.
- Extended the drawer background to the top of the screen while preserving the vertical position of the playlist manager and settings actions.
- Bumped Android version to `2026072705 / 2026.07.27.light-ui-source-format`.

## 2026-08-01 Multi-format cache priority and one-minute filter

- Rebased exclusively on the latest public `main` commit `404ff797`; no private fallback-repository patch was reused.
- Automatic candidates are ordered as MP3, FLAC, then other source formats without an extension whitelist.
- Known catalog durations below 60 seconds are skipped, and downloaded files must also report at least 60 seconds through Android media parsing.
- Text/HTML/JSON responses, empty files, unsupported files, and short files are rejected before playlist source persistence.
- Audio bytes remain untouched: title, artist, album, and ID3-style tags are not written into cached songs. Playlist data remains authoritative.
- Cache filenames use `title - artist.original-extension`; only real same-name collisions receive `(2)`, `(3)`, and so on. Cache migration remains supported, and unknown extensions use `.audio` rather than a false `.mp3` suffix.
- Audio and lyric files now share the exact same basename: `title - artist.audio-extension` and `title - artist.lrc`. Legacy `.txt` lyric files are read only for migration compatibility and are normalized to `.lrc`.

## 2026-08-01 Original-source playback fast path

- Fixed the cache path resolving every cross-platform candidate even when the playlist's original source was valid.
- The original source is now resolved, downloaded, validated, and returned immediately before any alternative search.
- MP3 is still requested first within the original source; its source format is used when MP3 is unavailable.
- Cross-platform matching runs only after an original-source resolve, download, readability, or 60-second validation failure.
- Alternatives are resolved and validated one at a time, returning the first valid result, with at most four attempts.

## 2026-08-01 Playback compatibility and playlist batch cache

- Kept support for valid M4A files while validating the audio track, device decoder, readable samples, and mid-file seeking before accepting a cache.
- Invalid existing caches are removed and resolved again instead of being accepted by duration metadata alone.
- Added MediaPlayer error containment so decode or seek failures release the player, remove the broken cache, and mark the song for manual replacement.
- Added a conditional one-click cache button at the bottom of the current playlist.
- Batch caching runs sequentially without changing playback; automatic failures are shown in red for manual version selection.


## 2026-08-01 Background playlist cache service

- Moved one-click playlist caching from an Activity thread into a foreground data-sync service.
- Batch caching now continues during background playback, lock screen use, and Activity recreation.
- Progress and per-song results are persisted; failed songs remain marked red for manual replacement.


## 2026-08-01 Resumable isolated playlist cache

- Moved playlist batch caching into a dedicated process so search and playback remain responsive.
- Added start/pause/resume/stale-task restart behavior to the same playlist cache button.
- Persisted task state and result journals with atomic files, while keeping playlist preferences single-writer.
- Added per-track cross-process cache locks and unique partial downloads.
- Hide the cache button when the current playlist has no uncached online tracks.


## 2026-08-01 Responsive UI and playback notification

- Moved batch result file scanning and parsing off the Android main thread.
- Coalesced cache progress refreshes and stopped redrawing lists for every callback.
- Made playlist/search navigation render immediately before asynchronous cache refresh.
- Removed per-song storage probes from the cache button UI path.
- Moved playback notification handling into a dedicated process and published track changes before lyric rendering.
- Throttled batch progress broadcasts and notification updates.


## 2026-08-01 Foreground-priority resilient batch cache

- Added a foreground cache/resolve lease so playback work preempts playlist batch caching.
- Lowered the batch worker thread priority and cooperatively releases per-song cache locks when foreground playback needs resources.
- Excluded prior automatic failures from future one-click cache requests while retaining manual replacement.
- Persisted the processed cursor across isolated cache-process restarts.
- Added a 45-second no-progress watchdog that skips the stalled track, restarts the isolated worker and continues with the next track.
- Bumped the upgradeable build to versionCode 2026080109.


### Playback-priority batch build verification

- Revalidated the committed foreground-priority, failed-track skip, persistent cursor and 45-second stall recovery implementation with a clean four-flavor build.


## 2026-08-01 Manual-priority search, retained picker results and background resolve

- Serialized native catalog search across processes and gave manual search precedence over automatic fallback and playlist batch caching.
- Persisted replacement-song results and source cursor per song, with pull-down, bottom-scroll and footer loading.
- Added keyboard Enter/Search action handling to the main search field.
- Moved playback catalog resolution and audio caching into the independent foreground playback service so work continues while another app is visible.
- Deferred lyric matching until playable audio is ready.
- Removed the one-minute gate from manual search, manual replacement and clicked playback while retaining it for one-click batch caching and automatic replacement.
- Bumped versionCode to 2026080110.
