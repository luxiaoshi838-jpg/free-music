# v153 歌单播放中途停止修复与报告

- `versionCode 2026080153`
- `versionName 2026.08.06.v153-playback-stop-report`

## 已确认的问题

v151/v152 的搜索后台 Range 缓存把“本次响应少于请求的 4 MiB”直接判断为歌曲下载完成。部分 CDN 会返回较小的合法分段，因此旧逻辑可能把歌曲前半段保存为完整缓存。文件头仍可播放，但播到截断位置就会停止。

## v153 修改

- HTTP 206 必须带有效 `Content-Range`；
- 每段起点必须与已写入字节连续；
- 每段正文长度必须等于声明长度；
- 必须下载到服务端声明的总长度才算完成；
- HTTP 416 只有在已写入长度等于总长度时才算正常结束；
- 播放前和播放结束时比较缓存时长与歌曲目录时长，明显过短的缓存会被删除并重新获取；
- MediaPlayer 错误、无回调停止、播放进度卡住、播放器对象消失、Activity 在播放中被销毁都会写入可复制报告；
- 播放器无回调停止时自动尝试恢复一次；
- 设置中的报告入口改为“播放/闪退报告”。

## 报告原因

- `media-player-error`：MediaPlayer 返回错误码；
- `playback-stopped-without-callback`：播放器停止但没有错误或完成回调；
- `playback-position-stalled`：播放器仍声称在播放，但进度 12 秒没有变化；
- `player-disappeared-without-error-callback`：播放器对象被释放或丢失；
- `cached-duration-short-before-start`：缓存开始播放前就确认时长明显不足；
- `cached-audio-ended-before-catalog-duration`：缓存提前播放结束；
- `activity-destroyed-during-active-playback`：播放期间 Activity 被销毁。当前播放器仍由 Activity 持有，若真机报告出现这一项，后续应把播放器所有权迁入前台播放服务。

## 验证

GitHub Actions run `31079587556` 已通过 v151 Range 回归、v152 连续切歌回归、v153 播放中断专项检查、四品牌 Android 编译、包名和版本号检查。自动构建不能代替真机连续播放验证。
