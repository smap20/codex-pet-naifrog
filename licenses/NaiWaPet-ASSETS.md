# 素材来源与许可

## 奶蛙参考视频

- 文件：`assets/source/Naiwa.mp4`
- 来源：[CHENGONGSHUO/Naiwa - Assets/Video/Naiwa.mp4](https://github.com/CHENGONGSHUO/Naiwa/blob/master/Assets/Video/Naiwa.mp4)
- 来源仓库许可：GNU General Public License v3.0
- SHA-256：`1c05a2a8af2052f2f0a5909f917cf3f1146215a3e5b51542a2f349dc05987e08`
- 源视频参数：约 15.4 秒，1080 × 1474，约 30 FPS，包含音轨

本项目按照来源仓库给出的 GPL-3.0 条款保留视频，并把整个项目按 GPL-3.0 发布。公开传播或 AI 生成并不自动等同于“无著作权限制”；因此这里明确记录当前可核验的来源、许可和改动，而不是宣称素材属于公有领域。

## 素材处理流程

`tools/build_assets.py` 会从上述视频可复现地生成运行时素材：

1. 固定为 30 FPS，并按 Lanczos 缩放为 294 × 400。
2. 通过边缘连通背景、受限抗锯齿扩张和前景连通分量移除白底及地面残影。
3. 为边缘生成轻微透明羽化，不修改角色动作顺序。
4. 把 462 帧打包为 8 张透明 PNG 图集。
5. 为每帧生成像素级点击掩码 `hitmask.bin`。
6. 提取单声道 22,050 Hz PCM 音轨；应用中默认开启，用户可随时关闭。
7. 从首帧生成应用图标，并生成文档预览。

生成文件位于：

- `src/NaiWaPet/Assets/Animation/`
- `src/NaiWaPet/Assets/Audio/laugh.wav`
- `src/NaiWaPet/Assets/App/`
- `docs/preview.png`

运行 `python tools/verify_assets.py` 可校验源文件哈希、图集布局、点击掩码和音频参数。

素材生成脚本会根据实际输入视频自动写入项目内相对路径和 SHA-256；离线校验器还会确认清单声明的图集与仓库中提交的图集完全一致。源视频仍需保存在项目目录内，避免在清单中留下不可移植的本机绝对路径。

## 参考范围

项目中提交的奶蛙像素与声音均由上述单一源文件生成。其他桌宠项目和网络上的“奶蛙捧腹大笑”公开视频仅作为形象、动作节奏、交互方式与工程设计参考。

若素材权利人认为来源或许可记录不准确，可通过仓库 Issue 联系维护者，以便核验并及时处理。
