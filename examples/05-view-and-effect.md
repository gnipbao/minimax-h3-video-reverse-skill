# 多表面产品：动作完整，效果仍可能遗漏

原创教学场景，不对应任何用户素材。时间、帧和事实 ID 均为设定；未附媒体，不能标为实际观看或生成就绪。

## 设定与旧版失败

一个硬壳展示盒包着蓝色织物外套。原片先拍正面，硬切到背面操作，再硬切回正面。背面操作镜长 3 秒：两手已经握住向上卷起的下缘，后表面的棋盘格标签露在卷边下方；织物中间的系带开口被压成低矮形状。手向下、略向外拉，布片展开并遮住开口两侧的标签区域，开口变成竖长形，白色交叉绳变得清楚。结尾手仍握住下缘，硬壳没有形变。

失败文案：“Product close-up. Both hands pull the edge downward to show flexibility.” 它有动作，却没有背面方向、初态、覆盖变化和开口几何；不能作为保真反推合格答案。一个正面 Picture 也未提供背面纹样与系带结构。

## 在现有事实中补齐

| 必保项 | 教学证据 | 事实与分配 | 输出核对 |
| --- | --- | --- | --- |
| 背面方向及结构 | 背面操作镜初帧 | F01 initial：背面、棋盘标签、压矮开口 | 静态与 H3 初态句 |
| 卷边初态 | 初帧 | F02 initial：卷边在上，两手已经握住 | 静态与 H3 初态句 |
| 覆盖和开口变化 | 初/中/末帧 | F03 action：向下展开，覆盖标签两侧，开口由矮变长 | Motion 与 H3 变化句 |
| 实际截止 | 末帧 | F04 ending：手仍握持，硬壳不变 | Motion 与 H3 终态句 |

实际任务应将“教学证据”换为真正查看过的证据 ID 和时间。不能凭上述表格伪造 observed。

背面镜使用自己的背面初帧作为 Picture 1。首帧只包含操作前的状态，不提前画成展开后的终态。前后硬切由装配恢复，不能生成盒子转身或织物自动复位。

## 单镜 H3 I2VA 可复制格式示例

```text
For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.

integrated_multimodal_description: [Shot 1] Use Picture 1 as the initial state of this three-second rear-view product close-up. The rigid display box is wrapped in a blue fabric sleeve. Its lower edge is rolled upward, leaving checkerboard labels exposed on the rear surface below the roll; the central laced opening is vertically compressed, with white cords crowded together. Two hands already hold the left and right ends of the rolled edge. They pull downward and slightly outward, unrolling the fabric across the rear surface and covering the label areas on either side of the opening. The compressed opening progressively extends into a tall vertical opening, separating the visible white cord crossings. Finish with both hands still holding the lowered edge and the rigid box unchanged. Keep the rear view and framing continuous.

overall_soundscape: N/A

non_diegetic_music: N/A
```

仅作格式演练：`python3 scripts/validate_prompt.py PROMPT.txt --mode I2VA --duration 3 --source-shot-count 1 --audio-omitted`。源镜数量来自此教学设定，不是脚本识别结果。

## 人工反测

- 删掉背面方向与表面结构，仍有“拉下缘”：判失败，缺视角锚点。
- 删掉露出→覆盖、矮开口→竖长开口，只留下“展示弹性”：判失败，缺视觉结果。
- 将“手仍握持”改成“松手并恢复原形”：判失败，扩写截止后的行为。
- 给三个硬切镜头只上传正面图，再要求“一段 I2V”：保持逐镜 Job，不能把排版偏好当连续改编授权。
- 只有正面且无展开的另一个产品视频：不强加背面、系带、卷边或变形，不制造锚点。

这些结论需要独立观察/语义判断。自动关键词命中不证明效果理解正确；格式通过仅说明文字满足声明的 H3 结构。
