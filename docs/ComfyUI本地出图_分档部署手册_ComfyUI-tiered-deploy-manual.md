# ComfyUI 本地出图环境 · 分档部署手册（T1–T5）

> **本手册不包含任何提示词。**
>
> 内容限于环境搭建、模型下载、参数配置与脚本执行，不包含人物提示词、角色描述、场景描述与成品图像。文中出现的 `@D:\AI\scripts\prompt.txt` 等写法均为占位符，指向使用者自行准备的文件。提示词撰写方法不在本手册范围内。

> **编写说明**：本手册与配套脚本在编写过程中使用了 AI 辅助。部署、调试与故障排查均在实机完成，数据来自实际运行结果；文档整理与脚本初稿由 AI 辅助生成，并经人工核对。

> **免责声明（使用前请阅读，如不同意任一条款请勿使用）**
>
> 1. **性质**：本手册为个人经验记录，非 ComfyUI、SDXL、Illustrious、Wan、Ultralytics 或任何模型作者的官方文档，与上述各方不存在隶属、合作或授权关系。
> 2. **内容范围**：不包含提示词、生成图片、角色设定、素材文件与模型权重。文中提示词位置均为占位符。
> 3. **生成内容与作者无关**：使用者依本手册所生成的图像、视频及其他产物，其内容、质量、风格、合法性、可用性与商业价值均与作者无关。作者不参与、不审阅、不背书，不承担任何责任。
> 4. **输出不确定性**：模型输出具有随机性，相同提示词在不同种子下结果不同。本手册不对生成结果的可达性、相似度或合规性作出任何承诺。
> 5. **版权责任**：若生成内容与既有作品、角色或真人形象构成近似，由此产生的版权、肖像权、商标权及平台规则问题由使用者自行承担，本手册不提供判断依据，亦不构成任何豁免。
> 6. **修改与再分发与作者无关**：任何人对本手册进行 fork、删改、增补、翻译或二次发布后产生的结果，包括内容误导、模型损坏、硬件故障、数据丢失、合规问题与商业纠纷，均与原作者无关。原作者不对衍生版本背书，亦不承担任何责任。
> 7. **转载要求**：依据 CC BY 4.0 转载或改编时，须保留署名并完整保留本节免责声明。删除或弱化本节后再行发布，构成对原意的实质性改变，作者不予认可。
> 8. **无维护义务**：作者无义务更新本文档、跟进上游变更、答复问题或修正错误。文中版本号、下载地址与参数可能随时间失效。
> 9. **数据说明**：耗时与显存数据中仅 T4 档为特定机器实测，其余为推算或无数据（标记见第 0 节）。驱动程序、系统版本、后台负载与散热状况均会显著影响结果，实际数值以自测为准。
> 10. **模型许可**：各模型适用各自的许可证，例如 Ultralytics 权重为 AGPL-3.0，FLUX.1 [dev] 为非商用许可，SDXL 系列多为 CreativeML OpenRAIL++-M。具体条款以各仓库 LICENSE 为准，本手册不代为判断，亦不提供法律意见。
> 11. **系统级操作风险**：BIOS 更新、页面文件配置、驱动安装与电源功率调整存在风险，可能导致设备无法启动或数据损坏。操作前请备份并自行评估，由此产生的损失由操作者承担。
> 12. **合规责任**：本手册仅提供技术流程，不构成对任何具体用途的许可、鼓励或背书。使用者应自行确保其使用方式符合所在地区法律法规、所用平台条款与相关规范。
> 13. **无担保**：本手册按「现状」提供，不附带任何明示或暗示的担保。因参照本手册操作而产生的直接或间接损失，包括数据丢失、硬件异常、时间损耗、业务中断及第三方索赔，作者不承担责任。

---

用途：将一台 Windows 机器配置为可脚本化、可复现的本地出图环境，覆盖**环境搭建、参数控制、ControlNet 姿势约束、人脸二次精修、2K 放大**，即阶段 C。

---

## 0. 数据可信度说明（先看这个）

本手册里的数字分三类，正文逐条标注：

| 标记 | 含义 | 说明 |
|---|---|---|
| **[实测]** | 在 i7-14700KF + RTX 4080 SUPER 16G + Win11 24H2 上量出的真数 | 有多次重复，含同进程波动范围 |
| **[推算]** | 按公开算力/显存带宽比例推出的量级 | 误差可能达 ±40%，只能当"预计"，不能当承诺 |
| **[无数据]** | 没有可靠依据 | 只给区间和"先跑一张验证"的建议，不给精确值 |

**只有 T4 档是 [实测]。** T1/T2/T3/T5 的耗时全部是 [推算] 或 [无数据]，请按此预期使用。

---

## 1. 判定档位（只看显存）

先跑体检：

```powershell
$ErrorActionPreference='SilentlyContinue'
"=== OS ==="   ; Get-CimInstance Win32_OperatingSystem | % { "{0} Build {1}" -f $_.Caption,$_.BuildNumber }
"=== CPU ==="  ; Get-CimInstance Win32_Processor | % { "{0} {1}C/{2}T" -f $_.Name,$_.NumberOfCores,$_.NumberOfLogicalProcessors }
"=== RAM ==="  ; "{0:N1} GB" -f ((Get-CimInstance Win32_PhysicalMemory | Measure-Object Capacity -Sum).Sum/1GB)
"=== GPU ==="  ; nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>$null
if(-not $?){ "nvidia-smi 不可用（核显 / AMD / 未装驱动）" }
"=== 磁盘 ===" ; Get-PSDrive -PSProvider FileSystem | ? Free | % { "{0}: 剩 {1:N0} G" -f $_.Name,($_.Free/1GB) }
```

| 显存结果 | 档位 |
|---|---|
| 无 NVIDIA GPU（核显） | **T1** |
| 6–8G | **T2** |
| 10–12G | **T3** |
| 14–16G | **T4** |
| ≥20G | **T5** |

例外：AMD 独显（ROCm/DirectML）、Intel Arc 独显目前都不走 CUDA，本手册未覆盖；按 T1 的 CPU 路径处理会非常慢。

---

## 2. 共用准备（五档都要做，做完跳到你的档）

### 2.1 目录

```powershell
$Root='D:\AI'
'','ComfyUI','models','models\checkpoints','models\vae','models\controlnet','models\upscale_models',
'models\text_encoders','models\diffusion_models','models\loras','models\ultralytics\bbox',
'models\ultralytics\segm','cache','cache\hf','cache\torch','cache\pip','cache\temp',
'input','output','temp','dl','scripts' | % { New-Item -ItemType Directory -Force -Path (Join-Path $Root $_) | Out-Null }
```

工作盘可换，把后面所有 `D:\AI` 全局替换即可。**不建议放系统盘**：核心模型约 13–42G，加视频组约 115G。

### 2.2 环境变量（用户级）

```powershell
setx HF_HOME "D:\AI\cache\hf"
setx HF_HUB_CACHE "D:\AI\cache\hf\hub"
setx HUGGINGFACE_HUB_CACHE "D:\AI\cache\hf\hub"
setx TORCH_HOME "D:\AI\cache\torch"
setx PIP_CACHE_DIR "D:\AI\cache\pip"
setx COMFYUI_MODELS "D:\AI\models"
```

设完需**新开 shell**。

### 2.3 下载工具

`aria2c.exe` 与 `7zr.exe` 放到 `D:\AI\temp\`（7zr 只能解 .7z，zip 用 `tar -xf`）。

### 2.4 装 ComfyUI 便携版

```powershell
# 下载约 1.9G
# https://github.com/comfyanonymous/ComfyUI/releases/latest/download/ComfyUI_windows_portable_nvidia.7z

D:\AI\temp\7zr.exe x <下载到的>.7z -oD:\AI\temp\cf
# 解压后是 ComfyUI_windows_portable\ 子目录，把其内容上移一层铺平到 D:\AI\ComfyUI
```

自查（用内嵌 Python）：

```powershell
D:\AI\ComfyUI\python_embeded\python.exe -c "import torch;print(torch.__version__, torch.cuda.is_available())"
```

- T2–T5 期望 `cuda.is_available()` 为 `True`
- **T1 期望为 `False`**（核显无 CUDA），属正常，后续走 `--cpu`

### 2.5 让 ComfyUI 认 D 盘模型目录

写 `D:\AI\ComfyUI\ComfyUI\extra_model_paths.yaml`：

```yaml
dsh:
  base_path: D:/AI/models
  is_default: true
  checkpoints: checkpoints
  vae: vae
  controlnet: controlnet
  upscale_models: upscale_models
  loras: loras
  clip: text_encoders
  text_encoders: text_encoders
  diffusion_models: diffusion_models
  embeddings: embeddings
  unet: diffusion_models
```

### 2.6 下载与校验的统一做法

两个源都直连、不走代理：

- ModelScope：`https://modelscope.cn/models/<repo>/resolve/master/<path>`
- hf-mirror：`https://hf-mirror.com/<repo>/resolve/main/<path>`

```powershell
# 清单文件 models.txt：一行 URL，紧跟缩进指令
#   <url>
#     out=文件名
#     dir=D:\AI\models\controlnet

D:\AI\temp\aria2c.exe -i D:\AI\dl\models.txt -j3 -x4 -s4 -k1M `
  --file-allocation=none -c --auto-file-renaming=false --max-tries=20 --retry-wait=5
```

**必须校验 sha256。** 已确认踩过的故障：文件大小完全正确、safetensors 头可解析、逐张量方差正常，内容却是全零（下载器预分配留下的空洞）。只有哈希能判定。

取官方哈希：

- ModelScope：`https://modelscope.cn/api/v1/models/<repo>/repo/files?Revision=master&Recursive=true`，每条含 `Sha256`
- hf-mirror：`curl -sIL <resolve URL>`，响应头 **`X-Linked-Etag`** 即 sha256（普通 `ETag` 是 CDN 的，不能用）

`scripts/audit_models.py` 实现「取官方哈希 → 算本地 → 不一致删除重下（最多 3 次）」。

---

## 3. T1 档 · 核显 / 无独显

**参考机型**：Intel Core Ultra 5 125H（Arc 核显）、Iris Xe、Radeon 780M 等。
**结论先行**：这一档不适合跑 SDXL，用 SD1.5、512×768 级。

### 硬件预期

| 项 | 要求 |
|---|---|
| 显存 | 无（共享内存） |
| 内存 | **16G 起，32G 明显更稳**（核显会占一部分做显存池） |
| 磁盘 | 25–35G（SD1.5 底模 2–4G，无需 ControlNet 全套） |

### 部署流程

1. 完成第 2 节共用准备（2.4 自查时 `cuda.is_available()` 为 `False`，正常）。
2. 下载 SD1.5 动漫底模（约 2–4G）到 `models\checkpoints\`，例如 `Lykon/DreamShaper`、`andite/anything-v4.5` 一类，任选其一。
3. 不需要 SDXL VAE（SD1.5 用自带）。可选 `vae\vae-ft-mse-840000-ema-pruned.safetensors`（约 0.33G）。
4. 启动（**必须 `--cpu`**）：

```powershell
cd D:\AI\ComfyUI
.\python_embeded\python.exe -s ComfyUI\main.py --windows-standalone-build `
  --cpu --port 8188 --listen 127.0.0.1 --disable-auto-launch `
  --output-directory D:\AI\output --input-directory D:\AI\input `
  --temp-directory D:\AI\temp\comfy
```

5. 验证：`curl http://127.0.0.1:8188/system_stats` 能看到 `comfyui_version` 即为活。
6. 冒烟出图（先只跑一张，看耗时是否可接受）：

```powershell
$env:COMFY_OUT="D:\AI\output"
D:\AI\ComfyUI\python_embeded\python.exe D:\AI\scripts\gen.py `
  --ckpt <你的SD1.5底模> --pos @D:\AI\scripts\prompt.txt `
  --w 512 --h 768 --steps 24 --cfg 7.0 --seed 1001 --prefix t1_smoke
```

### 参数基线

| 项 | 值 |
|---|---|
| 底模 | SD1.5 |
| 分辨率 | 512×768（竖）/ 768×512（横） |
| 步数 / CFG | 24 / 7.0 |
| 采样器 | `dpmpp_2m` + `karras` |
| 二段放大 / ControlNet / 修脸 / 2K | 全部不开 |

### 耗时

**512×768 SD1.5：[无数据]。** 只能给量级：核显 FP16 算力约为 4080S 的 1/20–1/40，SD1.5 512² 计算量约为 SDXL 1024² 的 1/6，粗估 **40 秒–3 分钟/张**，区间很宽，实际以第 6 步冒烟结果为准。
强行跑 SDXL 1024：[无数据]，预计数分钟/张，且大概率撞内存上限。

### 该档专属坑

- **不要把 SDXL 底模拖进来试**：6.5G 权重 + 注意力激活会超出共享内存池，表现为极慢或直接崩，不是调参能解决的。
- **16G 内存是下限**：Windows + 浏览器能吃掉 8G，留给推理的不多，建议关掉大内存程序再跑。
- **页面文件不要是 4G**：内存换页撞上限会崩，建议调到 32G 以上（需管理员）。
- 核显驱动版本对稳定性影响明显，出图崩溃优先怀疑驱动。

---

## 4. T2 档 · 6–8G 独显

**参考机型**：RTX 3060 8G、RTX 4060 8G、笔记本 RTX 4070。
**结论**：SDXL 能跑，但要靠 `--medvram`，且不建议开修脸。

### 硬件预期

| 项 | 要求 |
|---|---|
| 显存 | 6–8G |
| 内存 | 16G 起（offload 会用到） |
| 磁盘 | 约 40G（底模 6.46G + VAE 0.31G + OpenPose 2.33G + 放大 0.06G） |

### 部署流程

1. 完成第 2 节共用准备。
2. 下载核心组：

| 放到 | 文件 | repo | 大小 |
|---|---|---|---|
| checkpoints | `waiIllustriousSDXL_v170.safetensors` | `LyliaEngine/waiIllustriousSDXL_v170` | 6.46G |
| vae | `sdxl-vae-fp16-fix.safetensors` | `madebyollin/sdxl-vae-fp16-fix` | 0.31G |
| upscale_models | `4x-UltraSharp.pth` | 通用 4x 放大 | 0.06G |

3. 可选（想控姿势就装，会变慢）：`xinsir/controlnet-openpose-sdxl-1.0` 的 `diffusion_pytorch_model.safetensors` → 改名 `controlnet-openpose-sdxl-1.0.safetensors`，2.33G。
4. `sha256` 校验：`audit_models.py`。
5. 启动（**`--medvram` 是本档关键**）：

```powershell
cd D:\AI\ComfyUI
.\python_embeded\python.exe -s ComfyUI\main.py --windows-standalone-build `
  --medvram --reserve-vram 0.6 --port 8188 --listen 127.0.0.1 --disable-auto-launch `
  --output-directory D:\AI\output --input-directory D:\AI\input `
  --temp-directory D:\AI\temp\comfy
```

6. 验证 + 冒烟（832×1216、26 步、不开任何附加链路）。
7. 确认单张耗时能接受，再决定是否加 OpenPose。

### 参数基线

| 项 | 值 |
|---|---|
| 底模 | waiIllustriousSDXL_v170 |
| 分辨率 | 832×1216 / 1216×832 |
| 步数 / CFG | 28 / 6.0 |
| 采样器 | `dpmpp_2m` + `karras` |
| 二段放大 | 1.3× / 12 步（可选，慢 40–60%） |
| ControlNet | 可选，强度 0.7 / end 0.8 |
| 修脸 | **不建议**（等于再跑一遍 1024²，显存需求翻倍） |
| 2K 放大 | 不建议，最多 2x |

### 耗时

**[推算]**：4080S 同链路约 9s；按算力与显存带宽比例（3060 8G ≈ 0.25–0.35×，4060 ≈ 0.3–0.4×）推得 **25–40 秒/张**；开二段放大 **40–60 秒/张**。误差较大，以冒烟实测为准。

### 该档专属坑

- **`--highvram` 会直接 OOM**：它让权重全常驻，8G 装不下 SDXL + 激活。
- **不要同时开 ControlNet + 二段放大 + 修脸**：三者都在吃显存。优先级：先保二段放大，其次 ControlNet。
- **6G 卡**（如 3060 笔记本 6G）可能连 `--medvram` 都不够，要退到 `--lowvram`，速度再降约一半。先试 `--lowvram` 确认能出图，再往上调。
- batch 保持 1，batch>1 在 8G 上几乎必然 OOM。

---

## 5. T3 档 · 10–12G 独显

**参考机型**：RTX 3080 12G、RTX 4070 12G、RTX 4070 SUPER 12G。
**结论**：SDXL 全功能可用，是"完整链路"的下限。

### 硬件预期

| 项 | 要求 |
|---|---|
| 显存 | 10–12G |
| 内存 | 32G 建议 |
| 磁盘 | 约 45G（核心 + 5 个 ControlNet 约 11.7G + 检测模型 0.12G + 两个放大模型） |

### 部署流程

1. 完成第 2 节共用准备。
2. 下载核心组（同 T2 三件）。
3. 下载进阶组：

| 放到 | 文件 | repo（均取 `diffusion_pytorch_model.safetensors` 后改名） | 大小 |
|---|---|---|---|
| controlnet | `controlnet-openpose-sdxl-1.0.safetensors` | `xinsir/controlnet-openpose-sdxl-1.0` | 2.33G |
| controlnet | `controlnet-depth-sdxl.safetensors` | `xinsir/controlnet-depth-sdxl-1.0` | 2.33G |
| controlnet | `controlnet-canny-sdxl.safetensors` | `xinsir/controlnet-canny-sdxl-1.0` | 2.33G |
| controlnet | `controlnet-scribble-sdxl.safetensors` | `xinsir/controlnet-scribble-sdxl-1.0` | 2.33G |
| controlnet | `controlnet-tile-sdxl.safetensors` | `xinsir/controlnet-tile-sdxl-1.0` | 2.33G |
| ultralytics\bbox | `face_yolov8m.pt` / `hand_yolov8s.pt` | 检测模型 | 0.05 / 0.02G |
| ultralytics\segm | `person_yolov8m-seg.pt` | 人体分割 | 0.05G |
| upscale_models | `RealESRGAN_x4plus_anime_6B.pth` | 动漫向 4x | 0.02G |

   只装 OpenPose 也能工作，其余四种是不同约束方式，按需加。
4. 装人脸节点依赖并把 `dsh_facefix.py` 放进 `custom_nodes\`，重启：

```powershell
D:\AI\ComfyUI\python_embeded\python.exe -m pip install ultralytics opencv-python -i https://pypi.tuna.tsinghua.edu.cn/simple
```

5. 全部 `sha256` 校验。
6. 启动（**不加 `--highvram`**，12G 属临界，常驻反而挤）：

```powershell
.\python_embeded\python.exe -s ComfyUI\main.py --windows-standalone-build `
  --reserve-vram 0.4 --port 8188 --listen 127.0.0.1 --disable-auto-launch `
  --output-directory D:\AI\output --input-directory D:\AI\input `
  --temp-directory D:\AI\temp\comfy
```

7. 验证节点：`curl http://127.0.0.1:8188/object_info | findstr /C:"ControlNetApplyAdvanced" /C:"DshFaceCrop"`
8. 冒烟：先 832×1216 / 26 步 / 无附加链路，再逐项打开（二段放大 → ControlNet → 修脸 → 2K），每开一项记一次耗时。

### 参数基线

| 项 | 值 |
|---|---|
| 底模 | waiIllustriousSDXL_v170 |
| 分辨率 | 832×1216 / 1216×832 |
| 步数 / CFG | 26 / 6.0 |
| 二段放大 | 1.5× / 16 步 |
| ControlNet | 0.85 / end 0.9 |
| 修脸 | 开（target 1024 / denoise 0.35 / 20 步） |
| 2K 放大 | 4x + 缩 0.5 |

### 耗时

**[推算]**：按算力比例（4070 ≈ 0.5–0.6× 4080S）推得：单张 **12–20s**、+二段放大 **25–35s**、+修脸 **30–45s**、全链 2K **50–70s**。带 ±40% 误差。

### 该档专属坑

- **修脸是"再跑一遍 KSampler"**，显存峰值会叠加。12G 上修脸 + 2K 同时跑可能刚好踩线；OOM 时把 `--face-target` 从 1024 降到 768。
- **别用 `--highvram`**：12G 常驻 SDXL 后余量不足以做 2K 放大的分块推理。
- 5 个 ControlNet 不会一次吃完显存（按需加载），但**载入瞬间**有峰值，第一次切换类型时会慢几秒。
- 4x 再缩 0.5 = 2 倍输出；直接 4x 输出（4992×7296）在 12G 上会因分块过多而极慢。

---

## 6. T4 档 · 14–16G 独显（本手册的实测基准机型）

**参考机型**：RTX 4080 / 4080 SUPER / 4070 Ti SUPER 16G / 5070 Ti 16G。
**结论**：全功能可用，含阶段 D 的视频模型。本档所有数字均为 **[实测]**。

### 硬件预期

| 项 | 要求 |
|---|---|
| 显存 | 14–16G |
| 内存 | 32G 建议（视频档需要，权重搬运吃内存带宽） |
| 磁盘 | 核心+进阶约 45G；加视频组约 115G |

### 部署流程

1. 完成第 2 节共用准备。
2. 下载核心组 + 进阶组（清单同 T2/T3）。
3. 全部 `sha256` 校验通过后再启动，避免拿坏模型调参数、白花时间。
4. 启动 —— **出图和视频用两套参数**，这是本档最容易踩的地方：

```powershell
# 出图（快约 20%）
.\python_embeded\python.exe -s ComfyUI\main.py --windows-standalone-build `
  --highvram --port 8188 --listen 127.0.0.1 --disable-auto-launch `
  --output-directory D:\AI\output --input-directory D:\AI\input --temp-directory D:\AI\temp\comfy

# 视频（必须去掉 --highvram，否则 OOM）
.\python_embeded\python.exe -s ComfyUI\main.py --windows-standalone-build `
  --port 8188 --listen 127.0.0.1 --disable-auto-launch `
  --output-directory D:\AI\output --input-directory D:\AI\input --temp-directory D:\AI\temp\comfy
```

5. 冒烟：单张 832×1216 / 26 步，确认在 9 秒级。
6. 逐项打开链路，对照下面实测表核对。

### 参数基线

| 项 | 值 |
|---|---|
| 底模 | waiIllustriousSDXL_v170（NoobAI-XL 备选：脸更细，但构图理解弱） |
| 分辨率 | 832×1216 / 1216×832 |
| 步数 / CFG | **26** / **6.0** |
| 采样器 | **`dpmpp_2m` + `karras`**（四组同种子对比中最优） |
| 二段放大 | 1.5× / 16 步 |
| ControlNet | 0.85 / end 0.9 |
| 修脸 | target 1024 / denoise 0.35 / 20 步 / feather 0.18 |
| 2K 放大 | 4x-UltraSharp + 缩 0.5 |

### 耗时（全部 [实测]）

| 链路 | 耗时 |
|---|---|
| 832×1216 / 26 步，单张（模型已载入） | **9.0s** |
| 同上，同进程连跑 | 11.6 / 17.7 / 19.2 / 20.7s 都出现过，保守按 **19s** 估 |
| + 二段放大 1.5×（→1248×1824） | **17.7s** |
| + 修脸 | **23.2s** |
| + 4x 放大 + 缩 0.5（→2496×3648） | **33.7s** |
| 整批连跑（每张换骨架 + CN + 2K） | **40–49s/张** |
| 5 秒 480p 视频（832×480 / 81 帧 / 16fps / 4 步） | **102s** |

采样期 GPU 状态 [实测]：占用 96–99%、核心 2685 MHz、功耗 254W（上限 320）、温度 62°C、每步约 0.24s。

### 该档专属坑

- **`--highvram` 与视频模型互斥**：视频要两个 13.31G 专家轮流上，`--highvram` 让它们常驻，实测直接 `Allocation on device 0 would exceed allowed memory`（已分配 28.44 GiB / 上限 15.99 GiB）。
- **ComfyUI 有执行缓存去重**：同参数同种子重提会秒回，量出假的 0.6s / 9.72s。测速必须换种子。
- **同进程耗时波动大**：9s 到 20s 都出现过，主要来自显存整理和后台程序。批量估时间按 19s，不要按 9s。
- **fp8 在本档反而更慢**：`--fp8_e4m3fn-unet` 实测 21.7s vs fp16 20.2s（逐层转换开销吃掉收益），已回滚。
- **SageAttention 装不上**：`triton-windows` 编译需要 `Python.h`，便携版 Python 不带开发头文件；要装得先补开发环境。
- **batch 4 只快 11%**（8.09s/张 vs 9.07s/张），显存受限，别指望批量摊薄。

---

## 7. T5 档 · ≥20G 显存

**参考机型**：RTX 3090 24G、4090 24G、5090 32G。
**结论**：同链路更快、可批量，视频模型可常住不需来回换。

### 硬件预期

| 项 | 要求 |
|---|---|
| 显存 | ≥20G |
| 内存 | 64G 建议（批量 + 视频同时开） |
| 磁盘 | 120G+（含视频模型全家） |

### 部署流程

1. 完成第 2 节共用准备。
2. 下载核心组 + 进阶组（同上）。
3. 如需视频，另下视频组：

| 放到 | 文件 | repo | 大小 |
|---|---|---|---|
| diffusion_models | `wan2.2_i2v_{high,low}_noise_14B_fp8_scaled.safetensors` | `Comfy-Org/Wan_2.2_ComfyUI_Repackaged` → `split_files/diffusion_models/` | 13.31G ×2 |
| loras | `wan2.2_i2v_lightx2v_4steps_lora_v1_{high,low}_noise.safetensors` | 同上 → `split_files/loras/` | 1.14G ×2 |
| text_encoders | `umt5_xxl_fp8_e4m3fn_scaled.safetensors` | 同上 → `split_files/text_encoders/` | 6.27G |
| vae | **`wan_2.1_vae.safetensors`** | 同上 → `split_files/vae/` | 0.24G |

   ⚠️ 14B 用 `wan_2.1_vae`（16 通道）；`wan2.2_vae` 是 48 通道，给 5B TI2V 用。拿错报张量尺寸不匹配。
4. 启动（本档可一直挂 `--highvram`）：

```powershell
.\python_embeded\python.exe -s ComfyUI\main.py --windows-standalone-build `
  --highvram --port 8188 --listen 127.0.0.1 --disable-auto-launch `
  --output-directory D:\AI\output --input-directory D:\AI\input --temp-directory D:\AI\temp\comfy
```

5. 冒烟同 T4，再试 batch 2–4。

### 参数基线

与 T4 相同，可放开三点：步数可降到 24、分辨率可上 896×1280 或 1024×1024、batch 可 2–4。

### 耗时

**[推算]**：4090 在 SDXL fp16 上约为 4080S 的 1.5–1.8×，推得单张 **5–7s**、全链 2K **20–30s**。5090 缺公开对照数据，标 **[无数据]**。
批量不是线性加速：16G 上实测 batch4 只有 11% 提升；24G 预计提升更明显，但仍远不到 4 倍。

### 该档专属坑

- **批量和视频不要同时开**：即便 24G，两个 13.31G 专家 + 批量 SDXL 也会互挤。
- 3090 是 GDDR6X 且功耗高，长时间批量跑注意散热；显存温度是这类卡的常见故障点（本手册未实测，仅提示）。
- 显存大不等于可以无脑加大分辨率：SDXL 超过 1024 级后画面容易重复结构，2K 应走放大链而不是直接生成。

---

## 8. 通用踩坑清单（与档位无关）

按实际踩到的顺序：

1. **PowerShell 可能只有 5.1**，没有 pwsh 7：`& pwsh` 报 CommandNotFoundException，`.ps1` 被执行策略拒。对策：脚本纯 ASCII 输出，或 `[System.IO.File]::ReadAllText($p,[Text.Encoding]::UTF8)` 后 `iex`。
2. **写 .py 不要带 BOM**：`Set-Content -Encoding UTF8` 会加 BOM，Python 报 `invalid non-printable character U+FEFF`。正解：`[System.IO.File]::WriteAllText($p,$s,(New-Object System.Text.UTF8Encoding($false)))`。
3. **下载器会预分配文件**："文件大小对了"不代表下完。判完成看同名 `.aria2` 控制文件是否消失；判内容只能靠 sha256。
4. **ComfyUI 有执行缓存**：同参数同种子重提会秒回，测速必须换种子。
5. **HF 的 `/api/models/.../tree` 返回 403**，取 sha256 要用 `curl -sIL` 读 `X-Linked-Etag`。
6. **safetensors 坏得隐蔽**：逐张量 `std()==0` 只能查浮点被清零，查不出 `spiece_model` 这类字节张量被清零（实际导致过 tokenizer 解析崩溃）。
7. **7zr 只能解 .7z**，zip 用 `tar -xf`，混用报 Cannot open the file as archive。
8. **正向提示词里的否定句会招来实体**：「no third hand」实测让画面多出一只手。否定内容只放 negative。
9. **竖幅会压扁卧姿**：同一骨架同参数，832×1216 出"侧卧蜷缩"，改 1216×832 才躺下。躺/卧/俯拍一律横幅，且骨架要同方向。
10. **ControlNet 骨架点重合会粘连**：手腕点写在膝点坐标上，实测手臂和腿融成一坨。手/膝/髋的点错开 50–60px。
11. **骨架语义要夸张**：想把"手撑在墙上"画出来，腕点要拉到画面边缘，否则模型读成"托腮"。
12. **页面文件大于 4G**：内存 offload 撞 4G 上限会崩，建议 32G 以上。

---

## 9. 上线自查（任一档通用）

```powershell
# 1) 服务活着
curl http://127.0.0.1:8188/system_stats

# 2) 基础节点存在
curl http://127.0.0.1:8188/object_info | findstr /C:"CheckpointLoaderSimple" /C:"KSampler" /C:"SaveImage"

# 3) T3 以上再查
curl http://127.0.0.1:8188/object_info | findstr /C:"ControlNetApplyAdvanced" /C:"DshFaceCrop"

# 4) 模型校验
D:\AI\ComfyUI\python_embeded\python.exe D:\AI\scripts\audit_models.py

# 5) 冒烟出图（换种子）
$env:COMFY_OUT="D:\AI\output"
D:\AI\ComfyUI\python_embeded\python.exe D:\AI\scripts\gen.py `
  --pos @D:\AI\scripts\prompt.txt --w 832 --h 1216 --steps 26 --cfg 6 --seed 1001 --prefix smoke
```

---

## 10. 交给 AI 执行

本仓库根目录另附一份**给 AI 执行者看的**文件：[交给AI的部署指令_AGENT-RUNBOOK.md](../交给AI的部署指令_AGENT-RUNBOOK.md)。它把散落在五档中的步骤整理成阶段 0→5 的可执行序列，包含：每步的命令、每步的验证条件、失败分支、需要人工介入的停靠点、以及交付报告模板。

### 用法

把 `交给AI的部署指令_AGENT-RUNBOOK.md` 全文连同下面这段一起发给 AI：

```
在这台 Windows 机器上部署 ComfyUI 本地出图环境。执行依据是随附的
AGENT-RUNBOOK.md，严格按其中的阶段 0→5 顺序执行。

规则：
1. 每个阶段的「验证」必须实际跑通才算完成；失败按「失败分支」处理，
   仍失败则停下来报告，不要跳过、不要假装通过。
2. 需要管理员权限、修改 BIOS、修改页面文件、安装驱动的操作：停在这一步，
   把命令原样交给用户执行，等用户回报结果后继续。
3. 不生成、不补充、不推测任何图像提示词。提示词一律视为占位符，
   由用户提供文件路径；用户没提供时用 `test` 之类的非人物测试词验证链路即可。
4. 每完成一个阶段，先输出一段简报（做了什么 / 实测数字 / 遗留问题），再进入下一阶段。
5. 全部结束后，按「六、交付报告」的模板汇报，并列出所有占位符的实际取值。
```

### 简易版（只想要一句话启动时）

> 按 `交给AI的部署指令_AGENT-RUNBOOK.md` 部署到阶段 3（能出第一张图）。我的体检结果：显卡 ____、显存 __G、内存 __G、目标盘剩 __G，我选 T__ 档。按阶段 0→4 执行，每阶段验证通过再做下一步；需要管理员的操作停下来给我命令。标 [推算]/[无数据] 的地方，实测后要替换成真实数字。提示词我单独给，你只管环境、参数、姿势骨架、修脸、放大。

### 两条注意

- 开场白里**不要塞具体提示词**。AI 会把它们写进脚本、日志或提交记录里，之后很难清理干净。
- 开场白里**必须写死档位或让 AI 先体检再定档**。否则它会默认按自己那台机器的经验走，参数可能超出硬件能力。

---

## 附一：模型许可提示（发布/商用前必看）

下表只是**来源指引**，不构成法律意见。**每个模型的实际许可请打开对应仓库的 LICENSE 文件确认**——模型作者随时可能变更条款。

| 模型/组件 | 常见许可类型 | 注意事项 |
|---|---|---|
| SDXL 系列底模（Illustrious、NoobAI、wai 等） | 多为 **CreativeML OpenRAIL++-M** 及其衍生条款 | 该许可带"使用限制"清单；商用、再分发、微调后分发各有条件，需逐条读 |
| xinsir 系列 SDXL ControlNet | 仓库声明多为 **Apache-2.0** | 以仓库 LICENSE 为准 |
| Wan2.2（阿里） | **Apache-2.0** | 相对宽松，但仍建议核实版本 |
| umt5 文本编码器 | 跟随上游 T5/mT5 条款 | 各分发仓库可能不同 |
| Ultralytics YOLOv8 权重与代码 | **AGPL-3.0** | **这一条最容易被忽略**：AGPL 传染性较强，闭源商用需谨慎评估，或改用其他检测方案 |
| 4x-UltraSharp | 作者自定（多为非商用或需署名） | 来源常为社区分享，务必回溯原始出处 |
| Real-ESRGAN | **BSD-3-Clause** | 相对宽松 |
| ComfyUI 本体 | **GPL-3.0** | 分发修改版需开源 |

**如果只是把这个部署手册开源到 GitHub**：手册文本本身不涉及上述许可（它只是描述流程），但如果你在仓库里**附带模型权重或生成的图片**，就要逐个确认许可。

---

## 附二：本文可用的许可建议

如果要把这份手册放进公开仓库，建议：

- 文档本身用 **CC BY 4.0** 或 **MIT**
- 随附的脚本（如 `audit_models.py`）单独用 **MIT**
- 在 README 里显式写明：**本仓库不含提示词、不含模型权重、不含生成图片**

---

## 附三：本手册的边界


- 范围到**阶段 C**（参数 / 姿势 / 修脸 / 2K）。
- **阶段 D（视频）**：仅在 T4 档实测过一条链路（Wan2.2 I2V 14B fp8 双专家 + 4 步 LoRA，5 秒 480p 用 102s）；T5 未验证，T3 及以下不建议尝试。
- 未覆盖：AMD/Intel 独显加速路径、Mac、多卡、LoRA 训练流程。
