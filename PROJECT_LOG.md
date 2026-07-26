# Project Log

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

## 2026-07-26.2

### 公开库完整功能修正

- 顶部设置按钮与搜索入口之间保留圆形扫把按钮，搜索入口使用剩余宽度。
- 播放操作按钮默认隐藏，并根据当前歌曲上下文动态显示：
  - 歌单歌曲只显示“替换歌曲 / 替换歌词”；
  - 未加入歌单的搜索歌曲只显示“加入当前歌单”。
- 搜索歌曲加入歌单后立即切换到对应歌单播放队列；未加入时继续使用搜索结果队列。
- 新增独立缓存存储层：
  - 默认使用应用内部缓存根目录；
  - 设置中可选择外部缓存总文件夹；
  - 自动创建各歌单同名子文件夹和“缓存”子文件夹；
  - 搜索与替换缓存进入“缓存”，搜索歌曲加入歌单后迁移到歌单目录；
  - 歌单改名时同步尝试改名缓存目录；
  - 扫把只清理“缓存”子文件夹，并清除对应内存状态。
- 自动替换与手动替换改为相似度排序，不再只允许完全同名同歌手；手动候选在确认前必须实际验证可播放。
- 歌单歌曲自动替换失败后先允许手动处理；只有自动失败且手动遍历所有来源仍无可播放候选时才标红。成功播放或替换后自动取消红色。
- CSV 导出保留原有前八列，并追加歌词内容、本地 URI、目录 JSON、缓存 URI、缓存文件夹和失效状态；导入同时兼容旧八列格式与新完整往返格式。
- 设置抽屉顶部“设置”文字已移除，原有头部占位和其余布局顺序保留；新增“歌单缓存位置”按钮，长按可恢复默认位置。
- 姜Lab flavor 新增首次启动验证框架：
  - 真实口令及其哈希不进入公开源码；
  - 本地 `private.properties` 或 GitHub Secret 注入 SHA-256；
  - 验证成功后仅在本机保存通过状态，后续不再提示；
  - 其他三个品牌不启用该验证。
- 新增五分钟无输出构建看门狗、功能静态验收脚本和四品牌 GitHub Actions 构建流程。
- 本次修改同时记录于 `PROJECT_LOG.md` 与 `docs/CHANGELOG.md`，两份日志随同一提交同步到公开库。
