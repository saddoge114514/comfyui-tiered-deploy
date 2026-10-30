#!/usr/bin/env python3
"""Wan2.2 视频驱动：双专家 high/low noise + 4步 lightx2v LoRA，两段 KSampler。"""
import argparse, json, os, sys, time, urllib.request, urllib.error

SRV = os.environ.get("COMFY_URL", "http://127.0.0.1:8188").rstrip("/")
OUT = os.environ.get("COMFY_OUT", os.path.join(os.environ.get("COMFY_ROOT", "D:/AI"), "output"))
CLIENT = "dsh-vid-driver"

def post(path, obj):
    data = json.dumps(obj).encode()
    req = urllib.request.Request(SRV + path, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

def get(path):
    with urllib.request.urlopen(SRV + path, timeout=60) as r:
        return json.loads(r.read())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="t2v", choices=["t2v", "i2v"])
    ap.add_argument("--pos", required=True, help="提示词正文或 @文件路径")
    ap.add_argument("--neg", default="", help="负面提示词或 @文件路径")
    ap.add_argument("--w", type=int, default=832)
    ap.add_argument("--h", type=int, default=480)
    ap.add_argument("--length", type=int, default=81, help="帧数，16fps 时 81≈5s")
    ap.add_argument("--fps", type=float, default=16.0)
    ap.add_argument("--steps", type=int, default=4)
    ap.add_argument("--split", type=int, default=2, help="high noise 负责前几步")
    ap.add_argument("--cfg", type=float, default=1.0)
    ap.add_argument("--shift", type=float, default=8.0)
    ap.add_argument("--seed", type=int, default=-1)
    ap.add_argument("--sampler", default="euler")
    ap.add_argument("--sched", default="simple")
    ap.add_argument("--lora-strength", type=float, default=1.0)
    ap.add_argument("--image", default="", help="i2v 的起始图，文件名需在 input 目录")
    ap.add_argument("--prefix", default="wan")
    ap.add_argument("--vae", default="wan_2.1_vae.safetensors")
    a = ap.parse_args()

    def load(s):
        if s.startswith("@"):
            with open(s[1:], "r", encoding="utf-8") as f:
                return f.read().strip()
        return s

    pos, neg = load(a.pos), load(a.neg)
    seed = a.seed if a.seed >= 0 else int.from_bytes(os.urandom(4), "big") >> 1

    tag = "t2v" if a.mode == "t2v" else "i2v"
    g = {
        "1": {"class_type": "UNETLoader",
              "inputs": {"unet_name": f"wan2.2_{tag}_high_noise_14B_fp8_scaled.safetensors",
                         "weight_dtype": "default"}},
        "2": {"class_type": "LoraLoaderModelOnly",
              "inputs": {"model": ["1", 0],
                         "lora_name": f"wan2.2_{tag}_lightx2v_4steps_lora_v1.1_high_noise.safetensors"
                         if tag == "t2v" else
                         "wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors",
                         "strength_model": a.lora_strength}},
        "3": {"class_type": "ModelSamplingSD3",
              "inputs": {"model": ["2", 0], "shift": a.shift}},
        "4": {"class_type": "UNETLoader",
              "inputs": {"unet_name": f"wan2.2_{tag}_low_noise_14B_fp8_scaled.safetensors",
                         "weight_dtype": "default"}},
        "5": {"class_type": "LoraLoaderModelOnly",
              "inputs": {"model": ["4", 0],
                         "lora_name": f"wan2.2_{tag}_lightx2v_4steps_lora_v1.1_low_noise.safetensors"
                         if tag == "t2v" else
                         "wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors",
                         "strength_model": a.lora_strength}},
        "6": {"class_type": "ModelSamplingSD3",
              "inputs": {"model": ["5", 0], "shift": a.shift}},
        "7": {"class_type": "CLIPLoader",
              "inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors", "type": "wan"}},
        "8": {"class_type": "CLIPTextEncode", "inputs": {"text": pos, "clip": ["7", 0]}},
        "9": {"class_type": "CLIPTextEncode", "inputs": {"text": neg, "clip": ["7", 0]}},
        "10": {"class_type": "VAELoader", "inputs": {"vae_name": a.vae}},
        "11": {"class_type": "WanImageToVideo",
               "inputs": {"positive": ["8", 0], "negative": ["9", 0], "vae": ["10", 0],
                          "width": a.w, "height": a.h, "length": a.length, "batch_size": 1}},
        "12": {"class_type": "KSamplerAdvanced",
               "inputs": {"model": ["3", 0], "add_noise": "enable", "noise_seed": seed,
                          "steps": a.steps, "cfg": a.cfg, "sampler_name": a.sampler,
                          "scheduler": a.sched, "positive": ["11", 0], "negative": ["11", 1],
                          "latent_image": ["11", 2], "start_at_step": 0,
                          "end_at_step": a.split, "return_with_leftover_noise": "enable"}},
        "13": {"class_type": "KSamplerAdvanced",
               "inputs": {"model": ["6", 0], "add_noise": "disable", "noise_seed": seed,
                          "steps": a.steps, "cfg": a.cfg, "sampler_name": a.sampler,
                          "scheduler": a.sched, "positive": ["11", 0], "negative": ["11", 1],
                          "latent_image": ["12", 0], "start_at_step": a.split,
                          "end_at_step": a.steps, "return_with_leftover_noise": "disable"}},
        "14": {"class_type": "VAEDecode", "inputs": {"samples": ["13", 0], "vae": ["10", 0]}},
        "15": {"class_type": "CreateVideo",
               "inputs": {"images": ["14", 0], "fps": a.fps}},
        "16": {"class_type": "SaveVideo",
               "inputs": {"video": ["15", 0], "filename_prefix": a.prefix, "format": "mp4"}},
    }

    if a.mode == "i2v" and a.image:
        g["17"] = {"class_type": "LoadImage", "inputs": {"image": a.image}}
        g["11"]["inputs"]["start_image"] = ["17", 0]

    t0 = time.time()
    res = post("/prompt", {"prompt": g, "client_id": CLIENT})
    pid = res.get("prompt_id")
    print(f"prompt_id={pid} seed={seed} {a.w}x{a.h} {a.length}f steps={a.steps} cfg={a.cfg}",
          flush=True)

    while True:
        time.sleep(2.0)
        h = get(f"/history/{pid}")
        if pid in h:
            entry = h[pid]
            st = entry.get("status", {})
            if st.get("completed") or st.get("status_str") == "success":
                break
            if st.get("status_str") == "error":
                print("ERROR:", json.dumps(st, ensure_ascii=False)[:2000])
                sys.exit(1)
        if time.time() - t0 > 3600:
            print("timeout")
            sys.exit(2)

    dt = time.time() - t0
    files = []
    for node in entry.get("outputs", {}).values():
        for k in ("images", "videos", "gifs"):
            for it in node.get(k, []):
                files.append(it.get("filename"))
    print(f"耗时 {dt:.2f}s")
    for f in files:
        p = os.path.join(OUT, f) if f else f
        sz = os.path.getsize(p) / 1048576 if p and os.path.exists(p) else 0
        print(f"  {p}  {sz:.2f} MB")

if __name__ == "__main__":
    main()
