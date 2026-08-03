# Changelog

## 2026-08-02

- Fixed the remaining Android 16 migration-refresh ANR: post-migration cache URI lookups now run in the dedicated `cache-uri-refresh` worker rather than the Activity main thread.
- Preserved the startup white-screen fix and the non-blocking one-click playlist cache target scan.
- Added subtle press/rebound feedback to the previous and next buttons.
- Added a gray circular white-`×` clear control inside the search field; it appears only when text is present.
- Bumped Android source version to `2026080126 / 2026.08.02.cache-io-guard-ui-feedback`.
- Release APKs were not rebuilt in this environment because the upload contains only the source delta and prior APK outputs, not the complete Gradle/signing workspace.

- Fixed the remaining one-click-cache ANR path: tapping the button no longer calls provider-backed `songHasPlayableCache` / `CacheStorage.findAudioUri` while preparing the batch.
- Cache-button counting and the batch target list now use recorded cache URIs only, avoiding repeated full-folder SAF queries on Android 16.
- Kept the v124 startup white-screen fix and layered this change on top of the uploaded newer source/APK logic.
- Bumped Android source version to `2026080125 / 2026.08.02.one-click-cache-nonblocking`.
- Release APKs were not rebuilt in this environment because the uploaded package contains only a source delta and built APKs, not the complete Gradle project/signing workspace.

- Fixed the physical-device startup ANR reported in `CacheStorage.exists`: playlist cache counting no longer opens `content://` cache URIs on the main thread while the Activity view is being built.
- Cache-button visibility now uses a serialized background scan with request IDs, so switching playlists cannot apply stale counts.
- One-click playlist cache now performs its initial uncached-song scan in the background instead of blocking the UI before the batch starts.
- Post-migration/startup cache URI refresh now performs `CacheStorage.findAudioUri` off the main thread.
- Current-song playlist-add cache verification also runs in a worker thread; known cached URIs are tried directly and fall back through the existing playback failure path.
- Bumped Android source version to `2026080124 / 2026.08.02.cache-scan-off-main`.
- Release APKs were not rebuilt from this partial source-delta package because the complete project and signing material were not included.

- Changed startup to render the Activity UI before running last-song restore, cache normalization, report popup scheduling, and watchdog work.
- Startup restore now shows last-song metadata without calling synchronous `MediaPlayer.prepare()` on the main thread.
- Bumped Android version to `2026080123 / 2026.08.02.startup-ui-first`.
- Built, signed, and verified all four fixed-name release APKs.

- Delayed no-response watchdog startup until after the first UI frame plus 5 seconds, reducing startup white-screen crash risk while keeping crash/no-response reporting active after launch.
- Bumped Android version to `2026080122 / 2026.08.02.delayed-anr-watchdog`.
- Built, signed, verified, and MEmu launch-tested all four fixed-name release APKs.

- Moved current-playlist one-click cache below the playlist and made it appear only when the playlist has uncached network songs.
- One-click cache now processes only uncached network songs and skips playable cached entries instead of recaching the whole playlist.
- Renamed `闪退报告` to `闪退/无响应报告`.
- Added UI no-response reporting: if the main thread is blocked for at least 12 seconds, the app stores a copyable report with playback/song context and main-thread stack.
- Bumped Android version to `2026080121 / 2026.08.02.cache-button-anr-report`.
- Built, signed, and verified all four fixed-name release APKs with the existing release certificate.

- Changed crash-report behavior so the report auto-popup appears only once per crash report; it can still be opened manually from settings.
- Added a `闪退报告` settings button.
- Restored Enter/search-key search submission in the search input.
- Network cache now accepts only MP3 and FLAC as successful playable cache formats; M4A is rejected and old M4A cache entries no longer count as playable hits.
- Bumped Android version to `2026080120 / 2026.08.02.crash-report-enter-search-mp3-flac`.
- Built and signed all four fixed-name release APKs with the existing release certificate.

- Fixed the copied physical-phone crash report: `ConcurrentModificationException` in `normalizePlaylistCacheFilesAsync`.
- Startup cache normalization now uses a playlist/song snapshot instead of iterating the live playlist lists on a background thread.
- This prevents playlist add/delete/replace actions from racing the normalization pass.
- Bumped Android version to `2026080118 / 2026.08.02.playlist-normalize-snapshot`.
- Built and signed all four fixed-name release APKs with the existing release certificate.

- Added next-launch crash reporting for physical-phone-only crashes.
- Uncaught Java crashes now persist a copyable report containing version/device/playback/song context plus stack trace.
- Added the `上次闪退报告` dialog with copy, clear, and close actions.
- Bumped Android version to `2026080117 / 2026.08.02.crash-report-copy`.
- Built and signed all four fixed-name release APKs with the existing release certificate.

- Fixed a physical-phone crash risk when adding searched network songs to playlists by no longer saving full network lyrics inside playlist JSON.
- Network song lyrics now stay in the managed lyric cache and are hydrated from cache before lyric display.
- Local song lyric persistence is unchanged.
- Bumped Android version to `2026080116 / 2026.08.02.playlist-light-lyrics`.
- Built and signed all four fixed-name release APKs with the existing release certificate.

- Fixed a playlist-add crash boundary: adding the currently playing searched song now saves a playlist copy without replacing the active playback object.
- Adding a searched song to a playlist no longer starts a second cache task or lyric-matching task.
- After a successful add, next/previous playback uses the target playlist queue while the current playing resource continues untouched.
- Kept the readable-cache guard so playlist add waits for the playback-created cache instead of fetching the same song again.
- Bumped Android version to `2026080115 / 2026.08.02.playlist-add-pure-save`.
- Built and signed all four fixed-name release APKs with the existing release certificate.

## 2026-08-01

- Restored the current-playlist one-click cache action.
- One-click playlist cache now skips songs that previously failed and continues with later tracks.
- Added a per-track timeout for one-click playlist cache so a slow or stuck source is marked failed and the batch moves to the next song.
- Foreground playback now has priority: choosing a new song pauses the background one-click cache instead of letting it compete with playback.
- Bumped Android version to `2026080109 / 2026.08.01.playlist-cache-yield-timeout`.

- Removed the mistakenly added current-playlist one-click cache action and its background batch-cache path.
- Playlist add is metadata-only again: searched songs keep the playback-created cache, and adding them to a playlist does not start another cache task.
- Removed the extra `cacheFailed` song state introduced with the rejected batch-cache flow.
- Bumped Android version to `2026080102 / 2026.08.01.remove-playlist-cache-button`.

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

### Playback-confirmed source flag replacement

- Deferred automatic replacement flag persistence until the replacement source actually prepares and starts playback.
- Added a playback request serial so stale cache or replacement threads cannot write back into the current song after the user has moved on.
- Added a `MediaPlayer.OnErrorListener` path that marks playlist items unavailable without saving a failed replacement source.
- Kept the original playlist identity until playback success, then persisted the confirmed replacement `catalogJson`, cached URI and source label.
- Bumped Android version to `2026072901 / 2026.07.29.playback-flag-commit`.
## 2026-08-02

### Accepted direct-search-source APK baseline

- Marked the user-supplied `apk-output` APK set as the current accepted baseline.
- Verified accepted version metadata:
  - `versionCode 2026080113`
  - `versionName 2026.08.02.direct-search-source`
- Verified the accepted `大宝贝儿老婆` APK file SHA-256:
  `11fe07aaa76b8ca9d27f50fca03fbf8e2c3ed4cccd6067d13016a62830899d6f`.
- Verified release certificate SHA-256:
  `4cc298f33101b8c4c41866294e2739cd6f3b741e5a9f7aa01cb55983482d6b5d`.
- Replaced the four fixed-name root APK outputs from the accepted `*_搜索播放源直传_正式签名.apk` files and archived the older fixed-name APKs under `apk-output\旧版`.
- Local Git sync is still pending: direct GitHub API read works after clearing the broken `127.0.0.1:9` proxy, but `git fetch` needs Git credentials and `gh auth setup-git` could not write `C:\Users\22177\.gitconfig` in this run.
- Future fixes must start from the GitHub branch expected to match this accepted release: `fix/multiformat-cache-priority-60s` at `fba8b78910543ec2cf4bbad601e2664c0bdd9dd7`, not from older local APKs or old local branches.

### Cache location and playlist-add boundary

- Tightened search playback, cache storage, and playlist-add responsibilities.
- Search playback now verifies the persistent cache file can be read after `CacheStorage.storeAudio()` returns.
- Current searched network songs cannot be added to a playlist until their cache file is actually readable.
- Adding a searched song to a playlist copies the already verified song state and does not start another resolve/cache task.
- Network playback checks `cachedUri` first and reuses it when readable.
- Search-play cache files use the same managed naming convention as playlist cache files: `title - artist [short-key].extension`.
- Non-playlist cache cleanup remains reference-aware and only targets managed cache files not referenced by playlists.
- Bumped Android version to `2026080114 / 2026.08.02.cache-location-join-boundary`.
- Validation: `:app:compileBabywifeclassicDebugJavaWithJavac` passed locally.
- Built and signed all four release APKs with `free-music-release-2026.p12`.
- Wrote fixed-name APK outputs to `E:\脚本\大宝贝儿老婆_apk\apk-output`.
- Verified package metadata, `versionCode 2026080114`, labels, and release signing certificate SHA-256 `4cc298f33101b8c4c41866294e2739cd6f3b741e5a9f7aa01cb55983482d6b5d`.
- ZIP packaging was not produced because the compression command was blocked by the execution safety layer.


## v127 - 2026-08-03
- Network sources returning M4A are now accepted, cached with the original `.m4a` extension, and reused as playable cache.
- MP3 remains preferred; unsupported formats remain rejected.


## v128 - 2026-08-03
- Fixed Soda Music M4A playback by extracting PlayAuth from the resolved URL and decrypting CENC/AES-CTR audio before caching.
- Existing encrypted M4A caches from v127 are detected as invalid and replaced on the next playback.

- Cache audio and lyric files now use `歌曲名 - 歌手` without an opaque hash suffix; true name collisions use `(2)`, `(3)`, etc.

- v129: normalize every managed cache file at startup to `歌曲名 - 歌手`, removing legacy hash suffixes even for songs outside playlists.
- v129: rank exact `歌名 + 歌手` matches first, split adjacent Latin/Chinese query text, and merge multi-source results by global relevance.

- v130: correct dialog action labels: deleting a song, deleting a playlist, and text-entry dialogs now use “确定”; merging playlists uses “合并”.
