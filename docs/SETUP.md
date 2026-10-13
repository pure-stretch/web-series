# 环境与换机

## 首次准备（agent执行）

1. 确认当前目录是仓库，检查Git/Python工具、FFmpeg与中文字体；不要假定Windows盘符或旧电脑的缓存存在。
2. 安装uv及带libass的FFmpeg发行版；FFmpeg和ffprobe必须在PATH。macOS可用Homebrew，Windows可用winget或发行版安装。安装前核对包名及现有版本，避免改动系统默认Python。
3. 在仓库根目录执行 `uv run python scripts/ws.py doctor`。uv使用项目`.venv`；Python要求3.11及以上，不依赖全局pip。随后运行`uv run python -m unittest discover -s tests -v`和`uv run python scripts/smoke.py`；这两项只做本地验证，不消耗视频额度。换机后的agent负责检查结果，并写入STATUS；失败时先排查环境，不直接进入付费生成。
4. 本地复制 `.env.example` 到 `.env` 并填key；文件不提交。不要把key写进命令历史、截图、提示词或日志。
5. 初始化项目，设置中文字体，然后做一次字幕样片检查。Windows默认Microsoft YaHei，Mac默认PingFang SC；若跨机要求完全一致，两边安装同一套Noto Sans CJK SC，并写相同字体名。字体文件没有随仓库分发。

新窗口需能读写仓库并运行本地命令，网络和D盘等额外权限按当前环境申请。普通网页聊天仅上传几份文件，不等于具备本地完整制作环境。

## 图片和视频能力

- 图片：当前窗口内置图片工具，使用用户可用的技能说明。生成完复制到项目`images/`或`covers/`，并保存提示词和参考路径。无图片能力时明确停止出图，不能把“有Atlas视频key”视为图片能力已配置。
- 视频：仅内置Atlas Mini适配器；供应商模型权限、余额、定价仍由账户决定。换供应商需按其当前官方文档添加适配器并先小样验证。
- 声音：模型原生对白和现有音乐由时间线混音。跨镜统一音色靠试听及参考，模板不承诺自动锁声线。
- 本地ASR：可选`uv run --extra asr python scripts/transcribe.py 视频 输出.json --model base --download`。首次联网下载模型需告知用户；后续去掉`--download`使用缓存，默认不联网找模型。

## 三种迁移

**新电脑开新剧**：clone仓库 → 准备工具 → inbox放新素材 → 配本机key → 读START_HERE。

**同一个项目续作**：除clone，还要安全复制`inbox/`和`projects/<id>/`；重要的有STATUS、project/shots/timeline、approvals、budgets、tasks、所有图片视频音乐。审图浏览器缓存不会迁移，先导出意见JSON。重新运行doctor、validate，再核实未完成任务状态；已有提交不能重发。

**只交付运营**：只给`deliveries/*.zip`。里面不含key、任务状态、生成提示词或源项目。

这些目录被Git忽略是有意设计：避免把私人剧本、肖像、体积很大的成片和供应商记录默认传到公开仓库。需要云端同步素材时，另行确定私有存储/备份方案。

## 恢复异常

- `unknown/submitting`：查供应商控制台对应时间和镜头，确认任务ID后用attach-task接回。若确定未创建，也不要删旧记录，增加revision再取得新尝试授权；这样历史费用占用仍可追溯。
- `submit.lock`：先查进程，确认没有任务正在提交才移走锁；不能靠删锁绕过并发保护。
- `completed`但未下载：重跑poll，下载不重新提交生成。签名链接过期时重新查询任务。
- 素材已改：旧批准不适用于新版本；先展示变更，按用户授权范围继续。

参考：官方[技能机制](https://learn.chatgpt.com/docs/build-skills)。本仓库采用显式START_HERE入口，不要求用户安装仓库技能，也不生成/修改AGENTS.md。
