# 脚本用法

所有脚本只依赖 **ComfyUI 便携版自带的 Python**（3.13），不需要额外装包 —— 除了 `dsh_facefix.py`（它跑在 ComfyUI 进程里，需要 `ultralytics` 和 `opencv-python`）。

统一约定：路径来自环境变量，不写死。

| 变量 | 默认值 |
|---|---|
| `COMFY_ROOT` | `D:/AI` |
| `COMFYUI_MODELS` | `$COMFY_ROOT/models` |
| `COMFY_OUT` | `$COMFY_ROOT/output` |
| `COMFY_URL` | `http://127.0.0.1:8188` |
| `ARIA2C` | `$COMFY_ROOT/temp/aria2c.exe` |

> 脚本本身**不含任何提示词**。所有 `--pos` / `--neg` 都是使用者自己提供的文本或文件。

---

## gen.py — 出图驱动

拼 ComfyUI 节点图 → `POST /prompt` → 轮询 `/history/<id>` → 打印耗时与落盘路径。
无第三方依赖（`urllib` + `json`）。

```powershell
python gen.py --pos @C:\my\prompt.txt --neg @C:\my\negative.txt `
  --w 832 --h 1216 --steps 26 --cfg 6.0 --seed 1234 --prefix test
```

### 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--ckpt` | `waiIllustriousSDXL_v170.safetensors` | 底模文件名 |
| `--pos` / `--neg` | — | 正/负提示词；`@` 开头表示读文件 |
| `--w` `--h` | 1024 / 1024 | 分辨率 |
| `--steps` `--cfg` `--seed` `--batch` | 28 / 5.0 / 随机 / 1 | 采样参数 |
| `--sampler` `--sched` | `dpmpp_2m` / `karras` | 采样器 |
| `--hires` | 1.0 | 二段放大倍数，1.0 = 不开 |
| `--hires-steps` `--hires-denoise` `--hires-method` | 0（沿用）/ 0.45 / bislerp | 二段参数 |
| `--upscale` | 空 | 像素放大模型文件名，如 `4x-UltraSharp.pth` |
| `--final-scale` | 0 | 放大后缩回的倍数，0 = 不缩 |
| `--pose` `--cn` | 空 / openpose | 骨架图文件名 + ControlNet 模型 |
| `--cn-strength` `--cn-start` `--cn-end` | 0.85 / 0.0 / 0.8 | ControlNet 作用区间 |
| `--facefix` | 关 | 开人脸二次重采样 |
| `--face-model` `--face-conf` `--face-pad` | `face_yolov8m.pt` / 0.35 / 1.8 | 检测与扩框 |
| `--face-target` `--face-denoise` `--face-steps` `--face-feather` | 1024 / 0.35 / 20 / 0.18 | 重采样参数 |
| `--prefix` | `test` | 输出文件名前缀 |

### 注意

- 同参数同种子重复提交会被 ComfyUI 的执行缓存命中，**测速必须换种子**。
- `--pose` 的图要放在 ComfyUI 的 `input` 目录里。

---

## pose.py — 18 点骨架生成器

自己画 OpenPose 骨架图，不依赖外部库（只用 PIL）。黑底，官方配色骨棒 + 圆点。

```powershell
python pose.py --pose "@250,430;330,470;..." --w 1216 --h 832 --out D:\AI\input\pose.png
```

点序（COCO，指**人物自己的左右**）：

```
0 鼻  1 颈  2 右肩  3 右肘  4 右腕
5 左肩 6 左肘 7 左腕
8 右髋 9 右膝 10 右踝
11 左髋 12 左膝 13 左踝
14 右眼 15 左眼 16 右耳 17 左耳
```

### 三条硬规矩（实测踩出来的）

1. 骨架方向要和画布一致：横幅姿势横着画，竖幅姿势竖着画
2. 坐标要夸张：想画"手撑墙"，腕点要拉到画面边缘，否则模型读成"托腮"
3. 手腕点不要和膝/髋点重合，错开 50–60px，否则 ControlNet 会把手臂和腿融成一坨

---

## audit_models.py — 模型完整性校验

拉官方 sha256 → 算本地 → 不一致就删了重下（最多 3 次）。

```powershell
python audit_models.py          # 全量
python audit_models.py umt5     # 按关键字过滤
```

### 为什么需要它

已确认踩过：**文件大小完全正确、safetensors 头能解析、逐张量方差正常，内容却是全零**（下载器预分配留下的空洞）。只有哈希能判定。

### 哈希从哪来

- ModelScope：`/api/v1/models/<repo>/repo/files` 里的 `Sha256` 字段
- hf-mirror：`curl -sIL <resolve URL>` 响应头的 `X-Linked-Etag`（普通 `ETag` 是 CDN 的，不能用）

脚本里的 `ITEMS` 列表是**示例清单**，按你实际下载的文件改。

---

## vid.py — 视频驱动（阶段 D）

Wan2.2 双专家（high/low noise）+ 4 步加速 LoRA，两段 KSampler。

```powershell
python vid.py --mode i2v --image start.png `
  --pos @C:\my\video_prompt.txt --neg @C:\my\video_negative.txt `
  --w 832 --h 480 --length 81 --steps 4 --cfg 1.0 --seed 9001 --prefix test
```

### 关键点

- **必须去掉 ComfyUI 的 `--highvram`**，否则两个 13.31G 专家同时常驻会 OOM
- 14B 模型用 `wan_2.1_vae.safetensors`（16 通道）；`wan2.2_vae` 是 48 通道，给 5B 用
- `--length 81` + `--fps 16` ≈ 5 秒
- 在 16G 卡上，5 秒 480p 约 100 秒

---

## dsh_facefix.py — 人脸裁切 / 贴回（ComfyUI 自定义节点）

放到 `ComfyUI/custom_nodes/` 下，重启 ComfyUI 生效。**不依赖 Impact Pack**。

- `DshFaceCrop`：YOLO 取面积最大的脸 → pad 扩框 → 裁切 → 缩到 target 见方
- `DshFacePaste`：缩回原尺寸 → 羽化 mask → 贴回

依赖：

```powershell
.\python_embeded\python.exe -m pip install ultralytics opencv-python -i https://pypi.tuna.tsinghua.edu.cn/simple
```

权重放到 `$COMFYUI_MODELS/ultralytics/bbox/face_yolov8m.pt` 等位置（见手册第 4.2 节）。

> ⚠️ Ultralytics 的代码与权重采用 **AGPL-3.0**，闭源商用前请自行评估。
