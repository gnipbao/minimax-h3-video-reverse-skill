# 10 秒动物动作：首帧与 Motion 分工

**原创教学设定，非历史原视频转录，未执行 H3 生成。** 假设参考片已经完整核对，出现以下单镜动作；声音未核实。这个例子演示历史经验中的“接触—撤回—再次发力”和终态追踪。

以下是确认后的生产阶段示例：另假设用户已认可该动作顺序、目标与声音处理；新任务不能据此跳过自己的内容复述与确认。

## 假设输入与状态

```text
输出：I2V / I2V-A
目标：10 秒，单连续镜头
画幅：9:16（仅本例）
状态：PARTIAL，视觉已核对；音频 unavailable
0–2 秒：猫坐在木地板上，抬起右前爪靠近红球
2–4 秒：爪垫轻触球顶，球暂时不动
4–5 秒：前爪收回胸前，与球分离
5–6 秒：同一前爪再次向右前方伸出，推动红球
6–8 秒：红球向画面右侧滚动，猫收爪并转头跟随
8–10 秒：球停在右侧边缘内，猫仍坐在原处注视球
```

## 首帧提示词

```text
A photorealistic vertical 9:16 medium shot of a small gray tabby cat seated on a pale wooden floor. The cat is left of center, with both front paws resting on the floor and its head turned toward a single matte red rubber ball on screen-right. The ball is about one paw-length from the nearer front paw. A plain warm-white wall fills the background. Soft window light enters from screen-left. Natural fur texture, visible floor grain, realistic proportions, and a quiet uncluttered composition. The entire cat and ball are visible.
```

首帧不能写“猫推动红球”或“红球已经滚到墙边”，这些是后续动作。

## 镜头内动态提示词

```text
Use the reference image as the initial visual state. Create one continuous 10-second shot. Preserve the cat's gray tabby markings, body proportions, the single red ball, the pale wooden floor, and the direction of the window light. Hold the camera steady.

From 0 to 2 seconds, the cat lifts its camera-facing front paw and slowly reaches toward the ball. From 2 to 4 seconds, the paw pad rests lightly on top of the ball while the ball remains in place. From 4 to 5 seconds, the cat pulls the same paw back toward its chest, leaving a visible gap between paw and ball.

From 5 to 6 seconds, the paw moves forward again and pushes the ball toward screen-right. Keep this second contact distinct from the earlier resting touch. From 6 to 8 seconds, the ball rolls rightward across the floor as the cat lowers its paw and turns its head to follow it. From 8 to 10 seconds, the ball comes to rest inside the right edge of the frame. The cat remains seated in its original position, watching the stationary ball. End with both the cat and ball visible.
```

镜头级约束：单个红球；爪子与球的接触清楚；两次接触中间有撤回；猫不突然走到球旁边。避免将“无移动”应用于整个画面，否则球也无法滚动。

## H3 I2VA 可复制块

先生成/选择首帧，实际作为 Picture 1 提交。此例只提供提示词，没有附图，尚不具备生成所需的全部素材。

```text
For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.

integrated_multimodal_description: [Shot 1] A photorealistic vertical 9:16 continuous 10-second shot begins in the composition of <Picture 1>, with the gray tabby cat seated left of the single red ball on the pale wooden floor. Preserve the cat's markings, proportions, the ball's shape, and the soft light from screen-left. The camera holds steady. From 0 to 2 seconds, the cat lifts its camera-facing front paw toward the ball. From 2 to 4 seconds, its paw pad rests lightly on top of the ball without moving it. From 4 to 5 seconds, the paw withdraws toward the chest, leaving a visible gap. From 5 to 6 seconds, the same paw moves forward again and pushes the ball toward screen-right. Keep the two contacts visibly separate. From 6 to 8 seconds, the ball rolls rightward while the cat lowers its paw and turns its head to follow. From 8 to 10 seconds, the ball stops inside the right edge of the frame. The cat stays seated in its original position, watching the ball. End with both visible, without an internal cut or a duplicated ball.

overall_soundscape: N/A

non_diegetic_music: N/A
```

两个 N/A 是本例声音未核实的省略处理，不是原片静音结论。文字示例不构成 H3 输出效果证明。
