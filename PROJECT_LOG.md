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
