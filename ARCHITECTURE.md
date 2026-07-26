# Android 应用架构

本工程是独立运行的原生 Android 音乐应用，不依赖电脑端 WebView 服务。

## 入口

- 包名：`com.jianglab.babywife`
- Activity：`app/src/main/java/com/jianglab/babywife/MainActivity.java`
- 最低 Android API：23
- 目标 Android API：35

## 主要模块

当前应用以单 Activity 方式实现：

- 搜索页：本地及在线歌曲目录搜索
- 播放页：音频播放、播放模式与歌词显示
- 歌单页：播放、删除和管理当前歌单
- 设置抽屉：歌单管理、本地音频导入与背景图片设置
- 数据存储：使用 `SharedPreferences` 保存歌单、当前歌曲和播放位置
- 网络访问：通过 `HttpURLConnection` 读取公开音乐目录和歌词接口

## 架构检查

`scripts/verify_architecture.py` 会确认入口源码不存在以下旧壳架构标记：

- 电脑端服务端口 `17878`
- Android 模拟器宿主地址
- 本机回环音乐服务
- `android.webkit.WebView`

公开 GitHub Actions 在构建 APK 前先执行该检查。
