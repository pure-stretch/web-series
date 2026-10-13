# 工具手册（给agent）

从仓库根目录执行，以下用项目ID `demo` 举例。命令不代表用户授权；先按WORKFLOW拿到相应确认。所有项目文件路径相对于`projects/demo/`，使用`/`，不允许逃出目录。

## 建项和文件

```sh
uv run python scripts/ws.py doctor
uv run python scripts/ws.py init demo --title "我的网剧"
uv run python scripts/ws.py inventory demo
```

init复制模板，里面的镜头、片尾署名、简介是待填写样例。先用真实剧本改写，不能直接当交付物。把需引用的输入复制到`projects/demo/references/`，原inbox不变。修改project.json的字体与模型实际价格，`price_checked_at`记日期。价格留空时付费命令会拒绝执行。

角色/空间写bible.json。每镜shots.json包含首帧、设计、台词、独立提示词、时长、revision；可选last_image、seed。新增版本文件名如E01-S01-v2.png，避免覆盖旧图。

## 审图与批准

```sh
uv run python scripts/ws.py validate demo
uv run python scripts/ws.py review demo image
uv run python scripts/ws.py import-review demo /path/to/用户导出的意见.json
```

打开输出HTML，用户逐镜选择状态、写意见，导出JSON交回。导入会核验项目、镜号、文件内容，不匹配则整份拒绝，避免半导入。缓存按项目＋版本隔离。每页当前覆盖shots.json全部镜头；大型项目可按集使用独立项目，或将待审集镜头临时整理后再生成页，保留原镜头清单副本。

聊天确认也能记录（必须是用户原话）：

```sh
uv run python scripts/ws.py approve demo image E01-S01 --evidence "用户：这张通过"
uv run python scripts/ws.py approve demo generation E01-S01 --evidence "用户：按这张图和台词试拍5秒"
```

image绑定图及画面设计和台词；generation进一步绑定提示词、模型参数等。保守地，修改shots字段也可能使generation批准失效。发布或渲染命令不强制艺术审阅通过，允许制作待审预览；生成命令才硬性检查审图及付费批准。

## 视频API（真实花费）

```sh
uv run python scripts/ws.py plan demo E01-S01
uv run python scripts/ws.py authorize demo E01-S01 --limit 1 --evidence "用户明确授权本轮一美元内试拍这一镜"
uv run python scripts/ws.py submit demo B0001
uv run python scripts/ws.py poll demo
uv run python scripts/ws.py balance demo
```

先plan，用户确认预算和范围后authorize。submit只提交该授权范围，每镜先落盘记录再请求。已有记录（包括失败/未知）不重复提交。poll只查询一轮；agent可间隔30—60秒再查，及时向用户报告进度。

预算是“按核实单价×秒数×安全系数”的本地保守占用，不是供应商账单硬限额。并发账户支出、改价、计费规则都可能使真实费用不同。每批前后核对balance/控制台；模板默认不释放失败任务费用，不擅自扩预算。不得用新authorize给旧授权续无限额度。

成功下载后，poll打印相对video路径，agent选定正确版本写入shots.json的video字段；不会自动把新输出覆盖到旧选片。然后生成video评审页：

```sh
uv run python scripts/ws.py review demo video
```

补接未知提交：`uv run python scripts/ws.py attach-task demo tasks/对应记录.json 供应商任务ID --evidence "控制台核实依据"`。该命令只补任务ID，不生成。

## 剪辑

填写timeline.json。每个clip的in/out及subtitles的start/end都是**原视频秒数**；先裁切、按单镜speed变速，再汇总字幕，最后整集speed变速。不会用固定“每字秒数”自动裁掉真实对白。每镜按输出画幅居中铺满，复杂环视/特别构图应由agent先生成独立剪辑片段；不要把通用中心裁切当作摄影判断。

```sh
uv run python scripts/ws.py render demo timeline.json
uv run python scripts/ws.py inspect demo edits/E01-v1.mp4 edits/check-E01-v1
```

字幕与片名自动烧录。output必须是未存在的新版本文件。带音轨的素材保留音轨，无音轨补静音。

配乐写到timeline.music数组，例如：

```json
{"source":"references/song2.mp3","source_in":0,"start":30,"end":34,"gain_db":-22}
```

start/end为完成各单镜裁切后、整集变速前的时间。短段淡入淡出并限制混音峰值；仍需听审各镜音量。背景音乐若不想随整集速度变化，应先固化对白速度，再以speed=1的时间线混音。

报幕：填credits.json的真实署名，可增加music字段引用已批准歌曲，`card demo credits.json`导出文字卡。只把报幕拼在最后一集；再用所有最终集拼合集，避免两次添加：

```sh
uv run python scripts/ws.py card demo credits.json
uv run python scripts/ws.py join demo edits/E05-final.mp4 edits/E05-v1.mp4 edits/credits-v1.mp4
uv run python scripts/ws.py join demo edits/collection-final.mp4 edits/E01-final.mp4 edits/E02-final.mp4 edits/E03-final.mp4 edits/E04-final.mp4 edits/E05-final.mp4
```

join会统一画幅/帧率/音轨后拼接，可能重新编码；应保留原始各集。字幕、封面、简介由用户确认后，填写delivery.json，发布教程用`templates/publish_tutorial.txt`为起点，按实际发布平台核对入口。

```sh
uv run python scripts/ws.py package demo delivery.json
```

输出ZIP和旁置checks.json。ZIP仅两个文件夹＋教程，checks留在外侧。发布不是此工具的功能，需要用户另行授权。

## Provider依据

默认模型及首尾帧参数参考[Atlas Mini官方接口](https://www.atlascloud.ai/docs/more-models/bytedance/seedance-2.0-mini-image-to-video/generateVideo)（2026-10-13核对）。历史项目已经真实调用；本模板本次只用mock验证API流程，不为了测试再次消耗用户余额。endpoint或模型升级后先核对供应商文档。
