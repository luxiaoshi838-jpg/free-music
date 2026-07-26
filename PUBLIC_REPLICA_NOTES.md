# 公开复刻说明

本仓库是私有开发仓库当前 `main` 源码的公开快照，不复制私有 Git 提交历史。

## 已复制

- Android 应用源码与 Manifest
- Gradle 配置和本地构建脚本
- 图片、图标和 XML 资源
- 架构检查脚本
- 适用于公开仓库的 debug APK 构建工作流

## 主动排除

- `.jks`、`.keystore`、`.p12`、`.pfx` 等私钥材料
- 正式签名密码和凭据
- 私有 Actions 签名缓存
- 签名导出工作流
- `签名/`、`signing/` 和 `signing-export/`
- APK、AAB、构建目录和本地配置
- 私有 Git 历史

## Actions 防卡死规则

公开构建工作流会记录 Gradle 输出。若单次构建连续五分钟没有新增日志，将停止该构建并返回失败，避免任务长期卡住。
