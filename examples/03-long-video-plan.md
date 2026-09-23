# 30 秒段落与单次生成任务

**原创编排示例，非模型执行记录。** 假设一段 30 秒源视频有三个真实镜头，目标平台已核实单次上限 15 秒。

另假设内容与目标已获用户确认。实际新任务先复述叙事、结尾和目标，再交付这里的分段方案；“按 30 秒写”本身不是免确认。

| 源 Shot | 源时间 | 源事实与终态 |
| --- | --- | --- |
| SH01 | 0–12 秒 | 人物打开院门，走出门口，结尾门仍打开 |
| SH02 | 12–22 秒 | 硬切到街道侧面，人物走到蓝色自行车旁并握住把手 |
| SH03 | 22–30 秒 | 硬切到背后，人物推着车离开；结尾仍在行进 |

## 实际 Job 计划

不强行凑两个 15 秒任务，优先利用真实切镜：

| Job | 时长 | Job 内时间 | 源范围 | 首帧状态 | 结束后传递 |
| --- | --- | --- | --- | --- | --- |
| J01 / I2VA | 12 秒 | 0–12 | 0–12 | 人物尚在门内 | 衣着与面容；院门已打开 |
| J02 / I2VA | 10 秒 | 0–10 | 12–22 | 街道侧面，人物走近自行车 | 同一人物；双手已握住把手 |
| J03 / I2VA | 8 秒 | 0–8 | 22–30 | 背后视角，人物已握车把 | 行进方向；结尾仍在推车 |

每个任务独立使用 Picture 1 与 Shot 1；不能把第二个任务的 H3 开头写成 `[Shot 2] At 00:12.000`。源时间留在表格中。

装配：J01 → 硬切 → J02 → 硬切 → J03。源片若有额外黑场/叠化，必须另计其时间，不能简单相加后丢掉转场。

## J03 的动作核心

```text
Begin from the rear view of the person already holding the same blue bicycle by its handlebars. Preserve the established face, clothing, bicycle geometry, street layout, and daylight. Over the 8-second continuous shot, the person walks away while pushing the bicycle forward along the street. The wheels rotate in contact with the ground. The camera holds its position as the person and bicycle gradually become smaller in the frame. End while they are still moving away; do not add arrival, parking, or a turn into another street.
```

这段核心仍需按 I2VA 格式加图像对齐行与三个字段。未知声音字段留 N/A；不因“推车”自动加轮胎声或脚步声。

## 当源片是一个连续 30 秒镜头

若平台上限 15 秒，拆成多个 Job 不意味着源片有多个 Shot。源事实保留 SH01；目标用 SH01-a/SH01-b 等编排标记，选择自然停顿或可衔接状态，使用前段尾帧作为后段首帧候选。明确生成连接处可能需要后期衔接，不能保证无缝。若没有合理切点，不擅自加速或删除动作，说明需要的节奏调整。
