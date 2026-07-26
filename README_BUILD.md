# 大宝贝儿老婆 APK 工程

这是“大宝贝儿老婆”Android APK 的公开源码复刻工程。

## 当前状态

- 应用名称：大宝贝儿老婆
- 包名：`com.jianglab.babywife`
- 主入口：`app/src/main/java/com/jianglab/babywife/MainActivity.java`
- 当前公开仓库不包含正式签名文件、签名密码或私有签名缓存。

## 本地构建

Windows 可运行：

```powershell
.\build_local_apk.ps1
```

默认生成位置：

```text
app\build\outputs\apk\debug\app-debug.apk
```

也可以在安装 JDK 17、Android SDK 35 和 Gradle 8.7 后运行：

```text
gradle --no-daemon assembleDebug
```

## GitHub Actions

公开仓库只构建 debug APK。构建步骤若连续五分钟没有新增日志，会被判定为可能卡住并自动停止。

## 仓库约定

仓库只保存源码、配置和构建脚本；APK、测试截图、临时构建目录和本地签名材料不提交。