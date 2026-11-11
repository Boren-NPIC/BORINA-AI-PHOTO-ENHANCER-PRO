from io import BytesIO
from pathlib import Path
import warnings

import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

APP_DIR = Path(__file__).resolve().parent
MODEL_PATH = APP_DIR / "models" / "RealESRGAN_x4plus.pth"
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
# Pillow handles common raster formats. Optional plugins add native HEIC/HEIF and AVIF support.
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

try:
    import pillow_avif  # noqa: F401 - registers AVIF support with Pillow
except ImportError:
    pass

QUALITY_LONG_EDGE = {"1080p": 1920, "4k": 3840, "8k": 7680}

app = FastAPI(title="BORINA AI PHOTO ENHANCER PRO", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


_UPSAMPLER = None
_UPSAMPLER_ERROR = None


def get_realesrgan():
    """Load the optional neural upscaler once. Returns None when not configured."""
    global _UPSAMPLER, _UPSAMPLER_ERROR
    if _UPSAMPLER is not None:
        return _UPSAMPLER
    if _UPSAMPLER_ERROR is not None or not MODEL_PATH.exists():
        return None
    try:
        import torch
        from basicsr.archs.rrdbnet_arch import RRDBNet
        from realesrgan import RealESRGANer
        model = RRDBNet(
            num_in_ch=3, num_out_ch=3, num_feat=64,
            num_block=23, num_grow_ch=32, scale=4
        )
        _UPSAMPLER = RealESRGANer(
            scale=4, model_path=str(MODEL_PATH), model=model,
            tile=256, tile_pad=10, pre_pad=0,
            half=bool(torch.cuda.is_available())
        )
        return _UPSAMPLER
    except Exception as exc:
        _UPSAMPLER_ERROR = str(exc)
        warnings.warn(f"Real-ESRGAN unavailable; using local fallback: {exc}")
        return None


def apply_realesrgan(image: Image.Image):
    upsampler = get_realesrgan()
    if upsampler is None:
        return None
    rgb = np.asarray(image.convert("RGB"))
    bgr = rgb[:, :, ::-1].copy()
    output, _ = upsampler.enhance(bgr, outscale=4)
    return Image.fromarray(output[:, :, ::-1].copy())


def decode_uploaded_image(raw: bytes) -> Image.Image:
    """Decode by file signature rather than trusting the browser MIME type.

    Animated images use their first frame. EXIF orientation is applied before
    converting to RGB so downstream enhancement receives a predictable image.
    """
    with Image.open(BytesIO(raw)) as source:
        source.seek(0)
        source.load()
        image = ImageOps.exif_transpose(source).convert("RGB")
    return image


def read_upload(file_bytes: bytes) -> Image.Image:
    if not file_bytes:
        raise HTTPException(status_code=400, detail="The uploaded image is empty.")
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image is too large. Maximum upload size is 50 MB.")
    try:
        return decode_uploaded_image(file_bytes)
    except Exception as exc:
        raise HTTPException(
            status_code=415,
            detail=("This image format is not supported by the installed image codecs. "
                    "Try JPG, PNG, WEBP, GIF, BMP, TIFF, HEIC/HEIF, or AVIF."),
        ) from exc



def analyze_photo(image: Image.Image) -> dict:
    """Lightweight content-aware analysis used to choose restrained auto corrections."""
    sample = image.convert("RGB").copy()
    sample.thumbnail((512, 512), Image.Resampling.LANCZOS)
    rgb = np.asarray(sample, dtype=np.float32) / 255.0
    luminance = 0.2126 * rgb[:, :, 0] + 0.7152 * rgb[:, :, 1] + 0.0722 * rgb[:, :, 2]
    mean_luma = float(luminance.mean())
    contrast = float(luminance.std())
    # A fast edge-energy estimate; it is a heuristic, not a true focus measurement.
    gx = np.abs(np.diff(luminance, axis=1)).mean() if luminance.shape[1] > 1 else 0.0
    gy = np.abs(np.diff(luminance, axis=0)).mean() if luminance.shape[0] > 1 else 0.0
    detail = float((gx + gy) / 2.0)
    saturation = float((rgb.max(axis=2) - rgb.min(axis=2)).mean())

    adjustments = []
    if mean_luma < 0.36:
        adjustments.append("Low-light photo · gentle brightness lift")
    elif mean_luma > 0.76:
        adjustments.append("Bright photo · protect highlights")
    else:
        adjustments.append("Exposure looks balanced")
    if contrast < 0.16:
        adjustments.append("Low contrast · subtle contrast recovery")
    if detail < 0.035:
        adjustments.append("Soft details · careful sharpening")
    if saturation < 0.075:
        adjustments.append("Muted colors · natural color recovery")
    if not adjustments:
        adjustments.append("Balanced image · preserve natural appearance")

    return {
        "mean_brightness": round(mean_luma, 3),
        "contrast": round(contrast, 3),
        "detail_score": round(detail, 4),
        "saturation": round(saturation, 3),
        "recommendations": adjustments,
        "mode": "Smart Auto",
    }


def smart_auto_enhance(image: Image.Image) -> Image.Image:
    """Apply restrained, image-aware corrections without generative face changes."""
    image = ImageOps.exif_transpose(image).convert("RGB")
    stats = analyze_photo(image)
    brightness = stats["mean_brightness"]
    contrast = stats["contrast"]
    saturation = stats["saturation"]
    detail = stats["detail_score"]

    # Lift dark images gently; avoid aggressive brightening of already bright images.
    if brightness < 0.36:
        image = ImageEnhance.Brightness(image).enhance(1.0 + min(0.22, (0.36 - brightness) * 0.65))
    elif brightness > 0.78:
        image = ImageEnhance.Brightness(image).enhance(0.985)

    # Recover flat contrast conservatively.
    if contrast < 0.16:
        image = ImageEnhance.Contrast(image).enhance(1.0 + min(0.16, (0.16 - contrast) * 0.9))
    else:
        image = ImageEnhance.Contrast(image).enhance(1.025)

    # Avoid oversaturating vivid images.
    if saturation < 0.075:
        image = ImageEnhance.Color(image).enhance(1.06)
    else:
        image = ImageEnhance.Color(image).enhance(1.015)

    # Use mild denoise and adaptive sharpening; keep sharpening restrained on detailed photos.
    if detail < 0.035:
        image = image.filter(ImageFilter.MedianFilter(size=3))
        image = image.filter(ImageFilter.UnsharpMask(radius=1.5, percent=125, threshold=5))
    else:
        image = image.filter(ImageFilter.UnsharpMask(radius=1.1, percent=85, threshold=4))
    return image


def conservative_enhance(image: Image.Image) -> Image.Image:
    """Non-generative local fallback; does not synthesize or replace facial features."""
    image = ImageOps.exif_transpose(image).convert("RGB")
    # Mild denoise and restrained sharpening to avoid an artificial/plastic look.
    image = image.filter(ImageFilter.MedianFilter(size=3))
    image = ImageEnhance.Color(image).enhance(1.025)
    image = ImageEnhance.Contrast(image).enhance(1.035)
    image = image.filter(ImageFilter.UnsharpMask(radius=1.4, percent=115, threshold=4))
    return image



def manual_edit_image(image: Image.Image, brightness: float, contrast: float, saturation: float, sharpness: float, skin_smooth: float, blemish: float) -> Image.Image:
    """Apply user-controlled, non-generative photo adjustments."""
    image = image.convert("RGB")
    image = ImageEnhance.Brightness(image).enhance(max(0.2, min(2.0, brightness)))
    image = ImageEnhance.Contrast(image).enhance(max(0.2, min(2.0, contrast)))
    image = ImageEnhance.Color(image).enhance(max(0.0, min(2.0, saturation)))
    if blemish > 0:
        # Conservative global micro-texture cleanup; this is not a face-aware spot-removal tool.
        softened = image.filter(ImageFilter.MedianFilter(size=3))
        image = Image.blend(image, softened, min(0.55, blemish * 0.55))
    if skin_smooth > 0:
        # Gentle luminance smoothing approximation. Keep blend low to avoid plastic skin.
        smooth = image.filter(ImageFilter.GaussianBlur(radius=0.5 + skin_smooth * 1.8))
        image = Image.blend(image, smooth, min(0.42, skin_smooth * 0.42))
    if sharpness != 1.0:
        image = ImageEnhance.Sharpness(image).enhance(max(0.0, min(3.0, sharpness)))
    return image


def remove_image_background(image: Image.Image) -> Image.Image:
    """Use optional local rembg model; never upload the photo to a cloud service."""
    try:
        from rembg import remove
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="Background removal is not installed. Install backend/requirements-background.txt first.") from exc
    try:
        result = remove(image.convert("RGBA"))
        return result.convert("RGBA")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Background removal failed: {exc}") from exc


def resize_long_edge(image: Image.Image, target: int) -> Image.Image:
    width, height = image.size
    long_edge = max(width, height)
    if long_edge == target:
        return image
    scale = target / long_edge
    new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    # Pillow Lanczos is the reliable fallback resampler. Neural upscaling is an optional add-on.
    return image.resize(new_size, Image.Resampling.LANCZOS)


@app.get("/api/health")
def health():
    ai_ready = get_realesrgan() is not None
    return {
        "ok": True,
        "app": "BORINA AI PHOTO ENHANCER PRO",
        "engine": "Real-ESRGAN" if ai_ready else "Pillow local fallback",
        "neural_ai_ready": ai_ready,
        "model_found": MODEL_PATH.exists(),
        "max_upload_mb": MAX_UPLOAD_BYTES // (1024 * 1024),
        "supported_formats": ["JPEG", "PNG", "WEBP", "GIF", "BMP", "TIFF", "ICO", "HEIC/HEIF (plugin)", "AVIF (plugin)"],
    }


@app.post("/api/preview")
async def preview(file: UploadFile = File(...)):
    """Return a browser-friendly JPEG preview, including for HEIC/AVIF uploads."""
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    image = read_upload(raw)
    image.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
    output = BytesIO()
    image.save(output, format="JPEG", quality=88, optimize=True)
    return Response(content=output.getvalue(), media_type="image/jpeg")


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...)):
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    image = read_upload(raw)
    return {"filename": file.filename or "uploaded-image", "width": image.width, "height": image.height, **analyze_photo(image)}


@app.post("/api/enhance")
async def enhance(file: UploadFile = File(...), quality: str = Form("4k")):
    if quality not in QUALITY_LONG_EDGE:
        raise HTTPException(status_code=400, detail="Quality must be 1080p, 4k, or 8k.")

    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    image = read_upload(raw)

    original_size = image.size
    # Smart Auto selects conservative corrections from the uploaded image characteristics.
    image = smart_auto_enhance(image)
    neural_result = apply_realesrgan(image)
    if neural_result is not None:
        image = neural_result
        engine_mode = "Smart Auto + Real-ESRGAN"
    else:
        engine_mode = "Smart Auto · local processing"
    target = QUALITY_LONG_EDGE[quality]
    image = resize_long_edge(image, target)

    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    mode = engine_mode
    headers = {
        "Content-Disposition": f'attachment; filename="borina-enhanced-{quality}.png"',
        "X-Borina-Engine": mode,
        "X-Borina-Original-Size": f"{original_size[0]}x{original_size[1]}",
        "X-Borina-Output-Size": f"{image.width}x{image.height}",
    }
    return Response(content=output.getvalue(), media_type="image/png", headers=headers)


@app.post("/api/edit-preview")
async def edit_preview(
    file: UploadFile = File(...),
    brightness: float = Form(1.0),
    contrast: float = Form(1.0),
    saturation: float = Form(1.0),
    sharpness: float = Form(1.0),
    skin_smooth: float = Form(0.0),
    blemish: float = Form(0.0),
    remove_background: bool = Form(False),
    background_color: str = Form("#111827"),
    background: UploadFile | None = File(None),
):
    """Fast, downscaled preview endpoint used while editing controls move."""
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    image = read_upload(raw)
    image.thumbnail((1400, 1400), Image.Resampling.LANCZOS)
    image = manual_edit_image(image, brightness, contrast, saturation, sharpness, skin_smooth, blemish)
    if remove_background:
        foreground = remove_image_background(image)
        if background is not None:
            bg_raw = await background.read(MAX_UPLOAD_BYTES + 1)
            bg = read_upload(bg_raw).convert("RGB")
            bg = ImageOps.fit(bg, foreground.size, method=Image.Resampling.LANCZOS).convert("RGBA")
        else:
            try:
                color = background_color.strip().lstrip("#")
                if len(color) != 6:
                    raise ValueError("bad color")
                rgb = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
                bg = Image.new("RGBA", foreground.size, (*rgb, 255))
            except Exception as exc:
                raise HTTPException(status_code=400, detail="Background color must be a hex color such as #ffffff.") from exc
        bg.alpha_composite(foreground)
        image = bg.convert("RGB")
    output = BytesIO()
    image.save(output, format="JPEG", quality=88, optimize=True)
    return Response(content=output.getvalue(), media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@app.post("/api/edit")
async def edit_photo(
    file: UploadFile = File(...),
    brightness: float = Form(1.0),
    contrast: float = Form(1.0),
    saturation: float = Form(1.0),
    sharpness: float = Form(1.0),
    skin_smooth: float = Form(0.0),
    blemish: float = Form(0.0),
    remove_background: bool = Form(False),
    background_color: str = Form("#111827"),
    background: UploadFile | None = File(None),
):
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    image = read_upload(raw)
    image = manual_edit_image(image, brightness, contrast, saturation, sharpness, skin_smooth, blemish)
    if remove_background:
        foreground = remove_image_background(image)
        if background is not None:
            bg_raw = await background.read(MAX_UPLOAD_BYTES + 1)
            bg = read_upload(bg_raw).convert("RGB")
            bg = ImageOps.fit(bg, foreground.size, method=Image.Resampling.LANCZOS)
            bg = bg.convert("RGBA")
        else:
            try:
                color = background_color.strip().lstrip("#")
                if len(color) != 6: raise ValueError("bad color")
                rgb = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
                bg = Image.new("RGBA", foreground.size, (*rgb, 255))
            except Exception as exc:
                raise HTTPException(status_code=400, detail="Background color must be a hex color such as #ffffff.") from exc
        bg.alpha_composite(foreground)
        image = bg.convert("RGB")
    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return Response(content=output.getvalue(), media_type="image/png", headers={"Content-Disposition": 'attachment; filename="borina-manual-edit.png"'})
