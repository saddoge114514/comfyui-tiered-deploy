#!/usr/bin/env python
"""ComfyUI 简易出图驱动 —— 只用标准库，走 HTTP API。
用法:
  python gen.py --ckpt waiIllustriousSDXL_v170.safetensors \
      --pos "..." --neg "..." --w 1024 --h 1024 --steps 28 --cfg 5 \
      --seed 12345 --batch 1 --sampler dpmpp_2m --sched karras --prefix test
输出: 打印提示词 id、耗时、生成文件路径
"""
import argparse, json, os, sys, time, urllib.request, urllib.error

SERVER = os.environ.get("COMFY_URL", "http://127.0.0.1:8188")
OUTDIR = os.environ.get("COMFY_OUT", os.path.join(os.environ.get("COMFY_ROOT", "D:/AI"), "output"))


def post(path, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(SERVER + path, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def get(path):
    with urllib.request.urlopen(SERVER + path, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def build(a):
    g = {
        "1": {"class_type": "CheckpointLoaderSimple",
              "inputs": {"ckpt_name": a.ckpt}},
        "2": {"class_type": "CLIPTextEncode",
              "inputs": {"text": a.pos, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode",
              "inputs": {"text": a.neg, "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage",
              "inputs": {"width": a.w, "height": a.h, "batch_size": a.batch}},
    }

    pos, neg = ["2", 0], ["3", 0]
    if getattr(a, "pose", ""):
        g["20"] = {"class_type": "LoadImage", "inputs": {"image": a.pose}}
        g["21"] = {"class_type": "ControlNetLoader", "inputs": {"control_net_name": a.cn}}
        g["22"] = {"class_type": "ControlNetApplyAdvanced",
                   "inputs": {"positive": pos, "negative": neg,
                              "control_net": ["21", 0], "image": ["20", 0],
                              "strength": a.cn_strength,
                              "start_percent": a.cn_start, "end_percent": a.cn_end}}
        pos, neg = ["22", 0], ["22", 1]

    g["5"] = {"class_type": "KSampler",
              "inputs": {"model": ["1", 0], "positive": pos, "negative": neg,
                         "latent_image": ["4", 0], "seed": a.seed, "steps": a.steps,
                         "cfg": a.cfg, "sampler_name": a.sampler,
                         "scheduler": a.sched, "denoise": 1.0}}

    # 第二段：潜空间放大后低 denoise 重采样（hires fix）
    if a.hires > 1.0:
        g["8"] = {"class_type": "LatentUpscaleBy",
                  "inputs": {"samples": ["5", 0], "upscale_method": a.hires_method,
                             "scale_by": a.hires}}
        g["9"] = {"class_type": "KSampler",
                  "inputs": {"model": ["1", 0], "positive": pos, "negative": neg,
                             "latent_image": ["8", 0], "seed": a.seed, "steps": (a.hires_steps or a.steps),
                             "cfg": a.cfg, "sampler_name": a.sampler,
                             "scheduler": a.sched, "denoise": a.hires_denoise}}
        src = ["9", 0]
    else:
        src = ["5", 0]

    g["6"] = {"class_type": "VAEDecode",
              "inputs": {"samples": src, "vae": ["1", 2]}}

    # 修脸段：人脸裁切 → 高清重采样 → 羽化贴回
    img = ["6", 0]
    if getattr(a, "facefix", False):
        g["30"] = {"class_type": "DshFaceCrop",
                   "inputs": {"image": ["6", 0], "model_name": a.face_model,
                              "conf": a.face_conf, "pad": a.face_pad, "target": a.face_target}}
        g["31"] = {"class_type": "VAEEncode",
                   "inputs": {"pixels": ["30", 0], "vae": ["1", 2]}}
        g["32"] = {"class_type": "KSampler",
                   "inputs": {"model": ["1", 0], "positive": pos, "negative": neg,
                              "latent_image": ["31", 0], "seed": a.seed,
                              "steps": a.face_steps, "cfg": a.cfg,
                              "sampler_name": a.sampler, "scheduler": a.sched,
                              "denoise": a.face_denoise}}
        g["33"] = {"class_type": "VAEDecode",
                   "inputs": {"samples": ["32", 0], "vae": ["1", 2]}}
        g["34"] = {"class_type": "DshFacePaste",
                   "inputs": {"image": ["6", 0], "fixed": ["33", 0],
                              "x": ["30", 1], "y": ["30", 2], "w": ["30", 3], "h": ["30", 4],
                              "feather": a.face_feather}}
        img = ["34", 0]

    # 第三段：像素级放大模型（可选）
    if a.upscale:
        g["10"] = {"class_type": "UpscaleModelLoader",
                   "inputs": {"model_name": a.upscale}}
        g["11"] = {"class_type": "ImageUpscaleWithModel",
                   "inputs": {"upscale_model": ["10", 0], "image": img}}
        img = ["11", 0]
    if getattr(a, "final_scale", 0) and a.final_scale > 0:
        g["12"] = {"class_type": "ImageScaleBy",
                   "inputs": {"image": img, "upscale_method": "lanczos",
                              "scale_by": a.final_scale}}
        img = ["12", 0]

    g["7"] = {"class_type": "SaveImage",
              "inputs": {"images": img, "filename_prefix": a.prefix}}
    return g


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ckpt", default="waiIllustriousSDXL_v170.safetensors")
    p.add_argument("--pos", required=True)
    p.add_argument("--neg", default="")
    p.add_argument("--w", type=int, default=1024)
    p.add_argument("--h", type=int, default=1024)
    p.add_argument("--steps", type=int, default=28)
    p.add_argument("--cfg", type=float, default=5.0)
    p.add_argument("--seed", type=int, default=-1)
    p.add_argument("--batch", type=int, default=1)
    p.add_argument("--sampler", default="dpmpp_2m")
    p.add_argument("--sched", default="karras")
    p.add_argument("--prefix", default="test")
    p.add_argument("--hires", type=float, default=1.0,
                   help="潜空间放大倍数，>1 启用两段式（1.5 常用）")
    p.add_argument("--hires-denoise", type=float, default=0.45)
    p.add_argument("--hires-steps", type=int, default=0, help="0 表示沿用 --steps")
    p.add_argument("--hires-method", default="bislerp",
                   choices=["nearest-exact", "bilinear", "area", "bicubic", "bislerp"])
    p.add_argument("--upscale", default="", help="像素放大模型文件名，可空")
    p.add_argument("--pose", default="", help="输入目录里的姿势图文件名")
    p.add_argument("--cn", default="controlnet-openpose-sdxl-1.0.safetensors")
    p.add_argument("--cn-strength", type=float, default=0.85)
    p.add_argument("--cn-start", type=float, default=0.0)
    p.add_argument("--cn-end", type=float, default=0.8)
    p.add_argument("--facefix", action="store_true", help="开人脸二次重采样")
    p.add_argument("--face-model", default="face_yolov8m.pt")
    p.add_argument("--face-conf", type=float, default=0.35)
    p.add_argument("--face-pad", type=float, default=1.8)
    p.add_argument("--face-target", type=int, default=1024)
    p.add_argument("--face-denoise", type=float, default=0.35)
    p.add_argument("--face-steps", type=int, default=20)
    p.add_argument("--face-feather", type=float, default=0.18)
    p.add_argument("--final-scale", type=float, default=0.0, help="放大后缩回倍数，0=不缩")
    a = p.parse_args()
    if a.seed < 0:
        a.seed = int.from_bytes(os.urandom(4), "big") & 0xFFFFFFFF

    t0 = time.time()
    res = post("/prompt", {"prompt": build(a), "client_id": "dsh-driver"})
    pid = res.get("prompt_id")
    if not pid:
        print("提交失败:", json.dumps(res, ensure_ascii=False)[:800])
        return 1
    print(f"prompt_id={pid} seed={a.seed} {a.w}x{a.h} steps={a.steps} cfg={a.cfg}")

    while True:
        time.sleep(0.5)
        h = get(f"/history/{pid}")
        if pid in h:
            entry = h[pid]
            st = entry.get("status", {})
            if st.get("status_str") == "error" or st.get("completed") is False and st.get("status_str") == "error":
                print("执行出错:", json.dumps(st, ensure_ascii=False)[:1500])
                return 2
            if st.get("completed"):
                break
    dt = time.time() - t0
    files = []
    for node_id, out in entry.get("outputs", {}).items():
        for im in out.get("images", []):
            files.append(os.path.join(OUTDIR, im.get("subfolder", ""), im["filename"]))
    print(f"耗时 {dt:.2f}s")
    for f in files:
        sz = os.path.getsize(f) if os.path.exists(f) else -1
        print(f"  {f}  {sz/1024/1024:.2f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
