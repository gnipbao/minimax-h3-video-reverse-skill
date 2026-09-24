# H3 提示词适配

核实日期：2026-09-20。官方入口：[H3 文档与 FAQ](https://design.minimax.io/h3)、[官方代码与技能](https://github.com/MiniMax-AI/MiniMax-H3)。格式依据已安装的官方 `h3-prompt-writing` 的 base/ref 指南；此处为独立整理的工作约定，不复制整份上游指南。

## 先核实平台

官方 FAQ 在核实时说明最长 15 秒，并区分 FL2VA 与 Ref2VA。不同平台、工作流和版本可能进一步限制时长、分辨率或参考素材。运行前核实当前界面/接口；不要硬编码未知模型 ID、API 字段、价格或并发。

本 Skill 负责反推与提示词，不内置 API 客户端，不需要密钥。示例 10 秒只是创作长度；30 秒需分段编排，不代表单次支持 30 秒。

## 三字段

T2VA 直接开始：

```text
integrated_multimodal_description: [Shot 1] ...

overall_soundscape: ...

non_diegetic_music: ...
```

主描述包括同步动作、声音事件、对白、镜内变化和剪辑时刻。声景字段避免重复已写的对白；配乐字段只放观众侧音乐。必要约束用自然句合入主描述，不另发明第四个负面提示字段。

## I2VA：单首帧

把下面对齐行放第一行，空一行，再写三字段：

```text
For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.
```

`<Picture 1>` 必须对应将要提交的实际首帧。若当前只有首帧 Prompt，标为待生成/待附图；不能声称已对齐现有图片。

开场从该图片真实状态继续。保持项与运动项分开考虑，但在 H3 主描述中自然组合。不要把另一个尚未发生的动作结果放进初始帧。

## FL2VA：首尾帧

只有确认平台支持且图片已选定/计划明确时使用。按官方格式填入实际末镜编号与目标时长：

```text
How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot N) aligns with the S.SS-second mark of the target video.
```

例如单镜 8 秒，N=1、S.SS=8.00。描述可见中间变化如何接近尾帧，不仅写“从 A 变 B”。默认单连续镜头；真实切镜不塞入首尾插值。

源尾帧的 PTS 可能是 7.96 秒，生成目标终点可以是 8.00 秒。前者是源证据，后者是生成任务的端点定义，两者分别记录。

## 镜头与时间

- 第一镜用 `[Shot 1]`，不开头追加切镜时刻。
- 后续镜头用 `[Shot 2] At 00:03.500, ...`，编号连续、时刻递增且小于 Job 时长。
- 源视频只有 0.1 秒定位能力时，`00:03.500` 的末两位是格式补零。
- 每个独立 Job 的镜头、图片编号重置；源 Shot ID 留在编排表，不进入复制块。
- 不确定是推轨还是变焦时，描述“主体在画面中逐渐变大，景别收紧”，不伪造设备或镜头参数。

## 声音冲突的处理

通用创作指南可能倾向补全声景；保真反推必须服从证据边界。

| 来源情况 | 处理 |
| --- | --- |
| 已实际核实声音 | 写入相应字段 |
| 用户明确要求新增声音 | 标为改编后写入，不归因于原片 |
| 没有音轨 | 未确认字段 N/A，块外写 `no_track` |
| 有音轨但未能听取内容 | 未确认字段 N/A；保真目标默认另给原声复制交接，不把 N/A 当静音或放弃原声 |
| 用户要求真实音频复刻，但关键声音缺失 | 状态 PARTIAL；先解决音频访问，不伪造可执行声纹/对白 |

`N/A` 是本反推交付中的省略标记，不承诺平台一定生成静音。用户要求绝对静音时，需在平台/后期工作流中核实实际输出。

对原声继承，先读 [声音继承与反推](audio-inheritance.md)。普通三字段提示词没有输入音频波形的能力；要原样复用，需实际提交 Ref2VA `<Audio N>`（核实当前入口支持）或在视觉成片装配后铺回原音轨。官方全参考格式用 `fully_copy` 指明原声完全复用，用 `reference` 指明只借音色/节拍；二者不能互换，也不能把本地文件已被分析误称为已送入模型。`fully_copy` 是请求，不是成片结果证明。

对白使用稳定 `(S1)`；`<d>[Chinese] 原句</d>` 只放语言标记和实际语句。跨切镜延续用 `<scenetrans>`，实际片尾截断用 `<cutoff>`。若声音不是屏幕人物发出，不要强制其对口型。

## Ref2VA 与 L2VA 的边界

H3 全参考模式使用 `subject_definitions / summary / retention_analysis / detailed_description / overall_soundscape / non_diegetic_music` 六段。需要它时交接官方 `h3-prompt-writing` 与当前平台文档，输入已核实的事实表、素材角色和保留/改动要求。缺少该可选技能不影响本包的三字段路线。

参考素材标签与说话人 ID 分开管理：Picture 是帧图、Video 是整体视频关系、Audio 是实际引用音轨、Subject 是可复用视觉内容。仅“分析过某视频”不表示该视频已经上传给 H3。

L2VA 会推演前态；仅有尾图时不能声称反推出真实源动作。用户授权创作后才使用相应路线。
