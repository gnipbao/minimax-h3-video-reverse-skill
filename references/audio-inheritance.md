# 声音继承与反推

## 根问题：保留信号与理解内容是两件事

视频含音轨，只能证明存在音频流；FFprobe、波形、文件名与口型都不能证明歌词、曲风、声源或情绪。反过来，**听不到内容也不妨碍把同一条原始音频信号保留到成片**。将四件事分开记录：

1. **存在**：源文件是否有可读取的音频流，流索引、开始 PTS、时长和源文件哈希是什么。
2. **理解**：实际听过哪些时间段；自动转录、节拍检测和分离人声只是待复核线索。
3. **意图**：用户要原样保留、只借用声音特征、按事实重建，还是排除音频。
4. **路径**：目标界面能否实际提交视频/音频参考；若不能，是否有最终装配与音轨复用步骤。

保真任务且源文件确有音轨时，默认意图为**原样保留整条原声**。首轮内容确认只需说明“原声按原时间线保留；内容尚未核听”，除非声音本身决定故事理解，或用户要替换/扩写声音。`audio_status: unavailable` 描述的是内容核实状态，不是音轨不存在，也不自动把声音目标改成“新创作”。

## 路线选择

| 用户目标 / 可用能力 | 执行路线 | 不能声称 |
| --- | --- | --- |
| 原声必须与源文件完全一致；可装配成片 | 生成视觉后，移除新生成音轨，按源文件时间戳只铺回一次原始音轨；保留或有意识地处理原来的首尾空白 | 文字 Prompt 已复制波形；重新生成的人物已自动对准口型 |
| 希望 H3 直接接收源视频/音轨并尝试同步 | 核实当前平台支持 Ref2VA、素材实际提供且提交获得授权；用 `<Video N>`/`<Audio N>` 标明来源，并在 `retention_analysis` 中用 `fully_copy` 或 `partially_copy` 指明复制范围 | 仅写了 `<Audio 1>` 就表示文件已上传；模型输出必然与原信号逐样本一致 |
| 只借音色、律动或配乐风格，不直接复制 | Ref2VA 的 `reference` 关系；明确仅参考哪些**已核实**特征，实际附上音频参考 | `reference` 等同于 `fully_copy`；凭文件名猜出音色或歌词 |
| 用文字重建声音 | 实际听音、核对语句/语言、声源、起止时间与音画关联；源事实再进入 H3 对应字段 | ASR 草稿或口型推测是已核实对白 |
| 用户明确仅要视觉 / 源文件无音轨 | 声音字段按证据留 `N/A`，说明 `not_requested` / `no_track` | `N/A` 保证模型输出静音 |

准确复制与音画贴合是两个验收项。后期铺原声能保留信号，却无法使一个独立生成的嘴型自动跟上 Rap、对白或歌声；这些任务优先评估带原音频/原视频条件的 Ref2VA 或其它经核实的音频驱动流程。若当前界面不支持，明确提示口型风险，不把普通 T2VA/I2V 描述当成音频驱动。

## 实际处理顺序

1. 用 `scripts/probe_video.py` 核对音频流索引、音频与视频流的开始时间和时长。它只读元数据；其中 `audio_content_reviewed=false` 不得自行改成 true。
2. 若宿主能真正听音，先完整听或覆盖所有需要继承的段落；在切镜、说话人交替、入拍/停拍、动作落点、淡入淡出与尾部加密复听。逐段记录可听事实和不确定处，区分现场声、人物人声、环境层和观众侧音乐。没有听音能力时，保留整条音轨的路线仍可推进，不描述未听到的内容。
3. 建立**单一源时间线**：每个声源事件写源 PTS 范围、实际证据、所属人物或画外来源、跨切镜是否持续；短 Job 记录 `source_range_s → target_range_s`。原声不能随每个镜头从头播放，也不能因为画面切镜就重复歌词/节拍。
4. 如果目标改时长、重排镜头或换歌词，把原声复制范围、裁剪/伸缩/补声单独写为改编；原声已不能无修改地一比一继承。不要把原片 24 秒的音轨直接压到 15 秒视频而不说明变速或删减。
5. 验收两件事：音轨本身是否真的复用，音画是否对齐。检查开头、各硬切前后、说话人换气/开口、明显节拍动作及尾部；报告未测口型或音频差异，不因 Prompt 有 `fully_copy` 就宣称成功。

## H3 格式与交接

三字段 T2VA/I2VA/FL2VA 只承载文字描述。未听到的内容仍写：

```text
overall_soundscape: N/A
non_diegetic_music: N/A
```

在可复制块外附 `audio_handoff`：源媒体的私有路径或 ID、哈希、音频流索引、保留范围、源/目标时间映射、采用 Ref2VA 还是最终装配、是否已提交参考音频、需要复核的口型/节拍。不要把私有媒体路径或音轨打包进公开仓库。若使用 `scripts/compile_contract.py` 的可选 `audio_handoff` 输入，它会生成按交付路线覆盖整个源时间线的映射；不生成声波，也不替操作者完成混音。

官方全参考模式在**素材实际提交给模型**时可使用六段格式。以下只是关系骨架，具体声音内容未核实时不补歌词或乐器：

```text
subject_definitions:
<Video 1> is the actual source video for the target edit.
<Audio 1> is the synchronized original audio track from <Video 1>.

summary:
[video editing + audio reuse] The target edits <Video 1> while retaining <Audio 1> across the original timeline.

retention_analysis:
<Audio 1>: fully_copy - reuse the complete original signal as the target soundtrack without restarting at shot cuts.

detailed_description:
[Shot 1] The visual performance follows the timing of <Audio 1>; describe only observed actions and verified sound cues.

overall_soundscape: N/A
non_diegetic_music: N/A
```

`fully_copy` 是目标关系指令，**不是生成结果的证明**。若素材只提供给分析者，没有送入 Ref2VA，不使用这个骨架冒充已上传；改用装配交接。官方格式与关系定义见 [MiniMax H3 Ref2VA 提示词指南](https://github.com/MiniMax-AI/MiniMax-H3/blob/main/.agents/skills/h3-prompt-writing/references/ref-en.txt)；当前平台是否开放相同上传与复制能力要另核实。

## 反测：双人棚拍 Rap

输入：约 24 秒的双人吊麦表演，音轨存在但宿主无法听取，画面可看到双方口部与手势变化。保真反推且用户未要求换声。

- 正确首轮：复述**可见**互动，说明具体歌词/曲风未核实，并默认原声继承；只问影响表演含义的疑点，不把“换一段说唱配乐”设成默认选项。
- 正确最终：H3 三字段中不编唱词和配器；块外给原音轨一次性复用的时间线交接。若要让模型直接跟随原声，则先确认 Ref2VA 音频素材真实提交及当前入口支持，再交接六段关系；后期铺回原声的版本标明口型风险。
- 失败信号：`audio_status: unavailable` 被解释成“原声无法保留”；切成多个 Job 后每段重复音轨开头；仅写“保持原声”却没有音频素材/装配步骤；声称没核听却写出 Rap 歌词、BPM 或突然停乐。
