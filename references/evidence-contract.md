# v2 反推事实契约

目的：每句生成文案有来源，多个模式共享事实，修改后旧复核不能继续使用。它不能替代实际看视频，也不能验证“帧里确实发生了这件事”。

## 从视频到可复制提示词

1. 实际观看完整时间线；动作快、遮挡或疑似切镜处补看连续内容。先记录视觉终点和末帧。
2. 写证据条目：实际帧/片段/音轨、源文件哈希、真实时间范围、本地证据文件及哈希。
3. 写最小事实：一个可检查的状态或动作一条；英文输出时在这一层翻译一次。不同模式不重复编造文案。
4. 分配 Job：源范围、目标时长、参考帧对应的状态 ID。每条交付路线完整覆盖源时间。
5. 编译：生成三字段 H3 块、首帧、Motion、尾帧以及事实 ID 清单。
6. 媒体复核与语义复核完成后填写当前摘要的复核记录。严格检查通过后再标注交付状态。

仅格式草稿或没有工具的聊天任务可以人工执行同一流程；不得把它标为脚本验证过的生产包。

## 最小字段说明

完整可编译教学输入见 [evidence-contract.input.json](../examples/evidence-contract.input.json)。它是虚构案例；媒体路径和哈希是占位值，不能作为实测证据。

| 部分 | 内容 | 规则 |
| --- | --- | --- |
| source | media、duration_s、timestamp_precision_s、visual_access、audio_status | duration 是视觉范围；media 包含 path、sha256 |
| capabilities | max_job_duration_s、duration_verified、end_frames、audio | audio = supported / unsupported / unknown；独立于是否听过源音轨 |
| segments | id、kind=shot、start_s、end_s、end_condition | 完整连续覆盖；黑场/字卡要保留；end_condition = settled / ongoing / cutoff / unknown |
| evidence | id、kind、range_s、source_sha256、asset | kind = frame / clip / audio；单帧起止时间相同，使用真实 PTS |
| facts | id、segment_id、kind、range_s、status、evidence_ids、text | 一条一句可观察内容；时间在字段中，不在 text 中重复手写绝对时刻 |
| jobs | id、mode、source_range_s、duration_s、opening_fact_ids、closing_fact_ids、reference_images | mode = T2VA / I2VA / FL2VA；图像资源包含 path、sha256 |
| derived | 编译生成的 Prompt、参考图文案、事实 ID | 不手工编辑；重新生成可以逐字比对 |
| compilation | 编译器版本、input_digest | 绑定全部输入；不是人工复核证明 |
| reviews | media、semantic | 记录真实执行者、具体核对事项、相同的 input_digest |

所有媒体路径相对契约所在目录，也可使用本机绝对路径。CLI 输出到不同目录时会重定位相对路径，并据新输入重新编译；原观察文件保持不动。真实契约保留在私有运行目录，开源仓库仅放教学输入。

## 事实的精度

`kind` 支持 identity / initial / state / action / camera / ending / transition / soundscape / music。

- identity：在声明时间段内稳定的外观、数量或空间锚点。变化前后的属性分开记录，不把后半段造型塞进首帧。
- initial / state / ending：开场、过程状态、实际终帧。参考图只能引用边界附近的静态状态；动态过程放 action。
- action：动作链的一个阶段。多个接触之间存在撤回时分开；明确先后可以加 `after: ["F05"]`。仅在前驱确实先结束时用 after，同时动作不硬排因果。
- camera：先用背景关系判断运镜，不能把主体靠近一律写成镜头推进。
- transition：剪辑变化，附在相邻 Shot 的实际时间段。淡出不等于环境变暗。独立黑场/字卡作为独立 Shot 保存。
- soundscape / music：分别写声音与观众侧配乐。只凭画面无法建立音频事实。

事实状态与证据类型是两件事：

- observed：必须引用相符通道的直接证据。运动需要连续片段或至少两个不同时间的帧；这些只是最低结构要求，不能保证中间动作已看清。
- uncertain：保留在缺口清单，不编入任何模式的生成文案；analysis_status 为 PARTIAL。
- user_requested：新加的内容；必须有 request 原话或准确转述，并明确 intent=adapted 与 intentional_deviations。它不是视频观察事实。

事实范围采用源秒数，不能越过所属 Shot。单帧必须小于视觉结束时刻；连续事实可延伸至 Shot 的排他结束边界。静态首尾事实尽量使用真实帧时间；时间精度字段只表示观察精度，不能放大来掩盖缺少末帧。

## 模式与分段

T2VA、I2VA、FL2VA 由相同事实自动投影。每个 Job 的时间、Shot 和 Picture 标号独立重置；事实仍保留全片源时间。

DUAL 的两条路线分别从源起点覆盖到终点，不能拿文生版本的尾段替代图生版本的遗漏。I2VA/FL2VA 每个 Job 只能落在一个真实 Shot；T2VA 可包含多个真实切镜。FL2VA 需要确认首尾帧能力、两张图和边界附近的终态事实。

拆一个连续镜头时，后一 Job 的 opening_fact_ids 必须绑定切分点的实际状态。例如 0–5 秒已经把杯子举到嘴边，5–10 秒的首帧不能退回桌上。跨分段长动作应在连续状态锚点处分成可观察阶段；校验器拒绝未拆分却跨过 Job 边界的 action/transition，避免一句包含完整“开始到完成”的长事实在两段各执行一遍。

保真模式要求目标时长等于源范围长度。明确授权改时长时可用 adapted，编译器等比例重映射时间；压缩会改变节奏，必须披露。主体替换、删剧情或把源硬切改成一镜到底，应保留源档并另写明确的目标改编方案；当前 v2 编译器不自动替换/删除已观察事实，不能靠追加矛盾事实假装完成改编。

## 运行和复核

在仓库根目录运行：

```bash
python3 scripts/compile_contract.py examples/evidence-contract.input.json --output /tmp/h3-contract.json
python3 scripts/validate_contract.py /tmp/h3-contract.json
```

第二条通过表示声明和派生输出相符。此教学例尚未观看媒体，以下命令**应当失败**：

```bash
python3 scripts/validate_contract.py /tmp/h3-contract.json --require-reviewed
```

对于真实任务，实际看完媒体、逐条核实事实和参考图片后，才按下面结构填写 reviews。将占位摘要换成 compilation.input_digest；不要把下面的示例直接当成已复核证明。

```json
{
  "media": {
    "status": "reviewed",
    "input_digest": "<当前编译摘要>",
    "reviewer": "<实际执行者>",
    "notes": "<实际观看范围、关键动作加密范围、最后有效帧与尾段核对结果>",
    "evidence_ids": ["<逐项实际查看过的证据 ID>"],
    "full_timeline_viewed": true,
    "tail_rechecked": true
  },
  "semantic": {
    "status": "reviewed",
    "input_digest": "<当前编译摘要>",
    "reviewer": "<实际执行者>",
    "notes": "<事实与图像、接触顺序、终态、无新增声音、两种交付形式的检查结果>",
    "fact_text_checked": true,
    "route_parity_checked": true,
    "reference_alignment_checked": true
  }
}
```

再运行：

```bash
python3 scripts/validate_contract.py /path/to/contract.json --require-reviewed --verify-local-media
```

`generation_ready=true` 会强制同样的复核与本地文件校验，并要求真实媒体与已核实平台时长。设置这一输入值也会改变摘要，因此应先确认资源齐备、设置它、重新编译，然后执行最终复核。它不表示已经生成视频。

改源文件、事实文案、时间、Job 或能力参数都会使摘要失效；重新编译后旧 reviews 自动变成 unreviewed。只改 derived 会被逐字比较拒绝。未改输入而重新编译，会保留仍有效的复核。

复核记录是执行者声明，不是数字签名，也不是视觉识别器。文件哈希只能确认本地字节未换；不能证明图片来自声明的时间、文案准确或生成结果相似。不要替从未查看的证据填写 reviewed。

## 兼容与故障处理

- schema_version=1 保留格式检查，始终是旧草稿；不能通过严格门槛或声明 generation_ready。不要只把版本号改成 2。
- 缺少证据：补实际观看与采样，或将事实降为 uncertain。不要拿同一帧伪装多个时刻。
- 丢失阶段：在事实层补原片真实动作并重新编译两套版本，不能只补某个输出字符串。
- 音频门控失败：确认是否实际听过、目标是否支持声音；任一不成立时不编入音频事实。
- 本地文件校验失败：检查相对目录和哈希；更换图片后重新检查构图和边界状态。
- 语义仍有矛盾：回到媒体核查；校验器不能替你裁定。
