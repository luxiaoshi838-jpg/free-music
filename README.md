# Free Music

四品牌音乐 APK 本地部署源码。

当前包含四个品牌版本：

| 品牌 | 包名 | Gradle 任务 |
| --- | --- | --- |
| 大宝贝儿老婆 | `com.jianglab.babywife` | `assembleBabywifeclassicDebug` |
| 李大财主 | `com.jianglab.babywife.lidacaizhu` | `assembleLidacaizhuDebug` |
| 姜Lab | `com.jianglab.babywife.jianglab` | `assembleJianglabDebug` |
| 牛逼 | `com.jianglab.babywife.niubi` | `assembleNiubiDebug` |

构建要求：

- JDK 17
- Android SDK Platform 35
- Android Build Tools 35.0.0
- Gradle 8.7，首次可运行 `初始化GradleWrapper.ps1` 生成 wrapper

Windows 构建：

```powershell
.\构建四品牌APK.ps1
```

Linux / WSL 构建：

```bash
./build_four_apks.sh
```

成功后 APK 输出在 `本地构建输出/`。

注意：公开库不包含正式签名私钥。默认构建为 Debug APK，可以测试功能，但不能覆盖使用旧正式私钥签名的已安装版本。
