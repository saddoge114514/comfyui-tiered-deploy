#!/usr/bin/env python3
"""模型完整性审计：拉官方 sha256 → 本地校验 → 不一致则用 aria2 重下（4 线程）直到匹配。"""
import hashlib, json, os, subprocess, sys, time, urllib.request

ROOT = os.environ.get("COMFY_ROOT", "D:/AI")
ARIA = os.environ.get("ARIA2C", os.path.join(ROOT, "temp", "aria2c.exe"))
MODELS = os.environ.get("COMFYUI_MODELS", os.path.join(ROOT, "models"))
MS = "https://modelscope.cn"
HF = "https://hf-mirror.com"

# (本地相对 models 的路径, 来源类型, repo, 仓库内路径)
ITEMS = [
    ("checkpoints/waiIllustriousSDXL_v170.safetensors", "hf", "LyliaEngine/waiIllustriousSDXL_v170", "waiIllustriousSDXL_v170.safetensors"),
    ("checkpoints/NoobAI-XL-v1.1.safetensors", "hf", "Laxhar/noobai-XL-1.1", "NoobAI-XL-v1.1.safetensors"),
    ("checkpoints/Illustrious-XL-v0.1.safetensors", "hf", "OnomaAIResearch/Illustrious-xl-early-release-v0", "Illustrious-XL-v0.1.safetensors"),
    ("vae/sdxl-vae-fp16-fix.safetensors", "hf", "madebyollin/sdxl-vae-fp16-fix", "sdxl-vae-fp16-fix.safetensors"),
    ("vae/wan2.2_vae.safetensors", "ms", "Comfy-Org/Wan_2.2_ComfyUI_Repackaged", "split_files/vae/wan2.2_vae.safetensors"),
    ("text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors", "ms", "Comfy-Org/Wan_2.2_ComfyUI_Repackaged", "split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors"),
    ("diffusion_models/wan2.2_ti2v_5B_fp16.safetensors", "ms", "Comfy-Org/Wan_2.2_ComfyUI_Repackaged", "split_files/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors"),
    ("diffusion_models/wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors", "ms", "Comfy-Org/Wan_2.2_ComfyUI_Repackaged", "split_files/diffusion_models/wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors"),
    ("diffusion_models/wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors", "ms", "Comfy-Org/Wan_2.2_ComfyUI_Repackaged", "split_files/diffusion_models/wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors"),
    ("diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors", "ms", "Comfy-Org/Wan_2.2_ComfyUI_Repackaged", "split_files/diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors"),
    ("diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors", "ms", "Comfy-Org/Wan_2.2_ComfyUI_Repackaged", "split_files/diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors"),
    ("loras/wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors", "ms", "Comfy-Org/Wan_2.2_ComfyUI_Repackaged", "split_files/loras/wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors"),
    ("loras/wan2.2_t2v_lightx2v_4steps_lora_v1.1_low_noise.safetensors", "ms", "Comfy-Org/Wan_2.2_ComfyUI_Repackaged", "split_files/loras/wan2.2_t2v_lightx2v_4steps_lora_v1.1_low_noise.safetensors"),
    ("loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors", "ms", "Comfy-Org/Wan_2.2_ComfyUI_Repackaged", "split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors"),
    ("loras/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors", "ms", "Comfy-Org/Wan_2.2_ComfyUI_Repackaged", "split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors"),
    ("controlnet/controlnet-openpose-sdxl-1.0.safetensors", "hf", "xinsir/controlnet-openpose-sdxl-1.0", "diffusion_pytorch_model.safetensors"),
    ("controlnet/controlnet-depth-sdxl.safetensors", "hf", "xinsir/controlnet-depth-sdxl-1.0", "diffusion_pytorch_model.safetensors"),
    ("controlnet/controlnet-canny-sdxl.safetensors", "hf", "xinsir/controlnet-canny-sdxl-1.0", "diffusion_pytorch_model.safetensors"),
    ("controlnet/controlnet-scribble-sdxl.safetensors", "hf", "xinsir/controlnet-scribble-sdxl-1.0", "diffusion_pytorch_model.safetensors"),
    ("controlnet/controlnet-tile-sdxl.safetensors", "hf", "xinsir/controlnet-tile-sdxl-1.0", "diffusion_pytorch_model.safetensors"),
    ("upscale_models/RealESRGAN_x4plus_anime_6B.pth", "hf", "ai-forever/Real-ESRGAN", "RealESRGAN_x4.pth"),
]

ms_cache = {}
def ms_hashes(repo):
    if repo in ms_cache:
        return ms_cache[repo]
    url = f"{MS}/api/v1/models/{repo}/repo/files?Revision=master&Recursive=true"
    with urllib.request.urlopen(url, timeout=90) as r:
        js = json.loads(r.read())
    node = js.get("data") or js.get("Data") or {}
    files = node.get("files") or node.get("Files") or []
    d = {f.get("Path", f.get("path")): f.get("Sha256", f.get("sha256")) for f in files}
    d = {k: v for k, v in d.items() if k and v}
    ms_cache[repo] = d
    return d

def hf_hash(repo, path):
    """用 curl -sIL 拿 x-linked-etag（= LFS blob sha256）。"""
    url = f"{HF}/{repo}/resolve/main/{path}"
    try:
        out = subprocess.run(["curl.exe", "-sIL", "--max-time", "60", url],
                             capture_output=True, text=True).stdout
        for line in out.splitlines():
            if line.lower().startswith("x-linked-etag:"):
                return line.split(":", 1)[1].strip().strip('"')
    except Exception as e:
        print(f"  ! HF head fail {repo}: {e}")
    return None

def sha256_of(p, chunk=8 << 20):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

def download(url, dest):
    if os.path.exists(dest + ".aria2"):
        os.remove(dest + ".aria2")
    cmd = [ARIA, "-x4", "-s4", "-k1M", "--file-allocation=none", "-c",
           "--auto-file-renaming=false", "--max-tries=10", "--retry-wait=5",
           "--summary-interval=0", "--console-log-level=warn", "-d",
           os.path.dirname(dest), "-o", os.path.basename(dest), url]
    return subprocess.run(cmd, capture_output=True, text=True)

def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    ok = bad = skip = 0
    for rel, kind, repo, path in ITEMS:
        if only and only not in rel:
            continue
        local = os.path.join(MODELS, rel.replace("/", os.sep))
        if not os.path.exists(local):
            print(f"[缺失] {rel}")
            skip += 1
            continue
        want = None
        if kind == "ms":
            want = ms_hashes(repo).get(path)
        else:
            want = hf_hash(repo, path)
        if not want:
            print(f"[无官方哈希] {rel}")
            skip += 1
            continue
        got = sha256_of(local)
        if got == want:
            print(f"[OK]  {rel}  {os.path.getsize(local)/2**30:.2f}G")
            ok += 1
            continue
        print(f"[坏]  {rel}  本地 {got[:12]} != 官方 {want[:12]}  -> 重下", flush=True)
        url = (f"{MS}/models/{repo}/resolve/master/{path}" if kind == "ms"
               else f"{HF}/{repo}/resolve/main/{path}")
        for attempt in range(1, 4):
            if os.path.exists(local):
                os.remove(local)
            r = download(url, local)
            if os.path.exists(local) and sha256_of(local) == want:
                print(f"      重下成功（第 {attempt} 次）", flush=True)
                ok += 1
                break
            print(f"      第 {attempt} 次仍不匹配", flush=True)
        else:
            print(f"      放弃：{rel}", flush=True)
            bad += 1
    print(f"\n汇总 OK={ok} 坏={bad} 跳过={skip}")

if __name__ == "__main__":
    main()
