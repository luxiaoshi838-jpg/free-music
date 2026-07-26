# Free Music

四品牌音乐 APK 的公开源码工程。

| 品牌 | 包名 | Gradle 任务 |
| --- | --- | --- |
| 大宝贝儿老婆 | `com.jianglab.babywife` | `assembleBabywifeclassicDebug` |
| 李大财主 | `com.jianglab.babywife.lidacaizhu` | `assembleLidacaizhuDebug` |
| 姜Lab | `com.jianglab.babywife.jianglab` | `assembleJianglabDebug` |
| 牛逼 | `com.jianglab.babywife.niubi` | `assembleNiubiDebug` |

## 当前功能

- 搜索歌曲、歌单播放、歌词匹配和手动替换。
- 搜索歌曲加入歌单后，下一首自动切换到该歌单队列。
- 自动替换和手动替换均按相似度搜索，并验证候选是否真正可播放。
- 自动与手动替换都失败的歌单歌曲会标红。
- 顶部扫把按钮清理搜索及替换产生的临时缓存。
- 可选择缓存总文件夹；内部自动建立歌单同名目录和 `缓存` 目录。
- CSV 歌单支持旧格式导入，并支持完整状态往返导入导出。
- 姜Lab 版本支持仅首次启动验证，真实验证信息不保存在公开源码中。

## 构建要求

- JDK 17
- Android SDK Platform 35
- Android Build Tools 37.0.0
- Gradle 8.7

## 姜Lab 首次验证配置

公开仓库只保存验证框架，不保存真实口令或哈希。构建四品牌前：

```bash
python3 scripts/generate_jianglab_passphrase_hash.py
```

复制 `private.properties.example` 为 `private.properties`，把脚本输出写入：

```properties
JIANG_LAB_PASSPHRASE_SHA256=<64位SHA-256>
```

`private.properties` 已加入 `.gitignore`。GitHub Actions 也可以使用同名 Repository Secret。

## 本地构建

Windows：

```powershell
.\构建四品牌APK.ps1
```

Linux / WSL：

```bash
./build_four_apks.sh
```

构建脚本会检查姜Lab 私有哈希，并在单步骤连续五分钟没有新增日志时停止。成功产物位于 `本地构建输出/`。

公开库不包含正式签名私钥。默认生成 Debug APK，不能覆盖使用旧正式证书签名的安装包。
