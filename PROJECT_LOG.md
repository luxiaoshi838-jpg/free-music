# Project Log

## 2026-08-02

### Guard cache migration I/O and add playback/search feedback

- Physical-device follow-up on Xiaomi Android 16: version `2026080124` still produced a no-response report in `refreshCachedUrisAfterMigration -> refreshCachedUri -> CacheStorage.findAudioUri -> listDocumentsStrict` because the shipped migration refresh path queried the selected document tree from the Activity main thread.
- Renamed and hardened the refresh entrypoint as `refreshCachedUrisAfterMigrationAsync`; it snapshots UI state quickly, then performs every `findAudioUri` lookup on the dedicated `cache-uri-refresh` worker before returning results to the UI.
- Kept the v124 startup white-screen fix and v125 one-click-cache non-blocking target scan. The one-click button still builds its target list only from recorded URIs and never enumerates the cache folder.
- Added a subtle 4% press scale and short rebound animation to the previous/next controls, giving visible feedback without changing the established player layout.
- Added an overlaid search clear control: a small gray circle with a white `×` appears only while the search field contains text and clears the field when tapped.
- Static checks cover the async migration refresh, non-blocking one-click target scan, previous/next feedback, search clear control, version, and synchronized logs.
- Version bumped to `2026080126 / 2026.08.02.cache-io-guard-ui-feedback`.

### Make one-click playlist cache fully non-blocking

- Physical-device follow-up: version `2026080124` fixed startup white-screen ANR, but tapping one-click cache still entered `cacheCurrentPlaylistOneClick -> uncachedNetworkSongs -> songHasPlayableCache -> CacheStorage.findAudioUri -> listDocumentsStrict` on the Activity main thread in the shipped APK.
- Unified the version chain as `GitHub main < uploaded v123 source delta < v124 APK logic`, then applied this fix on top rather than reverting the APK startup changes.
- The one-click cache button and batch worker now classify cached songs only from their recorded `cachedUri` or direct local `file:/content:` URI. They never call `CacheStorage.findAudioUri` or enumerate the selected cache folder merely to build the target list.
- Removed the second provider-backed cache lookup from the per-track batch loop. The normal playback failure path remains responsible for clearing an unusable recorded URI.
- Result: pressing one-click cache returns control to the UI immediately; a slow Android 16 document provider can no longer stall the button before downloads begin.
- Static validation confirms the one-click target-list path contains no `songHasPlayableCache`, `CacheStorage.findAudioUri`, `ContentResolver.query`, or `openAssetFileDescriptor` call.
- Version bumped to `2026080125 / 2026.08.02.one-click-cache-nonblocking`.

### Move cache URI scans off the Activity main thread

- Physical-device no-response report: Xiaomi `25060RK16C`, Android 16 / SDK 36, version `2026080121`, main thread blocked for `715176 ms`.
- The captured stack terminates at `MainActivity.updatePlaylistCacheButtonVisibility -> uncachedNetworkSongs -> songHasPlayableCache -> NetworkMediaCache.cachedAudioExists -> CacheStorage.exists -> ContentResolver.openAssetFileDescriptor`.
- Root cause: building the playlist page synchronously opened each cached `content://` URI on the main thread merely to decide whether the one-click cache button should be visible.
- Replaced synchronous button counting with a single-thread background scan and monotonic request serial. Results are applied only when the same playlist is still active.
- Moved the initial one-click-cache target scan to its worker thread; the button/status show a non-blocking checking state while this runs.
- Moved post-normalization and post-migration `CacheStorage.findAudioUri` refresh work off the main thread.
- Moved current-song cache verification for playlist insertion off the main thread and removed redundant synchronous existence probes from playlist copy/play selection paths.
- Static validation: no Java parser-level syntax diagnostics were reported by `javac`; targeted audit confirms all remaining `cachedAudioExists` and bulk URI scans are inside worker/executor code.
- Full Android compile/sign validation was not possible from the uploaded package because it contains only `source_delta`, not the complete project, Gradle wrapper/dependencies, or release signing material.
- Version bumped to `2026080124 / 2026.08.02.cache-scan-off-main`.

### Startup UI-first restore for white-screen hang

- User reported the app still opens to a white screen and gets stuck, while notification controls can still play.
- Diagnosis: notification playback means the process/service is alive; the Activity first frame is being blocked. Startup still called last-song restore, cache normalization, report popup scheduling, and watchdog setup directly after `setContentView`.
- Changed startup so `onCreate` renders the shell UI and playlist lists first, then schedules restore/cache/report/watchdog work after the first frame delay.
- Changed startup last-song restore to display metadata without calling synchronous `MediaPlayer.prepare()` on the main thread. Audio preparation now waits for explicit playback instead of blocking the first Activity frame.
- Validation: `:app:compileBabywifeclassicDebugJavaWithJavac` passed.
- Built, zipaligned, signed, and verified all four release APKs.
- Version bumped to `2026080123 / 2026.08.02.startup-ui-first`.

### Delay no-response watchdog after white-screen startup crash report

- User reported the newly produced APK opens to a white screen and then exits before entering the app.
- MEmu launch log did not reproduce a Java fatal exception, but the startup path showed the no-response watchdog was being started at the beginning of `onCreate`.
- Reduced startup risk by delaying the watchdog until after the content view is created and the first UI frame has had 5 seconds to settle.
- Crash/no-response report functionality remains active after startup, and the settings entry remains available.
- Validation: `:app:compileBabywifeclassicDebugJavaWithJavac` passed.
- Built, zipaligned, signed, and verified all four release APKs.
- Installed `babywife-classic` over the previous build on MEmu; launch log showed `Displayed com.jianglab.babywife/.LauncherClassic` and no `FATAL EXCEPTION`.
- Version bumped to `2026080122 / 2026.08.02.delayed-anr-watchdog`.

### One-click cache visibility and crash/no-response report

- Moved the current-playlist one-click cache action out of the top-right toolbar. The top-right playlist action now remains sorting only.
- The one-click cache button now sits below the playlist and is visible only when the current playlist has uncached network songs.
- One-click cache now targets only uncached network songs. Songs with playable cache are skipped before work starts and checked again during the background loop.
- Renamed the settings entry and dialog from crash report to crash/no-response report.
- Added a lightweight UI responsiveness watchdog. If the main thread stops heartbeating for at least 12 seconds, the app saves a single copyable no-response report with package/version/device/playback/song context and the main-thread stack.
- The same copy, close, clear, and one-time auto-popup rules are used for crash reports and no-response reports.
- Validation: `:app:compileBabywifeclassicDebugJavaWithJavac` passed. All four release APKs built, signed, and verified.
- Version bumped to `2026080121 / 2026.08.02.cache-button-anr-report`.
- Output root: `E:\脚本\大宝贝儿老婆_apk\apk-output`.

### Crash-report dialog, enter search and cache format boundary

- Crash reports now auto-pop only once after a crash. Copy, close, cancel, or clear stops future automatic popups for the same report.
- Added a `闪退报告` button in the settings drawer so the single stored report can be reopened and copied later.
- Restored keyboard search: pressing the input-method search action, done action, or Enter in the search box triggers the same search action as the search button.
- Tightened network cache format acceptance:
  - MP3 remains preferred and receives metadata verification.
  - FLAC is accepted and cached.
  - M4A and other non-MP3/non-FLAC network results are rejected before they can be stored as successful cache entries.
  - Existing M4A cache entries no longer count as playable cache hits.
- Local imported files are not affected by this network-cache boundary.
- Validation: `:app:compileBabywifeclassicDebugJavaWithJavac` passed, and all four release APKs built and signed.
- Version bumped to `2026080120 / 2026.08.02.crash-report-enter-search-mp3-flac`.

### Fix phone crash from playlist normalization race

- User copied the new crash report from a Xiaomi Android 16 phone.
- Root cause: `ConcurrentModificationException` in `normalizePlaylistCacheFilesAsync` while iterating `playlists` on a background thread.
- The crash happened because the startup cache-file normalization thread iterated the live playlist/song lists while the foreground playlist flow modified them.
- Fixed by taking a snapshot of playlists and songs on the UI thread before starting the background normalization work.
- The background thread now iterates only that snapshot, so adding/deleting/replacing songs can no longer modify the list being iterated.
- Validation: `:app:compileBabywifeclassicDebugJavaWithJavac` passed, and all four release APKs built and signed.
- Version bumped to `2026080118 / 2026.08.02.playlist-normalize-snapshot`.

### Add copyable next-launch crash report

- User reported playlist add still crashes on a physical phone, while MEmu does not reproduce it.
- Added a process-wide uncaught-exception handler in `MainActivity`.
- On crash, the app now saves a latest crash report with package, version, device, Android version, thread, playback context, current playlist, current song, catalog snippet, URI/cache URI, and Java stack trace.
- On next launch, the app shows `上次闪退报告` with selectable text and actions to copy, clear, or close.
- The report is capped to avoid unbounded state growth and overwrites the previous crash report.
- Validation: `:app:compileBabywifeclassicDebugJavaWithJavac` passed, and all four release APKs built and signed.
- Version bumped to `2026080117 / 2026.08.02.crash-report-copy`.

### Avoid real-device crash when adding cached search songs

- User reported that adding a searched song to a playlist still crashes on a physical phone, while the same flow does not crash in MEmu.
- Static diagnosis found that network songs still persisted full lyric text into playlist JSON through `Song.toJson()`.
- Changed network-song persistence so playlists and last-search state save identity/cache references only; full lyrics stay in the managed `.lrc` cache.
- Added cache hydration before lyric display so playlist playback can read the cached `.lrc` without bloating SharedPreferences.
- Kept local-song lyric persistence unchanged.
- Validation: `:app:compileBabywifeclassicDebugJavaWithJavac` passed, and all four release APKs built and signed.
- Version bumped to `2026080116 / 2026.08.02.playlist-light-lyrics`.

### Fix playlist-add crash boundary

- Fixed the crash-prone path where adding the currently playing searched song to a playlist replaced `currentSong` with a new playlist copy while the media player was still bound to the old object.
- Playlist add is now a pure save/context switch operation: it saves a playlist copy, switches the next/previous queue context to that playlist, and does not start another cache or lyric-matching task.
- Kept the existing cache boundary: a searched song can be added only after its playback cache is readable, so adding does not re-fetch or re-cache the same resource.
- Built and signed all four release APKs with the existing release certificate.
- Version bumped to `2026080115 / 2026.08.02.playlist-add-pure-save`.
- Output fixed APK names in `E:\脚本\大宝贝儿老婆_apk\apk-output`: `大宝贝儿老婆.apk`, `姜Lab.apk`, `李大财主.apk`, `牛逼.apk`.

## 2026-08-01

### Restore and guard playlist one-click cache

- Restored the current-playlist one-click cache action; the feature should not be removed.
- One-click playlist cache now skips songs that previously failed and continues with later tracks.
- Added a per-track timeout for one-click playlist cache so a slow or stuck source is marked failed and the batch moves to the next song.
- Foreground playback now has priority: choosing a new song pauses the background one-click cache instead of letting it compete with playback.
- Version bumped to `2026080109 / 2026.08.01.playlist-cache-yield-timeout`.

### Remove rejected playlist one-click cache

- Removed the mistakenly added current-playlist one-click cache action and its background batch-cache path.
- Playlist add is metadata-only again: searched songs keep the playback-created cache, and adding them to a playlist does not start another cache task.
- Removed the extra `cacheFailed` song state introduced with the rejected batch-cache flow.
- Version bumped to `2026080102 / 2026.08.01.remove-playlist-cache-button`.

### Playlist one-click cache skip failed tracks

- Added a `缓存` action to the current-playlist page for one-click caching the active playlist.
- One-click caching now writes a persistent `cacheFailed` flag on each failed network playlist song.
- Later one-click cache runs skip songs with `cacheFailed=true`, so the batch continues after the failed song instead of repeatedly starting from it.
- Successful cache, fresh playlist add, and confirmed song replacement clear the failed-cache mark.
- Verified Java compilation for all four debug flavors with project-local Gradle cache and JDK17.
- Version bumped to `2026080101 / 2026.08.01.playlist-cache-skip-failed`.

本文件是项目主日志。所有功能修改、构建流程修改、缓存/签名/导入导出逻辑修改，都必须在提交前记录到这里，并同步维护 `docs/CHANGELOG.md`。

## 2026-07-26

### 公开库四品牌源码恢复

- 公开库：`luxiaoshi838-jpg/free-music`
- 提交：`fb2adae Restore four-brand local APK source`
- 内容：
  - 将公开库从单品牌模板恢复为四品牌 Android 工程。
  - 四品牌：`babywifeclassic`、`jianglab`、`lidacaizhu`、`niubi`。
  - 加入 `app/libs/musicbridge.aar`、四品牌图标、默认背景、核心播放器与歌单源码。
  - 明确公开库不包含正式签名私钥，默认只能构建 Debug APK。

### 播放上下文与缓存清理修正

- 本地提交：`78d7b18 Refine playlist playback and cache cleanup`
- 状态：本地已提交，推送 GitHub 时网络连接失败，远端暂未同步。
- 内容：
  - 顶部设置与搜索之间新增圆形扫把按钮，用于清除非歌单缓存。
  - 从歌单播放时隐藏“加入当前歌单”。
  - 从搜索播放时隐藏“替换歌曲 / 替换歌词”。
  - 搜索歌曲加入歌单后，播放上下文切换到对应歌单，下一首走歌单队列。
  - 未加入歌单的搜索歌曲，下一首走搜索结果队列。
  - 手动替换歌曲放宽候选限制：同名同歌手优先，其次允许同名其他歌手版本。
  - 歌单内缓存/播放失败歌曲持久标记为不可用，并在列表标红。
  - CSV 导入增强，兼容当前导出歌单格式。

### 日志同步规则

- 新增要求：所有后续修改必须同时更新本地日志与在线日志。
- 实施方式：
  - 每次代码或构建流程修改，都先更新 `PROJECT_LOG.md` 和 `docs/CHANGELOG.md`。
  - 日志文件随 Git 提交推送到公开库，作为在线日志。
  - 若网络推送失败，必须在最终回复中说明“本地已记录但远端未同步”。

### 待办：歌单缓存位置

- 用户要求：
  - 设置页增加“歌单缓存位置”功能。
  - 点击后默认打开当前缓存位置，并允许选择缓存总文件夹。
  - 缓存总文件夹内按歌单名称创建子文件夹。
  - 另有 `缓存` 子文件夹，用于搜索结果歌曲和被替换后的歌曲/歌词。
  - 扫把清理功能主要清理 `缓存` 子文件夹。
  - 设置页顶部“设置”两个字取消，其他设置位置保持不变。
- 状态：尚未实现，下一步处理。

### Gradle 环境修复

- 用户要求：修复当前机器没有 `gradle`，导致无法本地生成 APK 的问题。
- 进展：
  - 外网下载 `gradle-8.7-bin.zip` 两次失败：一次 `unexpected EOF`，一次 `connection reset`。
  - 本机存在 Gradle 8.2.1 wrapper 缓存，但默认 `C:\Users\22177\.gradle\native` 锁文件拒绝访问。
  - 使用项目专用 `GRADLE_USER_HOME=E:\脚本\_gradle_home_free_music` 后，Gradle 8.2.1 可正常启动。
  - 已创建本地 `local.properties` 指向 `D:\software\SDK`。
  - 离线解析失败点：公开源码使用 Android Gradle Plugin 8.5.2，但本机未缓存该插件。
  - 本机所谓 Android Gradle Plugin 8.1.2 缓存不完整，无法离线构建。
  - 已将 `settings.gradle` 增加阿里云 Maven 镜像，优先用于插件和依赖解析。
  - 继续保持 Android Gradle Plugin 8.5.2，避免为了本机环境降低项目构建版本。
  - 改用国内镜像下载 Gradle 8.7。
  - Gradle 8.7 已成功安装到 `D:\software\Gradle\gradle-8.7`。
  - 生成 wrapper 时已进入 Android 插件配置阶段，说明 AGP 8.5.2 依赖解析成功。
  - 新阻塞点：项目路径含中文，AGP 在 Windows 上拒绝构建；已按提示加入 `android.overridePathCheck=true`。
  - 已生成项目自带 Gradle wrapper：`gradlew`、`gradlew.bat`、`gradle/wrapper/gradle-wrapper.jar`、`gradle/wrapper/gradle-wrapper.properties`。
  - wrapper 下载源固定为 `https://mirrors.aliyun.com/macports/distfiles/gradle/gradle-8.7-bin.zip`，避免默认官方源在当前网络下反复超时。
  - 已验证 `.\gradlew.bat --version` 可正常下载并启动 Gradle 8.7。
  - 已验证 `.\gradlew.bat --no-daemon tasks` 可正常解析 Android 项目任务，四品牌 assemble/install 任务均可被识别。
  - 首次真实 `assembleDebug` 验证发现本机缺少 AGP 默认寻找的 Build Tools 34.0.0。
  - 已在 `app/build.gradle` 固定使用本机现有的 `buildToolsVersion "37.0.0"`。
  - 已在 `gradle.properties` 增加 `android.suppressUnsupportedCompileSdk=35`，消除 AGP 8.5.2 对 compileSdk 35 的兼容提示。
  - 已在 `gradle.properties` 增加 `android.javaCompile.suppressSourceTargetDeprecationWarning=true`，减少 JDK 21 构建 Java 8 目标时的重复噪音警告。
  - 使用 `ANDROID_USER_HOME=E:\脚本\_android_user_home_free_music` 避开 `C:\Users\22177\.android` 拒绝访问问题后，`.\gradlew.bat --no-daemon assembleDebug` 已成功完成。
  - 本地已生成四个 Debug APK flavor：`babywifeclassic`、`jianglab`、`lidacaizhu`、`niubi`。
- 结论：当前机器“不存在全局 gradle”不再阻塞项目，后续应统一使用项目根目录的 `.\gradlew.bat` 构建。

## 2026-07-27

### 总缓存目录、替换与首次验证

- 缓存存储改为单一总文件夹方案：默认仍为应用内部 `files/network_music`，卸载时由 Android 一并清除。
- 设置抽屉顶部原“设置”标题位置改为缓存位置按钮，其余设置区布局保持不变。
- 用户可通过 Android 文档树选择一个外部总缓存文件夹；歌曲与 `.lrc` 歌词直接存放在同一目录，不再进行歌单子目录之间的文件移动。
- 扫把按钮会同时检查当前外部目录与历史内部目录，仅保留仍被歌单引用的缓存键。
- 搜索歌曲加入歌单后立即切换为歌单播放上下文；未加入时继续使用搜索队列。
- 上次退出为搜索歌曲时恢复搜索上下文，不显示“替换歌曲 / 替换歌词”；上次退出为歌单歌曲时不显示“加入当前歌单”。
- 自动替换从严格同名同歌手放宽为标题相似度与歌手相似度综合排序，并继续对候选资源执行真实解析。
- 手动替换列表允许相近标题、不同版本与歌手信息不完整的候选；只有自动解析失败且手动搜索/选择也失败时才持久标红。
- CSV 导入继续严格兼容当前导出列：歌名、歌手、专辑、时长秒、平台、平台代码、歌曲ID、歌词版本。
- 姜Lab flavor 增加首次启动验证框架：公开源码不包含真实口令或口令哈希，运行时读取最终 APK 签名证书的 CN 作为校验值；验证成功后仅在本机保存通过状态。
- 正式签名私钥不进入公开库；新密钥和最终签名 APK 在本地交付包内保存。

### CSV 导入、旧版缓存核查与缓存管理二次修正

- 已实际检查用户此前上传的 `apk-output.zip`，其中包含四个 `2026.07.17.178` APK：
  - 大宝贝儿老婆：`com.jianglab.babywife`
  - 姜Lab：`com.jianglab.babywife.jianglab`
  - 李大财主：`com.jianglab.babywife.lidacaizhu`
  - 牛逼：`com.jianglab.babywife.niubi`
- 四个旧 APK 使用同一旧签名证书，SHA256 指纹为 `A3CE8A630DDD34E67CE7FB1EC54279B8E36BD61E0172028901749E13041DA228`。
- 旧版源码与 APK 字符串均确认：歌曲和歌词默认存储在 `getFilesDir()/network_music`，即 `/data/user/0/<包名>/files/network_music`。
- 旧版备份规则仅包含 SharedPreferences，不包含 `files/network_music`；卸载旧签名版本后，旧歌曲和歌词缓存会由 Android 清除，不能由新签名版本继承。
- 修复 CSV 导入字段覆盖错误：原逻辑先用“包含歌曲”识别歌名，导致“歌曲ID”列覆盖歌名列；现在先精确识别歌曲 ID，并只接受“歌名/歌曲名/歌曲标题”等明确标题字段。
- 顶部扫把由彩色 Emoji 改为自绘白色线性图标，圆形背景与设置按钮保持一致。
- 缓存位置按钮从设置抽屉顶部移到底部操作区，并紧邻“选择本地图片作为背景”按钮上方。
- 缓存位置详情明确显示旧版默认物理路径、当前路径、卸载是否清除及系统备份范围。
- 更换外部总缓存文件夹时，先复制全部受管理的歌曲和歌词文件，复制全部成功后才删除旧位置文件；迁回应用内部时采用相同迁移规则。
- 迁移与扫把清理只管理 64 位 SHA256 缓存名，避免误删用户所选文件夹内的其他普通文件。
- 新增“删除歌单/歌曲时同步清理缓存”设置按钮，默认关闭；开启后仅当歌曲不再存在于任何歌单时，才删除对应歌曲和歌词缓存。
- 本次修改在独立源码与构建流程中完成，不会停止或覆盖手机上正在运行的软件进程。

### 卸载缓存、导入入口与歌曲文件信息修正

- 删除原“删除歌单/歌曲时同步清理缓存”开关；删除歌曲、清空歌单或删除歌单现在只修改歌单记录，歌曲、歌词和歌曲信息文件继续保留。
- 顶部扫把仍只清理未被任何歌单引用的网络歌曲缓存；已从歌单删除的歌曲会在后续执行扫把清理时作为非歌单缓存被清除。
- “卸载软件时清理缓存”改为真实可执行的存储切换：
  - 开启时使用应用内部 `files/network_music`，Android 卸载应用时自动清理；
  - 关闭时要求选择 Android 文档树外部总文件夹，卸载应用后文件继续保留；
  - 从关闭切换为开启时，先将全部受管理文件迁回应用内部，成功后才删除外部目录中的对应文件。
- 说明：Android 不会向正在被卸载的应用提供可靠的自身卸载回调，因此不能在卸载瞬间主动删除任意公共文件夹；本实现通过“应用内部位置/外部保留位置”迁移来保证开关行为真实可靠。
- 网络缓存文件改为 `歌名 - 歌手 [短标识].扩展名`，歌词使用相同真实歌名文件名；每首歌曲同时保存隐藏 JSON 信息文件，记录完整缓存键、歌名、歌手、专辑、平台目录和歌曲/歌词文件名。
- 新下载的 MP3 写入标准 ID3v2.3 `TIT2/TPE1/TALB` 标签；其他格式仍保留真实文件名和完整 JSON 歌曲信息。
- 启动时对歌单中已经存在的旧 64 位哈希缓存执行兼容识别，存在实际缓存时逐步改名并补充歌曲信息文件；未缓存歌曲不会产生空信息文件。
- “导入本地歌曲”合并为单一入口，点击后选择“选择歌曲”或“选择文件夹”。
- “导入歌单”合并为单一入口，点击后选择“CSV 文件”或“歌单链接”。
- “选择本地图片作为背景”移动到“更换桌面图标”正上方。
- 设置抽屉整体增加状态栏高度加 8dp 的顶部边距和 8dp 底部边距，使歌单管理窗口下移，不再挤入通知栏。
- 扫把按钮改用用户本次上传的白色扫把图片，提取为透明背景资源，并在圆形按钮中按 82% 画布居中；原图自身保留边距，实际扫把主体不会撑满按钮。
- 版本提升为 `2026072702 / 2026.07.27.cache-uninstall-import-ui`。
- 本次修改继续只在 GitHub 分支与云端构建环境执行，不会停止、重启或覆盖手机上正在运行的软件进程。


### MP3 缓存统一与设置栏界面修正

- 网络歌曲解析优先向音乐桥请求 MP3/320k 结果；若实际下载内容已经是真实 MP3，则不重复转码。
- 下载后根据文件头判断真实编码，不相信 URL 后缀；FLAC、OGG、OPUS、M4A、AAC、WAV、WMA、WebM 等非 MP3 内容使用 FFmpegKit 与 `libmp3lame` 转为 192 kbps、44.1 kHz、双声道 MP3。
- Android 23 兼容转码依赖固定为 `io.github.jamaismagic.ffmpeg:ffmpeg-kit-lts-full-16kb:6.1.4`；不提高应用最低系统版本。
- 受管理缓存写入层强制只接受 MP3，避免把非 MP3 文件改后缀冒充 MP3。
- 每个最终 MP3 在进入缓存目录前写入并重新读取校验 ID3v2.3：`TIT2` 歌名、`TPE1` 歌手、`TALB` 专辑；缺失专辑使用“未知专辑”，标签校验失败则本次缓存失败，不保存无信息 MP3。
- 设置抽屉宽度改为屏幕宽度约 60%；原歌单管理窗口和其他按钮的纵向位置保持不变。
- 打开设置抽屉时仅把系统状态栏背景切换为与抽屉一致的黑色，使黑色背景延伸到屏幕顶部；关闭后恢复原状态栏颜色。
- 缓存文件夹按钮不再显示“卸载后保留/卸载时清理”等附加文字，具体卸载行为仍在设置详情中说明。
- 歌单管理按钮文字由“新建在线/导出CSV”缩短为“新建/导出”。
- 版本提升为 `2026072703 / 2026.07.27.mp3-cache-settings-ui`。

### 轻量版：取消内置 FFmpegKit 转码

- 用户确认：APK 体积约 180 MB 过大，主要由 FFmpegKit 和相关 native 库导致。
- 本次仅保留设置栏相关界面修改：设置抽屉 60% 宽度、黑色背景延伸到状态栏、缓存文件夹按钮短文案、歌单管理“新建/导出”短按钮。
- 已移除 `ffmpeg-kit-lts-full-16kb` 依赖，避免把 FFmpegKit、libav*、libmp3lame 等大体积 native 库打入 APK。
- 轻量版仍优先向音乐桥请求 MP3/320k；若下载内容已经是真实 MP3，则写入并校验 ID3 后缓存。
- 若解析到的音频不是 MP3，轻量版不在手机端转码，不把非 MP3 文件改后缀保存为 MP3。
- 本地导入歌曲不做 MP3 转换，继续按本地文件原路径导入和播放。
- 版本提升为 `2026072704 / 2026.07.27.light-ui-no-ffmpeg`。

### 源格式回退与设置抽屉宽度修正

- 修正“优先 MP3”被误实现为“只接受 MP3”的问题。
- 在线歌单/网络歌曲仍优先请求 MP3；若实际下载到的是 M4A、AAC、OGG、FLAC、WAV 等非 MP3，则不再用 FFmpegKit 转码，也不拒绝播放，而是按真实源格式缓存和播放。
- 只有真实 MP3 会写入并校验 ID3 歌曲信息；非 MP3 仅保留友好文件名和隐藏 JSON 元数据。
- 设置抽屉宽度从 60% 调整为 70%。
- 设置抽屉黑色背景框延伸到屏幕顶部，内部歌单管理和按钮位置通过顶部 padding 保持与旧位置一致。
- 版本提升为 `2026072705 / 2026.07.27.light-ui-source-format`。

### 播放成功后再提交替换 flag

- 修正“搜索歌曲加入歌单后，原来源不可用自动切换到其他来源时，替换 flag 在播放成功前就写回歌单”的风险。
- 新增播放请求序号 `playbackRequestSerial`，缓存/解析线程返回时必须确认仍是当前播放请求，避免旧线程回写当前歌曲。
- 自动替换来源只先作为临时候选播放；只有播放器 `prepare/start` 成功后，才提交新的来源 flag、`catalogJson`、`cachedUri` 并保存歌单。
- 播放器失败时不保存替换来源，歌单内歌曲按原有不可用逻辑标记，提示“未写入替换来源”。
- 为 `MediaPlayer` 增加 `OnErrorListener`，真机解码或来源不可用时拦截错误，避免异步播放器错误直接冲掉应用状态。
- 版本提升为 `2026072901 / 2026.07.29.playback-flag-commit`。
### 2026-08-02 accepted APK-output baseline

- User supplied the accepted latest APK set in `E:\脚本\大宝贝儿老婆_apk\apk-output`.
- Accepted baseline version: `versionCode 2026080113`, `versionName 2026.08.02.direct-search-source`.
- Verified `大宝贝儿老婆_搜索播放源直传_正式签名.apk` SHA-256:
  `11fe07aaa76b8ca9d27f50fca03fbf8e2c3ed4cccd6067d13016a62830899d6f`.
- Replaced fixed-name APK outputs from the accepted files:
  `大宝贝儿老婆.apk`, `姜Lab.apk`, `李大财主.apk`, `牛逼.apk`.
- Verified all four APKs use `versionCode 2026080113`.
- Verified signing certificate SHA-256:
  `4cc298f33101b8c4c41866294e2739cd6f3b741e5a9f7aa01cb55983482d6b5d`.
- Older fixed-name APKs from `2026080109` were moved to `apk-output\旧版\archived_before_2026080113_20260802_140606`.
- GitHub branch expected to match this accepted release:
  `fix/multiformat-cache-priority-60s` at commit `fba8b78910543ec2cf4bbad601e2664c0bdd9dd7`.
- Local Git sync was not completed because `git fetch` hit `SEC_E_NO_CREDENTIALS`; `gh auth setup-git` could not write `C:\Users\22177\.gitconfig`; zip download fallback was blocked by the execution safety layer. Do not treat this as remote-synced.

### 2026-08-02 cache location and playlist-add boundary

- Fixed the search-play-to-playlist boundary:
  - Search playback must finish persistent cache storage first.
  - Adding the current searched song to a playlist no longer starts a second resolve/cache task.
  - If the current searched network song has not produced a readable cache file yet, the app asks the user to wait instead of starting another cache flow.
  - Playlist insertion now copies the verified song state, including `uri`, `cachedUri`, `lyric`, `catalogJson`, and `source`, rather than inserting the mutable search-result object directly.
- Network playback now checks `cachedUri` first; if the cache file is readable, it plays that directly instead of calling `NetworkMediaCache.cache()` again.
- `NetworkMediaCache.cache()` now verifies the URI returned by `CacheStorage.storeAudio()` is readable immediately after writing; failed writes surface as cache-folder errors instead of leaving fake cached state.
- Search-play cache naming continues to use the same managed cache convention as playlist songs: `title - artist [short-key].extension`, with paired lyric and hidden metadata files.
- Clear-transient-cache remains reference based: it keeps keys from playlists and only removes managed cache files that are not referenced by any playlist.
- Version bumped to `2026080114 / 2026.08.02.cache-location-join-boundary`.
- Validation: `:app:compileBabywifeclassicDebugJavaWithJavac` passed locally with project-local Gradle and Android user homes.
- Built release APKs for all four brands and signed them with `free-music-release-2026.p12`.
- Output fixed-name APKs were written to `E:\脚本\大宝贝儿老婆_apk\apk-output`.
- Verified all four outputs have `versionCode 2026080114` and signing certificate SHA-256 `4cc298f33101b8c4c41866294e2739cd6f3b741e5a9f7aa01cb55983482d6b5d`.
- ZIP packaging was not produced in this pass because the compression command was blocked by the execution safety layer.


## 2026-08-03 - Accept M4A network sources
- Added M4A to managed playable network-cache formats.
- Kept MP3 as the preferred resolve format and FLAC/M4A as source-format fallbacks.
- Bumped the four-brand Android build to v127.


## 2026-08-03 - Decrypt encrypted M4A before playback
- Confirmed the supplied sample is CENC-encrypted AAC in an M4A container.
- Ported the dependency library PlayAuth and AES-CTR decryption path to Android cache handling.
- Invalidates encrypted v127 cache entries and bumps all four brands to v128.

- Corrected user-visible cache filenames from `歌曲名 - 歌手 [哈希]` to `歌曲名 - 歌手`; old managed cache names migrate on the next access, with numeric suffixes only for real collisions.

- v129 corrects remaining legacy cache names and search ordering: `miyaki米芽奇` now prioritizes tracks whose title/artist combination exactly matches both terms.

- v130 fixes an accidental UI-label replacement where destructive and edit confirmation dialogs displayed “复制”. The real crash-report copy action remains unchanged.

- v131 accepts any format that the current Android device can actually prepare for playback. Acquisition priority is MP3 > FLAC > M4A > other; unplayable downloads are deleted before becoming cache files.
- v131 enforces one consistent cache basename (`title - artist`) across formats and removes older same-basename audio when the chosen format changes.

- v132 closes the IME after song/playlist search submission, adds a circular clear control to playlist search, and applies consistent subtle press feedback to all main button-like controls.

## 2026-08-03 - Full cache folder migration with all-files permission

- Fixed cache-folder changes skipping friendly files named `歌曲名 - 歌手.扩展名`.
- External-to-external and external-to-internal moves now enumerate every regular file in the old cache folder.
- Each copied file is SHA-256 verified before the selected cache location changes or old files are removed.
- Android 11+ now requests the system all-files management permission before opening the destination folder picker.
- Migration reports any old files that could not be deleted instead of silently claiming a complete move.

## 2026-08-04 - Single logical cache per song and deterministic search flow

- Cache reuse is now keyed first by normalized song title and artist, not only by source platform and catalog ID.
- Same-song playback/cache requests are serialized to stop repeated taps from downloading multiple source candidates concurrently.
- Source and format downloads remain temporary candidates until one final playable winner is selected.
- Only the winner is written to the user cache folder; other same-song source caches and temporary candidates are removed.
- Status text now distinguishes candidate download, candidate verification, final selection, and final cache completion.
