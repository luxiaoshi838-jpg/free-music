# v148 缓存状态与非歌单清理修复

## 问题一：文件存在且可播放，但仍显示缓存未完成

v143 在缓存文件已经过下载、解密和真实音轨探测并写入缓存后，加入歌单时仍会对 `content://` URI 再执行一次同步 `MediaExtractor + MediaPlayer.prepare()`。部分 Android 文件提供器会在这一步返回失败，即使同一个文件已经存在并可以正常播放，因而产生“缓存未完成”的误判。

v148 将“缓存是否完成”恢复为受管理文件状态检查：文件必须存在且不能仍为加密 M4A。真实音轨探测仍保留在写入缓存之前，没有取消异常音频验证。

## 问题二：扫把无法删除未加入歌单的缓存

外部缓存文件使用 `歌名 - 歌手.格式` 的友好名称。旧清理逻辑虽然从 `.babywife_<key>.json` 元数据中读到了真实文件名，但删除阶段只遍历受管理名称，友好名称文件没有进入删除列表。

v148 在原清理之前遍历用户选择缓存文件夹的全部直接子文件，按照元数据删除不属于任何歌单的音频、歌词和元数据文件。

## 版本

- versionCode: `2026080148`
- versionName: `2026.08.05.v148-cache-state-cleanup`
- Workflow: `Build v148 Cache State and Cleanup Four Brands`
- Artifact: `v148-cache-state-cleanup-four-brand-apks`
