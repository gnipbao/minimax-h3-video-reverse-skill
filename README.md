# MiniMax H3 视频反推 Skill

**给 AI 一段参考视频，先确认它看懂了什么，再拿到可以复制使用的视频提示词。**

把视频中的人物、动作、镜头、叙事和声音交接，整理成 MiniMax H3 文生视频或逐镜图生视频提示词。你可以纠正 AI 的理解，也可以明确要求压缩时长、换主体或改成一镜到底。

由 [知识猫 / gnipbao](https://github.com/gnipbao) 维护，提供 Agent Skill、使用教程、原创示例和本地校验工具。支持 **AUTO · T2VA · I2V · DUAL**。

[快速开始](#快速开始) · [使用示例](#使用示例) · [工作原理](#工作原理) · [声音怎么继承](#声音怎么继承) · [文档与示例](#文档与示例) · [开源赞助商](#开源赞助商)

## 开源赞助商

感谢支持本项目的开源赞助商。

| 赞助商 | 服务介绍 |
| :---: | --- |
| <a href="https://www.whatstoken.ai/register?aff=1000984916"><img src="assets/sponsors/whatstokenai-logo.png" width="100" height="100" alt="WhatsTokenAI 品牌 Logo" /><br /><strong>WhatsTokenAI</strong></a> | 统一 AI 模型 API 接入平台，提供兼容 OpenAI 格式的接口，方便开发者接入多种 AI 模型。<br /><br />[注册体验](https://www.whatstoken.ai/register?aff=1000984916) |

## 快速开始

准备一个支持 `SKILL.md`、能够实际读取完整视频的 Agent，以及你要反推的参考视频。Skill 本身不包含 H3 模型，不自动生成视频，也不要求 API Key；生成环节在你选择的视频平台完成。

**1. 安装到 Codex**

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
git clone https://github.com/gnipbao/minimax-h3-video-reverse-skill.git \
  "${CODEX_HOME:-$HOME/.codex}/skills/minimax-h3-video-reverse"
```

目标目录已存在时，先检查已安装版本，避免覆盖自己的修改。其他支持 `SKILL.md` 的 Agent 可将整个仓库放到其技能目录，发现方式以宿主文档为准。普通聊天界面可以提供 [SKILL.md](SKILL.md) 及所需参考文档，但仍须具备实际的视频理解能力。

**2. 附上视频，发出请求**

在能发现该技能的新会话中发送：

```text
$minimax-h3-video-reverse
帮我反推附件视频。先用中文复述内容、动作和叙事逻辑，等我确认。
确认后给我一段完整的英文提示词，保留原片镜头、动作顺序与结尾。
有音轨时默认保留原声，并说明实际继承方式。
```

**3. 确认或纠正，拿到提示词**

| 交互阶段 | 你会看到什么 |
| --- | --- |
| AI 先复述 | 视频发生了什么、动作如何相连、最后停在哪里，以及影响结果的关键疑点 |
| 你确认或纠正 | 回复“理解正确”，或直接指出人物关系、动作顺序、视觉效果等需要修正的地方 |
| AI 交付 | 按已确认的理解给出完整提示词，或逐镜首帧、动态提示词与装配说明 |

默认中文沟通、英文 Prompt。“一段就行”只约束最终格式；明确说“不用确认，直接写”可以跳过确认。同一素材与目标确认后，改语言、合并段落或切换交付模式直接复用，不重复询问故事。

## 选择输出方式

不确定时用 **AUTO**；只想拿到一段完整提示词，可以直接像上面那样说明。

| 模式 | 适合需求 | 交付内容 |
| --- | --- | --- |
| **AUTO** | 让 AI 根据视频决定 | 按外观与时间信息选择合适路线 |
| **T2VA** | 文生视频，描述完整时间线 | 自包含的全片描述与 H3 三字段 Prompt |
| **I2V** | 先锁定外观，再生成动作 | 每镜首帧或首尾帧 Prompt、Motion Prompt、约束与装配说明 |
| **DUAL** | 同时需要整体与逐镜方案 | 基于同一事实表的 T2VA 与 I2V 两套版本 |

I2V 默认采用单首帧。只有平台支持首尾帧、且尾帧能帮助约束变化时，才采用首尾帧路线；真实切镜保留在装配中。详细交付格式见 [输出契约](references/output-contract.md)。

## 使用示例

以下请求都沿用“先理解、再确认、后交付”的流程。你也可以在确认后继续要求“改成中文”“合成一段”或“给图生视频版本”。

<details>
<summary><strong>逐镜复刻：首帧 + 动态提示词</strong></summary>

```text
$minimax-h3-video-reverse
完整检查附件视频，输出 I2V。保留真实镜头，不压缩时间。
每镜给独立首帧提示词、动态提示词、H3 块和镜间装配说明。
中文解释，英文 Prompt；对白与画面文字保留原语言，未核实的内容不要补写。
```

</details>

<details>
<summary><strong>明确改编：改成 10 秒一镜到底</strong></summary>

```text
$minimax-h3-video-reverse
以附件视频为依据，改编成 10 秒的一镜到底 I2V。
保留主角身份、动作先后与结尾表情，允许用连续收紧景别替代切镜。
说明原片与改编的差异，以及时长变化后原声需要怎样处理。
```

</details>

<details>
<summary><strong>长视频：按 30 秒段落组织</strong></summary>

```text
$minimax-h3-video-reverse
把附件长视频反推后按 30 秒叙事段落组织。
先核实目标 H3 平台的单次时长，超过上限就拆成多个生成任务。
给每个任务的源时间映射，交接人物、道具、动作状态和连续音轨。
```

</details>

## 工作原理

反推需要回答具体问题：谁先动、碰到了哪里、遮挡之后还在不在、镜头是在移动还是切换、最后的动作有没有完成。本 Skill 先建立这些事实，再把它们写成生成指令。

```mermaid
flowchart LR
  A[参考视频与目标] --> B[完整观看与关键动作复查]
  B --> C[镜头、动作与状态事实]
  C --> D[复述内容与表达]
  D --> E{用户确认}
  E -->|纠正| B
  E -->|确认或明确跳过| F[编写对应模式的提示词]
  F --> G[核对时长、首尾状态与声音交接]
```

1. **完整看，再补细节。** 从全局浏览、真实切镜、连续时间覆盖，到关键动作加密检查，最后倒查首尾与末段。
2. **追踪变化。** 分开记录人物动作、相机运动、道具持有、接触、遮挡和终态；未知内容不靠常识填满。
3. **确认表达。** 剧情核对因果和反转，舞蹈核对动作，艺术展示核对层次与视点变化，操作演示核对步骤与反馈。
4. **从同一组事实写输出。** 文生与图生版本共用镜头顺序、事件和结尾；工程化生产包通过事实契约编译，修改后重新复核。

| 常见误读 | 本 Skill 的处理 |
| --- | --- |
| 把触碰、撤回、再次接触合成一个动作 | 拆开接触与分离，让反应跟随真正的触发事件 |
| 道具被遮住，就写成消失 | 追踪持有、遮挡与再出现的状态 |
| 连续拉远或环绕，被误写成切镜 | 依据画面与空间关系识别真实剪辑边界 |
| 空间笔触有层次，被写成均匀切片 | 描述可见结构与视差，不猜制作软件或算法 |
| 片尾仍在行驶，却补成停车到达 | 保留真实截止状态与余波 |

更多规则与反测条件见 [历史经验](references/historical-lessons.md)。这些规则不能替代实际观看；脚本也不能判断 AI 是否看懂了画面。

## 声音怎么继承

**有原音轨且没有要求换声时，默认保留原声。** 是否存在音轨、是否听清内容、怎样把声音送入成片，是分别核对的三件事。

| 目标 | 实际做法 |
| --- | --- |
| 原样保留声音 | 生成视觉后移除新音轨，按原时间线只铺回一次完整原音轨；切镜与分段不重播音频开头 |
| 用原音频约束生成 | 核实目标入口支持 Ref2VA，并实际提交参考素材；用 `fully_copy` 表达原声复用目标，再检查结果 |
| 用文字重建或重新设计 | 只写实际核听的声音事实；新增配乐、对白或声效明确作为用户要求的改编 |

未核听内容时，不猜歌词、音色、曲风或音效。H3 声音字段中的 `N/A` 表示未写入声音事实，不表示原片静音。**文字 Prompt 本身不携带原始波形，后期铺回原声也不会自动让新画面对准口型。** 说唱、对白与舞蹈需要单独核对音画同步；改时长或重排镜头时，也要调整声音方案。

完整流程见 [声音继承与交接](references/audio-inheritance.md)。

## 使用边界与验证状态

- **完整视频是依据。** 只有截图、缩略图或打不开的链接时，只能分析可见部分，不能补造完整时间线。
- **分段服从平台能力。** “30 秒段落”是编排需求；单次生成时长与首尾帧、音频参考能力，以目标平台实际支持为准。格式见 [H3 适配](references/h3-adapter.md)。
- **生成由你接续。** 本项目交付提示词与素材交接说明，不自动调用付费生成、上传视频或发布作品。
- **验证范围公开。** 当前为 **0.4.0 候选版本**，并非已发布的 GitHub Release。自动校验覆盖结构、链接、事实契约和回归行为；H3 成片相似度、口型与生成效果尚未完成对照。详见 [验证记录](docs/validation.md)。

## 文档与示例

| 想了解什么 | 从这里开始 |
| --- | --- |
| Agent 如何执行完整流程 | [SKILL.md](SKILL.md) |
| 确认、纠正与多轮修改 | [确认协议](references/narrative-confirmation.md) · [原创教学对话](examples/04-narrative-confirmation.md) |
| 10 秒动作与逐镜 I2V | [动物动作示例](examples/01-cat-and-ball.md) |
| 首尾帧如何约束变化 | [产品展开示例](examples/02-product-unfolding.md) |
| 长片如何拆成实际任务 | [30 秒分段示例](examples/03-long-video-plan.md) |
| 能力不足时怎么办 | [观察边界](references/video-observation.md) · [人工反测](examples/retest-prompts.md) |
| 工程化编译与复核 | [事实契约](references/evidence-contract.md) · [v2 教学输入](examples/evidence-contract.input.json) |
| 每次改进的依据与验证 | [0.2 事实绑定](docs/evolution-0.2.md) · [0.3 人机确认](docs/evolution-0.3.md) · [0.4 声音继承](docs/evolution-0.4.md) |

示例均为原创教学设定，不附第三方视频，也不作为真实视频观察或模型生成记录。

<details>
<summary><strong>开发者：本地辅助工具与仓库结构</strong></summary>

阅读 Skill 和使用聊天流程不要求 Python。编译与检查工具需要 Python 3.10+；媒体探测需已安装 FFprobe，抽帧另需 FFmpeg。脚本使用 Python 标准库，不自动下载依赖或读取密钥。

```bash
# 在仓库目录运行：检查结构、链接、示例与回归
python3 scripts/check_repo.py

# 核对本地视频元数据；不代表已看过画面或听过声音
python3 scripts/probe_video.py /path/to/reference.mp4

# 选取关键帧，并自动包含首尾帧；输出后仍需实际观看
python3 scripts/sample_frames.py /path/to/reference.mp4 \
  --output /tmp/h3-frames-new --at 0.5 2 4
```

生产包的编译与严格检查见 [事实契约](references/evidence-contract.md)。真实任务需要当前用户确认或明确豁免，以及实际媒体和语义复核。教学输入只用于格式演示，不能直接声明生成就绪。校验器检查声明与文件一致性，不验证用户是否真的确认，也不判断生成画面是否相似。

```text
SKILL.md                 Agent 入口与执行协议
agents/openai.yaml       Codex 显示信息
references/              观察、确认、声音、输出与 H3 适配
examples/                原创教学案例与人工反测
scripts/                 PTS 抽帧、事实编译与仓库检查
tests/                   契约、分段、确认与声音交接回归
docs/                    验证范围、版本演进与回滚记录
```

用户素材、证据和生成结果保存在自己的项目目录；`outputs/`、`runs/` 和媒体默认忽略。

</details>

## 参与改进

欢迎通过 [Issues](https://github.com/gnipbao/minimax-h3-video-reverse-skill/issues) 反馈误读、漏镜、动作顺序或声音交接问题。描述使用场景、预期结果与实际输出，并提供可公开的最小复现材料，会更容易定位问题。提交代码修改前运行 `python3 scripts/check_repo.py`。

## 来源与许可

本项目根据维护者的方法模板与历史反推实践整理，整理方法为 [dao-skill](https://github.com/gnipbao/dao-skill)。完整来源边界见 [provenance](references/provenance.md)。

原创代码、文档与教学示例采用 [MIT License](LICENSE)。MiniMax H3 模型、官方资料和第三方素材保留各自许可。本项目为社区整理，与 MiniMax 官方没有隶属关系。
