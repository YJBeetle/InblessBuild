# InblessBuild

公开的构建入口。`Inbless` 子模块固定私有项目的提交；源码不会复制提交到本仓库。

## 使用

在本仓库 Settings → Secrets and variables → Actions 配置：

- `INBLESS_READ_TOKEN`：仅对私有 Inbless 仓库开放 Contents read 的 fine-grained PAT。
- `ARTIFACT_PASSWORD`：独立的长密码，用于加密安装包和诊断日志。

每次 push 自动构建；也可使用 Actions → Private source build → Run workflow 手动运行。PR 不触发构建；同一 ref 的新运行取消旧运行。三个平台并行构建：macOS arm64 的 DMG、Windows x64 的 NSIS、Linux x64 的 DEB。执行子模块中的 SDK 构建、格式、Clippy、离线测试、Tauri 打包和安装包校验，不发布 Release。

每个平台只上传一个 AES-256 加密的 `.7z`，同时加密文件名，保留 7 天。内部包含已验证安装包、校验和与完整构建日志。失败时也尝试上传加密诊断日志；未生成安装包则只有日志。用 7-Zip 打开并输入 `ARTIFACT_PASSWORD` 对应的密码即可。

公开 Actions 页面仅显示各检查阶段的状态，不输出私有构建日志。第三方依赖安装、检出路径和固定提交标识仍可见。不要给此入口添加外部 PR 触发，不缓存私有源码或编译输出到公开 Actions cache。

## 更新源码版本

子模块使用固定提交，不会在构建时自动跟随分支。需要新版本时，在本地更新后提交父仓库的 gitlink：

```sh
git -C Inbless fetch origin
git -C Inbless checkout origin/codex/rust-tauri-ios
git add Inbless
git commit -m "build: 更新 Inbless 版本"
git push
```

构建需要遵守 GitHub Actions 的使用政策。此入口不改变源码授权或可见性。
