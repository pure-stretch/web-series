# 网剧制作工作台

把剧本和素材放进 `inbox/`，让能访问本地文件的 ChatGPT Work / Codex 按 `START_HERE.md` 开始制作。Windows 与 macOS 使用同一份流程和 Python 工具。

这是从五集《我在拉伸店当卧底》的完整制作过程提炼的模板：**先定角色和空间，再逐镜审图，确认后做视频；只重做有问题的镜头。**

## 换电脑怎么开始

1. 安装 Git、[uv](https://docs.astral.sh/uv/getting-started/installation/)、FFmpeg（含 ffprobe、libass）。让 agent 帮你检查安装即可。
2. clone 本仓库，在 ChatGPT / Codex 中打开这个本地目录。
3. 把剧本、人物及场景图片放到 `inbox/`，音乐可一起放入。
4. 复制 `.env.example` 为 `.env`，填入 Atlas Cloud API key；也可以在当前会话的环境变量中提供。
5. 对 agent 说：

> 请先读 START_HERE.md 和 STATUS.md，盘点 inbox，检查环境，然后按标准流程开始。先给我项目理解、缺项和预算方案；未经确认的镜头不要生成视频。

你不需要自己操作下面的命令。它们供接手的 agent 使用。

```sh
uv run python scripts/ws.py doctor
uv run python scripts/ws.py init my-series --title "新网剧"
uv run python scripts/ws.py inventory my-series
```

## 流程与产物

**8环节、35步**的分工和确认点见 [流程](docs/WORKFLOW.md)。操作命令见 [工具使用](docs/TOOLS.md)，换机及续作见 [环境与迁移](docs/SETUP.md)。

| 目录 / 文件 | 用途 |
|---|---|
| `START_HERE.md` | 新窗口启动指令，替代依赖旧聊天记忆 |
| `inbox/` | 用户原始剧本和素材，只读使用 |
| `templates/` | 项目、人物场景、镜头、剪辑、交付模板 |
| `projects/<项目>/` | 该项目状态、图、视频、评审、API任务与批准记录 |
| `deliveries/` | 分集＋合集＋发布教程的最终ZIP |
| `scripts/` | 跨平台命令，不依赖盘符、PowerShell或curl.exe |

## 可运行的范围

- 环境检查、素材清单、项目初始化、版本指纹、逐镜HTML审图/视频评审、JSON意见导入。
- Atlas Seedance Mini：费用估算、批准范围检查、提交、单次轮询、下载、断点续作和不明提交防重。
- FFmpeg：镜头裁切/单镜速度、无音轨补静音、字幕和片名、配乐混音、整集变速、合集、报幕文本卡、抽帧/解码检查、最终打包。
- 本地可选ASR。默认不下载大模型；agent按需要启用。

剧本拆镜、审美、图片生成和质量判断由 agent 在会话中完成。图片优先用当前窗口内置图片工具；本仓库不能给没有图片权限的账号增加权限。没有图片工具时，停在出图步骤说明缺项，不用占位图冒充已完成。不同供应商的视频API需要新适配器，不能只换一个key就视为兼容。

默认 **不提交任何付费请求**；需要用户确认模型、范围、重试额度和本轮上限。没有真实key也能跑测试、演示和所有本地剪辑。

## 验证

```sh
uv run python -m unittest discover -s tests -v
uv run python scripts/smoke.py
```

smoke在临时目录合成小测试片，不使用inbox、不联网、不消耗视频额度。不配置GitHub自动检查。每次换电脑，由接手agent先运行doctor、上面的基础测试和smoke，解决环境问题后再制作；实际验证范围见 `STATUS.md`。

代码与模板使用MIT许可证。用户放入的剧本、人物、音乐及生成资产不自动适用本仓库许可证。
