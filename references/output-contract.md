# 输出契约

## 输入约定

```text
参考视频：本地文件或能够实际读取的视频
输出模式：AUTO / T2VA / I2V / DUAL（默认 AUTO）
任务：保真反推 / 明确改编
Prompt 语言：英文（默认）/ 中文
目标时长：沿用原片或用户指定
声音：保留原始音轨（默认保真且有音轨）/ 按已核实事实重建 / 仅视觉 / 用户另行设计
目标平台：名称、单次时长、首尾帧能力；未知可留空
交互：默认先复述并等待确认；已有当前确认直接复用；明确免确认时记录跳过
```

输出模式是交付形式；H3 T2VA/I2VA/FL2VA 是生成任务形式，两者不要混为一列。`I2V-B` 是本 Skill 的镜头路线名，不是 API 模型 ID。

## 第一阶段：内容理解与确认

新素材先输出中文复述：视频内容、事件因果或视觉表达、真实结尾、目标保留/改动与关键疑点，然后请求用户确认或纠正。不要先写英文 Prompt 再问“满意吗”。具体纠正与复用规则见 [确认协议](narrative-confirmation.md)。

`interaction_status=WAITING_FOR_CONFIRMATION` 是对话阶段；`analysis_status` 仍按媒体证据填写。确认前可继续观察、记录事实，不能交付 T2VA/I2V/DUAL 提示词。用户明确跳过则注明 waived，不声称 confirmed。格式要求“一段提示词”不跳过这一步。

确认完成后的最终内容必须与当前复述一致。H3 三字段保持原样，不把用户问答或确认字段塞进生成块。仅要一段的用户得到一段生成描述，必要能力说明放块外；一段文本不代表平台能够单次生成任意时长。

## 状态说明

放在复制代码块之外，保持短小：

```yaml
analysis_status: PARTIAL
scope: visual
audio_status: unavailable
timestamp_precision_s: 0.1
intent: faithful
interaction_status: WAITING_FOR_CONFIRMATION
notes: 视觉范围已核对；声音内容未核实。N/A 不代表原片静音。
```

上述只是格式示例，不得直接沿用为当前任务事实。若 `audio_status: unavailable` 而源音轨存在并打算沿用，在状态说明中另写 `audio_delivery: original_track_handoff`；`N/A` 不是音轨交接。能力不足时返回：

```yaml
analysis_status: BLOCKED
missing_capability: 无法读取完整视频及其时间线
required_input_or_capability: 可访问的完整视频与视频理解能力
```

## AUTO 的决策

| 判据 | 默认交付 |
| --- | --- |
| 视觉身份主要由首帧表达；后续为连续动作 | I2V |
| 整体时间演化与叙事信息占主导 | T2VA |
| 外观锁定和时间演化都重要，单一路线明显丢信息 | DUAL |

题材不能决定模式。“动物”不必然 I2V，“广告”不必然 T2VA。用户明确选择的输出优先；无能力支持的部分说明缺口。

## T2VA

```text
integrated_multimodal_description: [Shot 1] <风格、初始构图、时间演化与终态。> [Shot 2] At <真实切镜时刻>, <转场及新状态。>

overall_soundscape: <已核实的持续声景；未核实或无相应内容时 N/A。>

non_diegetic_music: <已核实的观众侧配乐；未核实或无相应内容时 N/A。>
```

主描述自包含。不要使用“如原视频”“参照截图”代替人物、动作或状态；真正送入模型的图片对齐标记不属于这种省略。原声不在三个文字字段内，见 [声音继承与交接](audio-inheritance.md)。

## I2V 逐镜生产包

共享视觉锚点只放跨镜头真实稳定的内容。混合媒介或昼夜变化不要强行锁定为全片同一风格/光照。

```text
global_visual_dna: <真实共享锚点；无全片规律可省略。>

[Shot 01]
time_range: <源时间起点 → 源时间终点>
i2v_type: I2V-A
reference_frame_time: <真实参考帧时间>
reference_image_prompt: <独立可用的静态初始画面。>
i2v_motion_prompt: Use the reference image as the initial visual state. <保持项、动作、运镜、终态。>
i2v_negative_constraints: <镜头级必要约束，或 N/A。>
```

I2V-B 使用 `start_frame_time / start_frame_prompt / end_frame_time / end_frame_prompt` 替代单帧字段。Motion 写从初态到终态的连续路径，不只列两幅画面。

以上是人用的生产包。另给每个生成任务的 H3 三字段块，见 `h3-adapter.md`。尾帧 Prompt 不能假装为已存在图片；真正运行时需要生成/选择并上传对应图像。

镜间装配表至少记录：源镜头、剪辑次序、转场类型、转场持续时间、需继承的身份与状态。原声继承时另保留一条跨镜连续音轨与源/目标时间映射，不能给每个镜头重新配上整段音频。真实硬切留在装配中；淡出不得误写成天色变暗。

## DUAL

顺序为：

1. `global_visual_dna`
2. `T2VA_VERSION`：三字段
3. `I2V_SHOT_PACKAGE`：逐镜帧图和运动
4. 需要时附装配表

两套方案复用相同 Shot 划分、实体与事件。因模式造成的信息分配差异可以存在，终态相互矛盾不可以。

## 用户改编与多轮修改

在源事实之外维护 `intentional_deviations`：具体改变、用户要求、目标时间与保留项。例：“将原两镜改为 10 秒连续收紧景别；保留举杯→饮用→看镜头的顺序”。不声称原片本来就是一镜到底。

只重写用户要求改变的部分。实际参考图优先于旧生图文案；用户修正事实后需要回查视频，不能仅把更顺口的说法当证据。剧情、关键动作、视觉机制、终态或声音目标发生改变时更新复述；已明确“按这个改完直接写”则无需再问。只改语言、排版或模式不重新确认叙事，必要的平台和参考图检查仍执行。

## 30 秒与长视频

“30 秒段落”是编排层；单次模型生成长度由平台限制决定。若平台上限为 15 秒，30 秒可以编排为两个不超过 15 秒的 Job；切分优先落在已有切镜或动作停顿，必要时拆成更多短 Job。

源时间不随分段改变。每个 Job 重置目标时间与 `[Shot 1]`，另列源范围。跨 Job 传递：主体外观、道具、持有关系、空间方向、光照进度、动作未完成状态。不要让每段重新关上已打开的门或重新拿起已握住的道具。

不要为凑整秒截断关键动作，也不要把一段长动作自动加速；若平台限制迫使改变节奏，标为改编并说明具体影响。

## 可选机器契约

新生产包用 `examples/evidence-contract.input.json` 的 v2 事实结构，另按 [确认协议](narrative-confirmation.md) 建立真实任务的 narrative_review，再按 [证据契约](evidence-contract.md) 编译和复核。若选择最终装配原声，可选填 `audio_handoff: {"method": "postproduction_copy"}`，同时把 `scripts/probe_video.py` 返回的 `audio_track_present`、`audio_stream_index`、`video_start_s`、`audio_start_s`、`audio_duration_s` 记入 `source`；编译器给 T2VA/I2V 各自生成连续映射与音频相对画面起点的偏移，严格本地校验核对真实流索引。这条路线只声明音轨交接，不声称口型已同步；Ref2VA 六段格式仍按平台能力单独交接。

教学输入没有用户确认，只能编译为兼容草稿；不能复制它绕过新任务确认。首帧与 Motion、H3 三字段都来自同一组事实；直接改派生文案会被拒绝。每条交付路线必须独立覆盖源时间线，分段首帧必须符合切分点当前状态。用户素材路径、截图与证据账本留在私有运行目录。

`examples/contract.json` 是 v1 兼容格式草稿；不能声明生成就绪。v2 中 `generation_ready` 会要求当前叙事确认或明确豁免、有效媒体/语义复核、已核实平台时长和本地素材哈希通过，但仍不代表模型已运行或输出已通过相似度检查。教学例的资源未附带，该值必须为 false。
