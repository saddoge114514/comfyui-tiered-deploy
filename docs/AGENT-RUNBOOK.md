# AGENT-RUNBOOK · 交给 AI 执行的部署流程

本文件是**给 AI 执行者看的**，不是给人看的。它把手册里散落在五档中的步骤整理成一条可执行序列，供 AI 在一次会话内推进到底。

---

## 一、把这段发给 AI

复制下面整块，连同本文件全文一起发送：

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

---

## 二、阶段 0 · 体检与定档

先取机器事实，不要凭用户口述。

```powershell
# GPU 与显存
Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion,
  @{n='VRAM_GB';e={[math]::Round($_.AdapterRAM/1GB,1)}}
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv   # 有 NVIDIA 卡时

# CPU / 内存 / 系统
Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors
[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB,1)
[System.Environment]::OSVersion.Version
(Get-CimInstance Win32_OperatingSystem).Caption

# 磁盘（选一个剩余空间 ≥ 目标模型体积的卷，优先 NVMe）
Get-PhysicalDisk | Select-Object FriendlyName, MediaType, Size
Get-PSDrive -PSProvider FileSystem | Select-Object Name,
  @{n='FreeGB';e={[math]::Round($_.Free/1GB,1)}}

# 页面文件（低于 16G 时给建议，不擅自修改）
Get-CimInstance Win32_PageFileUsage | Select-Object Name, AllocatedBaseSize, CurrentUsage
```

**定档规则（只看显存）**

| 显存 | 档位 |
|---|---|
| 无独显 / 核显 | T1 |
| 6–8 GB | T2 |
| 10–12 GB | T3 |
| 14–16 GB | T4 |
| ≥ 20 GB | T5 |

**输出**：一张事实表（GPU / 显存 / 内存 / 系统 / 目标盘剩余空间 / 页面文件），以及判定出的档位。档位确定后再进阶段 1，不要中途改档。

> 集成显卡无法用 `nvidia-smi`，`AdapterRAM` 在部分驱动上读数不准（可能为 4GB 或负数）。核显一律按 T1 处理，不要试图用 `AdapterRAM` 反推。

---

## 三、阶段 1 · 目录与环境变量

以 `D:\AI` 为例；换盘时把 `$root` 改掉即可，后续命令全部引用变量，不要重复写死路径。

```powershell
$root = 'D:\AI'
$dirs = 'ComfyUI','models\checkpoints','models\loras','models\vae','models\controlnet',
        'models\upscale_models','models\text_encoders','models\diffusion_models',
        'models\clip_vision','models\embeddings','cache\hf','cache\torch','cache\pip',
        'output','input','temp','dl','scripts'
foreach ($d in $dirs) { New-Item -ItemType Directory -Force "$root\$d" | Out-Null }

# 用户级环境变量（不需要管理员）
$envs = @{
  HF_HOME              = "$root\cache\hf"
  HF_HUB_CACHE         = "$root\cache\hf\hub"
  TORCH_HOME           = "$root\cache\torch"
  PIP_CACHE_DIR        = "$root\cache\pip"
  COMFYUI_MODELS       = "$root\models"
  COMFY_ROOT           = $root
  COMFY_OUT            = "$root\output"
}
foreach ($k in $envs.Keys) { [Environment]::SetEnvironmentVariable($k, $envs[$k], 'User') }
$envs.GetEnumerator() | ForEach-Object { "$($_.Key) = $($_.Value)" }
```

**验证**：目录存在、环境变量写入用户作用域（新开的进程里能读到）。

**失败分支**
- 目标盘剩余空间小于所需体积 → 停下来，把「目标盘剩余」与「所需体积」一起报给用户，不要自行换盘。
- 写入用户环境变量被拒绝 → 改为 `'Process'` 作用域仅用于本次会话，并告知用户环境变量未持久化。

---

## 四、阶段 2 · 安装 ComfyUI

```powershell
$root = 'D:\AI'
$dl   = "$root\dl"

# 7z 解压工具（官方 7-Zip 的独立版，只有几百 KB）
curl.exe -L -o "$dl\7zr.exe" https://www.7-zip.org/a/7zr.exe

# ComfyUI 便携版（NVIDIA 版；AMD/CPU 版把 nvidia 换掉）
curl.exe -L -o "$dl\ComfyUI_windows_portable_nvidia.7z" `
  https://github.com/comfyanonymous/ComfyUI/releases/latest/download/ComfyUI_windows_portable_nvidia.7z

& "$dl\7zr.exe" x "$dl\ComfyUI_windows_portable_nvidia.7z" "-o$root" -y
# 解压结果是 $root\ComfyUI_windows_portable\，把内容上移一层铺平到 $root\ComfyUI
```

启动并验证：

```powershell
$py = "$root\ComfyUI\python_embeded\python.exe"
& $py -s "$root\ComfyUI\ComfyUI\main.py" --windows-standalone-build --port 8188 `
  --listen 127.0.0.1 --disable-auto-launch `
  --output-directory "$root\output" --input-directory "$root\input" `
  --temp-directory "$root\temp\comfy"
# 另开一个终端验证：
curl.exe -s http://127.0.0.1:8188/system_stats
```

**验证**：`/system_stats` 返回 JSON，含 `comfyui_version`、`devices[0].vram_total`、`vram_free`。日志里应出现 `Total VRAM` 与 extra search path 行。

**显存策略参数（按档位选择，写进启动命令）**

| 档位 | 参数 |
|---|---|
| T1 | `--cpu` |
| T2 | `--medvram --reserve-vram 0.6` |
| T3 | `--reserve-vram 0.4` |
| T4 / T5 | `--highvram`（**注意：跑视频时必须去掉**） |

**失败分支**
- 下载 404 → `releases/latest/download/<asset>` 直链可能改名，改用 release 页面解析实际文件名。
- `7zr.exe` 报 `Cannot open the file as archive` → 下载物其实是 zip，改用 `tar -xf`。
- 启动后 `/system_stats` 连不上 → 先看日志是否 OOM 或端口占用；不要盲目改端口。

---

## 五、阶段 3 · 模型下载与校验

**这一步是全流程最容易假通过的地方。** 文件大小正确、safetensors 头能解析，内容仍可能是全零。

1. 生成下载清单（`$root\dl\models.txt`），格式为 URL + 缩进的 `out=` / `dir=`：

```
https://huggingface.co/<repo>/resolve/main/<file>.safetensors
  out=<file>.safetensors
  dir=D:/AI/models/checkpoints
```

2. 下载：

```powershell
& "$root\temp\aria2c.exe" -i "$root\dl\models.txt" -x16 -s16 -k1M `
  --file-allocation=none -c --auto-file-renaming=false `
  --max-tries=15 --retry-wait=5 --summary-interval=60
```

3. **校验（必做）**：用 `scripts/audit_models.py`，或按下面这段独立校验：

```python
# 对比官方 sha256 与本地文件；官方值：ModelScope 取 API 的 Sha256 字段，
# hf-mirror 取 `curl -sIL <resolve URL>` 响应头里的 X-Linked-Etag（不是 ETag）
import hashlib, sys
p, expect = sys.argv[1], sys.argv[2].upper()
h = hashlib.sha256()
with open(p, 'rb') as f:
    for chunk in iter(lambda: f.read(8 << 20), b''):
        h.update(chunk)
print('MATCH' if h.hexdigest().upper() == expect else f'MISMATCH {h.hexdigest().upper()}')
```

**验证**：清单内每个文件都输出 `MATCH`。任一 `MISMATCH` 或 `.aria2` 控制文件仍存在 → 删除该文件后重下，最多 3 次。

**失败分支**
- `huggingface_hub` + `hf_transfer` 长时间 0 字节、日志刷 `s3::get_range retry` → 放弃该路径，改用 aria2 直连或多镜像。
- 走代理时额度可能被打光 → 优先试国内镜像与 ModelScope；镜像域名解析到 `198.18.x.x` 说明进了 Clash fake-IP 段，实际走不走代理由规则决定。
- 只校验浮点张量方差的脚本查不出文本编码器损坏（`spiece_model` 是字节张量），必须整文件哈希。

---

## 六、阶段 4 · 冒烟出图

提示词由使用者提供；无提示词时用 `test` 之类非人物词验证链路即可，不要自行编写内容。

```powershell
$py = "$root\ComfyUI\python_embeded\python.exe"
& $py "$root\scripts\gen.py" --ckpt <你的底模文件名> --pos test --neg "" `
  --w 832 --h 1216 --steps 26 --cfg 6.0 --seed 1 --prefix smoke
```

**验证**：产物落在 `$root\output`，尺寸正确，**不是纯色或纯灰**（纯灰说明权重全零，回阶段 3）。

**必须注意**：ComfyUI 对完全相同的请求复用执行结果，同参数同种子再提交会秒回，测量耗时会失真。**测速一律换种子。**

**失败分支**
- 报 `sentencepiece` 解析错误 → 文本编码器损坏，见阶段 3 的哈希校验。
- 报显存不足 → 按档位调整 `--reserve-vram` 或降分辨率，不要直接改 `--highvram`。

---

## 七、阶段 5 · 可选链路（按档位决定是否执行）

| 链路 | 最低档位 | 依赖 |
|---|---|---|
| 二段放大（`--hires 1.5`） | T2 | 无 |
| ControlNet 姿势约束（`--pose`） | T3 | openpose 模型 + `pose.py` |
| 人脸二次精修（`--facefix`） | T3 | `ultralytics`、`opencv-python`、YOLO 权重；自定义节点 `dsh_facefix.py` |
| 2K 放大（`--upscale` + `--final-scale`） | T3 | 放大模型 |
| 视频（`vid.py`） | T4 | Wan2.2 双专家 + 4 步 LoRA + `wan_2.1_vae` |

每接一条链路，都要求「换种子重跑一次 → 记录耗时 → 检查产物尺寸」，确认无误后再接下一条。

**视频特别注意**：启动 ComfyUI 时去掉 `--highvram`，否则两个 13B 级专家常驻会 OOM；14B 用 `wan_2.1_vae`（16 通道），`wan2.2_vae` 是 48 通道给 5B 用的。

---

## 八、交付报告模板

部署结束后按此输出，缺项要写明原因：

```
【机器】GPU / 显存 / 内存 / 系统 / 目标盘剩余
【档位】T?
【启动命令】完整一行，含显存参数
【模型清单】文件名 + 大小 + sha256 校验结果（逐条）
【冒烟结果】分辨率 / 步数 / 耗时 / 产物路径
【已启用链路】二段放大 / ControlNet / 修脸 / 2K / 视频
【实测数字】各项耗时，标注是实测还是推算
【遗留问题】未完成的步骤、需要管理员或人工处理的项
【占位符取值】$root、底模文件名、模型目录等实际值
```

---

## 九、给执行者的边界

- 只在用户指定范围内操作磁盘，不动系统目录、不改系统级配置。
- 不安装未经用户同意的驱动、不更新 BIOS、不修改页面文件——这些只给命令，不代为执行。
- 不生成任何提示词，不对生成内容作评价或引导。
- 每一步的实测数字如实记录；没测过的写「未测」，不要用推算值冒充实测。
