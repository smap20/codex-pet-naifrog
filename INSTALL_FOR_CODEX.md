# 给接收者 Codex 的安装说明

用户把本包交给你并请求安装后，请完成以下操作。本包面向 Linux，纯离线 Python 3.8+ 安装，不需要构建动画、下载模型或安装第三方库。

1. 解压到用户可读写目录，读取 README.md 和 install.py。用普通用户执行 `bash install.sh check`。运行目录可任意，入口根据脚本自身定位资源。
2. 检查会验证 SHA256SUMS.json，识别 App 的 package.json、版本和归档 SHA-256。若自动定位失败，查找用户实际安装的 `resources/app.asar`，再添加 `--app`。不要把 Codex CLI 当成桌面 App。
3. 本版可以直接升级已验证且文件未变的 v4.4 安装。仅当检查报告 supported=true 时，执行 `bash install.sh install`，非默认路径保留相同参数。不要 sudo 整个脚本，不要把宠物装进 root 的主目录。用户如使用 CODEX_HOME，保持该值；必要时显式指定 --codex-home。
4. 系统 App 目录可能需要 sudo；让用户在终端完成真实的系统权限提示。安装器会备份原 App 与既有奶蛙目录，生成并校验播放器扩展，再切换资源；异常时尝试恢复。本操作不涉及用户的聊天、登录数据或偏好设置。
5. 完成后核对 Codex 数据目录下 `naifrog-installer/installed.json` 的 status=installed，以及目标 pet.json 的 animationManifestPath=animation-v4.5.json。告诉用户完全退出并重新打开 Codex，然后从宠物列表选择“奶蛙”。不要自动杀死正在运行本次聊天的 Codex。
6. 如果版本或代码指纹不匹配，停止修改并报告具体版本与 SHA-256；保留当前 App。不要删除校验、硬套其他版本补丁，也不要声称仅复制 pet/ 就装好了完整动画。这需要针对实际版本另做播放器适配。

完整的状态映射、帧数、时长、拖动规则已经包含在素材清单中，保持不变。本包没有额外动作点播菜单。

撤销本包安装：普通用户执行 `bash uninstall.sh`（使用非默认数据目录时加同样的 --codex-home）。卸载会检查当前文件是否被后续修改，再恢复该次安装前的状态。
