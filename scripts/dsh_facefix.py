"""DSH 修脸节点：YOLO 检测人脸 → 裁切放大 → 重采样后贴回。

不用 Impact Pack，只依赖 ultralytics（已装进内嵌 python）。
节点：
  DshFaceCrop  : IMAGE + 模型名 → 裁剪图 + bbox 整数（便于贴回）
  DshFacePaste : 原图 + 修好的裁剪图 + bbox → 羽化贴回
"""
import os
import numpy as np
import torch

ROOT = os.environ.get("COMFY_ROOT", "D:/AI")
MODELS_DIR = os.environ.get("COMFYUI_MODELS", os.path.join(ROOT, "models"))
MODEL_ROOTS = [os.path.join(MODELS_DIR, "ultralytics", "bbox"), os.path.join(MODELS_DIR, "ultralytics", "segm")]

_CACHE = {}


def _find_model(name):
    if os.path.isabs(name) and os.path.exists(name):
        return name
    for root in MODEL_ROOTS:
        p = os.path.join(root, name)
        if os.path.exists(p):
            return p
    raise FileNotFoundError(f"找不到检测模型 {name}，已查找 {MODEL_ROOTS}")


def _load(name):
    if name not in _CACHE:
        from ultralytics import YOLO
        _CACHE[name] = YOLO(_find_model(name))
    return _CACHE[name]


def _to_numpy(img):
    """ComfyUI IMAGE [B,H,W,C] float 0-1 → uint8 RGB"""
    a = (img.clamp(0, 1) * 255.0).round().to(torch.uint8).cpu().numpy()
    return a


def _feather_mask(h, w, feather):
    m = np.ones((h, w), dtype=np.float32)
    f = max(1, int(min(h, w) * feather))
    ramp = np.linspace(0.0, 1.0, f, dtype=np.float32)
    m[:f, :] *= ramp[:, None]
    m[-f:, :] *= ramp[::-1][:, None]
    m[:, :f] *= ramp[None, :]
    m[:, -f:] *= ramp[::-1][None, :]
    return m


class DshFaceCrop:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "model_name": ("STRING", {"default": "face_yolov8m.pt"}),
                "conf": ("FLOAT", {"default": 0.35, "min": 0.05, "max": 0.95, "step": 0.05}),
                "pad": ("FLOAT", {"default": 1.8, "min": 1.0, "max": 4.0, "step": 0.1}),
                "target": ("INT", {"default": 1024, "min": 256, "max": 2048, "step": 64}),
            }
        }

    RETURN_TYPES = ("IMAGE", "INT", "INT", "INT", "INT")
    RETURN_NAMES = ("crop", "x", "y", "w", "h")
    FUNCTION = "run"
    CATEGORY = "dsh"

    def run(self, image, model_name, conf, pad, target):
        arr = _to_numpy(image)
        H, W = arr[0].shape[:2]
        model = _load(model_name)
        res = model(arr[0][:, :, ::-1], conf=conf, verbose=False, device="cuda:0")
        boxes = res[0].boxes.xyxy.cpu().numpy()

        if len(boxes) == 0:
            x0, y0, x1, y1 = 0, 0, W, H
        else:
            # 取面积最大的那张脸
            areas = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
            b = boxes[int(np.argmax(areas))]
            cx, cy = (b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0
            half = max(b[2] - b[0], b[3] - b[1]) * pad / 2.0
            x0, x1 = cx - half, cx + half
            y0, y1 = cy - half, cy + half

        x0, y0 = int(max(0, x0)), int(max(0, y0))
        x1, y1 = int(min(W, x1)), int(min(H, y1))
        w, h = max(64, x1 - x0), max(64, y1 - y0)

        crop = arr[:, y0:y0 + h, x0:x0 + w, :]
        t = torch.from_numpy(crop).float().div_(255.0).permute(0, 3, 1, 2)
        t = torch.nn.functional.interpolate(t, size=(target, target), mode="bicubic",
                                            align_corners=False)
        t = t.permute(0, 2, 3, 1).clamp(0, 1)
        return (t, x0, y0, w, h)


class DshFacePaste:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "fixed": ("IMAGE",),
                "x": ("INT", {"default": 0, "min": 0, "max": 8192}),
                "y": ("INT", {"default": 0, "min": 0, "max": 8192}),
                "w": ("INT", {"default": 256, "min": 32, "max": 8192}),
                "h": ("INT", {"default": 256, "min": 32, "max": 8192}),
                "feather": ("FLOAT", {"default": 0.18, "min": 0.0, "max": 0.5, "step": 0.02}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "run"
    CATEGORY = "dsh"

    def run(self, image, fixed, x, y, w, h, feather):
        base = _to_numpy(image).astype(np.float32)
        patch = _to_numpy(fixed)
        t = torch.from_numpy(patch).float().div_(255.0).permute(0, 3, 1, 2)
        t = torch.nn.functional.interpolate(t, size=(h, w), mode="bicubic",
                                            align_corners=False)
        patch = (t.permute(0, 2, 3, 1).numpy() * 255.0).round().clip(0, 255).astype(np.float32)

        mask = _feather_mask(h, w, feather)[None, :, :, None]
        out = base.copy()
        out[:, y:y + h, x:x + w, :] = base[:, y:y + h, x:x + w, :] * (1 - mask) + patch * mask
        return (torch.from_numpy(out / 255.0).float(),)


NODE_CLASS_MAPPINGS = {
    "DshFaceCrop": DshFaceCrop,
    "DshFacePaste": DshFacePaste,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "DshFaceCrop": "DSH 人脸裁切",
    "DshFacePaste": "DSH 人脸贴回",
}
