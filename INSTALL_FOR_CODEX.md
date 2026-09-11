# 给接收者 Codex 的安装说明

用户把本包交给你并请求安装后，请按以下流程操作。本包支持 Linux 与 macOS，使用 Python 3.8+ 标准库；安装动画不需要下载模型、pip 或 Node 依赖。

1. 解压到用户可读写目录，读取 `README.md` 与 `install.py`，以普通用户运行 `bash install.sh check`。入口根据脚本自身路径定位资源，当前目录可任意。
2. 检查会验证 `SHA256SUMS.json`，读取 App 的 `package.json`，并匹配平台、版本、完整 `app.asar` 和目标 JavaScript 模块的 SHA-256。若自动定位失败，Linux 用 `--app /实际目录/resources/app.asar`；macOS 用 `--app "/Applications/ChatGPT.app"`。不要把 Codex CLI 当成桌面 App。
3. 仅当检查报告 `supported=true` 时，运行 `bash install.sh install`，并保留检查时使用的参数。不要移除指纹校验、套用近似版本或手工替换未知构建。
4. 如用户设置了 `CODEX_HOME`，保持该值；必要时显式传入 `--codex-home`。宠物安装到该目录的 `pets/naifrog`，备份与记录位于 `naifrog-installer/`。

## Linux

受支持版本为 `26.903.61454` 且代码指纹匹配。系统 App 目录可能需要 `sudo`；不要 sudo 整个脚本，安装器仅在写入 `app.asar` 时请求权限。安装器备份原 App 与既有奶蛙目录，异常时双向回滚。已验证的 v4.4 可直接升级。

## macOS

已验证 Apple Silicon 版本：`26.903.71938`、`26.908.31748`，且代码指纹必须匹配。默认目标为 `~/Applications/ChatGPT Naifrog.app`，也可用 `--target-app` 指定另一个 `.app` 路径。

macOS 流程不会覆盖 `/Applications` 中的官方 App。安装器复制完整 bundle，在副本里重建 `app.asar`，更新 `Info.plist` 的 `ElectronAsarIntegrity`，进行 ad-hoc 深度签名并用 `codesign --verify --deep --strict` 复验，最后才原子切换 App 和宠物目录。修改后的副本不再保留 OpenAI 的开发者签名或公证身份；必须把这一点如实告诉用户。

不要自动终止当前 App 或聊天。安装完成后告诉用户：

1. 完全退出官方 ChatGPT/Codex App。
2. 打开安装记录中 `targetBundle` 指向的“奶蛙”App。
3. 在宠物列表选择“奶蛙”；必要时按设置中的刷新按钮。
4. 不要同时运行官方 App 与奶蛙副本。官方 App 升级后，等新版本指纹获支持，再重新生成副本。

## 完成检查与撤销

完成后核对 `${CODEX_HOME:-~/.codex}/naifrog-installer/installed.json` 中 `status=installed`，以及目标 `pet.json` 的 `animationManifestPath=animation-v4.5.json`。macOS 还应有 `mode=macos-side-by-side`、`targetBundle` 和 `installedAsarIntegrity`。

普通用户运行 `bash uninstall.sh` 撤销；非默认数据目录要带相同的 `--codex-home`。卸载会先检查 App、签名、Electron 完整性和宠物是否被后续修改。Linux 恢复安装前的 App 与宠物；macOS 仅移除记录中的并排副本并恢复宠物，官方 App 始终不动。

若检查失败，报告实际平台、版本与 SHA-256 并停止。不要声称只复制 `pet/` 就完成了 1401 帧安装；完整动作依赖本包经过构建指纹约束的播放器扩展。
