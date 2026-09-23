# 8 秒产品展开：首尾帧不等于两张无关图片

**原创教学设定，未生成视频。** 假设已完整检查一个连续镜头：桌面的折叠阅读灯从收拢状态打开，最终停在展开状态；平台已确认支持首尾帧。

以下假设用户已确认展示目的、展开过程与终态；新任务先按确认协议复述，再进入这个生产阶段。

## 首帧与尾帧

首帧 Picture 1：

```text
A clean 16:9 studio product shot of a compact cream-colored folding reading lamp on a matte blue tabletop. Its circular base lies flat. The narrow lower arm and rectangular lamp head are folded close together above the base. The product is centered, fully visible, and unlit. A soft large light source from upper-left creates a broad highlight and a gentle shadow toward lower-right. Plain blue background, precise product geometry, no logo or text.
```

尾帧 Picture 2：

```text
The same cream-colored reading lamp on the same matte blue tabletop, in the same centered 16:9 studio composition. The circular base remains flat in its original position. The lower arm is raised, and the rectangular lamp head extends horizontally above the base. The lamp is fully unfolded and remains unlit. Preserve the original hinge count, proportions, surface finish, lighting direction, and shadow softness. No logo or text.
```

尾帧保持底座位置，但允许关节角度变化。不能同时要求“产品绝不改变形状”又要求灯臂展开。

## H3 FL2VA 可复制块

此处 8.00 秒是生成任务的目标端点；源片最后一帧的 PTS 另存于取证记录。

```text
How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot 1) aligns with the 8.00-second mark of the target video.

integrated_multimodal_description: [Shot 1] A continuous 8-second studio product shot starts from Picture 1. The cream-colored reading lamp rests on the matte blue tabletop with its arm and rectangular head folded above the circular base. The camera remains fixed. During the first 2 seconds, hold the closed configuration. From 2 to 5 seconds, the lower arm rotates upward around its visible base hinge while the base stays flat and stationary. From 5 to 7 seconds, the lamp head rotates around the upper hinge until it extends horizontally, approaching the configuration in Picture 2. The existing parts remain rigid; only the two hinge angles change. From 7 to 8 seconds, the movement settles into the final composition of Picture 2. Keep the lamp unlit, preserve its proportions and cream finish, and maintain the same soft light and blue background throughout.

overall_soundscape: N/A

non_diegetic_music: N/A
```

本例没有证实声音，因此不添加电机声、咔哒声或背景配乐。若实际平台只支持首帧，降级为 I2V-A，以文字约束终态，说明尾帧未参与模型输入；不要伪造双图接口。
