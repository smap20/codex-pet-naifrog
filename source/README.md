# 素材处理源码记录

安装只使用已经完成并校验的 `../pet/`，不执行本目录里的动画处理脚本。

`laugh-source.mp4` 是捧腹大笑源视频；`upstream-build-assets.py` 是 GPL-3.0 上游背景处理源码。`fix-gaps.py`、`repair.py`、`build.py` 保存本次手部间隙、移动眼睛/手脚恢复及固定尺度图集组装的改动；这些是历史工作区处理脚本，依赖其中记载的中间帧和布局，并非独立安装入口。

`my-naiwa-sources.json` 给出七段其他源视频的固定提交、路径和 Git blob SHA1。完整上游链接和许可状态见 `../SOURCES.md`。图集是多个来源的组合，不能仅依据其中一份 LICENSE 推断所有素材的许可。

处理过程使用 FFmpeg、NumPy、SciPy、Pillow、OpenCV；原始分割还用到 RMBG 1.4、MobileSAM 和 GrabCut。它们都不是安装或播放依赖，也没有打入本包。
