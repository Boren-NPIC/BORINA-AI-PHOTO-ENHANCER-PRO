# BORINA AI PHOTO ENHANCER PRO

Website MVP with a React/Vite frontend and a local FastAPI image-processing backend.

## Smart Auto update
- Automatically analyzes each uploaded image for brightness, contrast, edge/detail level, and saturation.
- Shows image-specific suggestions after upload.
- One-click enhancement applies restrained adaptive corrections rather than the same fixed settings to every photo.
- Uses local processing; optional Real-ESRGAN neural upscaling is used when correctly installed.
- Analysis runs on a downscaled sample to reduce memory use.

## Phase 1 features
- Upload JPG, PNG, or WEBP images
- One-click conservative enhancement
- Preserve original aspect ratio
- Export 1080p, 4K, or 8K (long edge target)
- Before/after preview and download
- Local processing; no paid API key
- Safe fallback enhancement using Pillow if the optional Real-ESRGAN engine is not installed

> Face identity note: no generative face replacement is used. The default pipeline applies conservative denoising, sharpening, and resizing. No software can guarantee mathematically identical facial details after enhancement, especially when the source is blurry or low-resolution.

## Requirements
- Windows 10/11
- Python 3.10 or 3.11
- Node.js 20+

## Run on Windows
1. Extract this ZIP.
2. Open the project folder in VS Code.
3. Open a terminal in the project root and run:

```powershell
cd backend
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

4. Open a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

5. Open the Vite URL shown in the terminal (usually http://localhost:5173).

## Optional Real-ESRGAN AI engine
Phase 1 works without this optional engine using a high-quality local enhancement fallback. To add true neural upscaling, install a compatible PyTorch/Real-ESRGAN environment for your NVIDIA GPU and place the official `RealESRGAN_x4plus.pth` weights at:

`backend/models/RealESRGAN_x4plus.pth`

Then install `backend/requirements-real-esrgan.txt` and follow `backend/REAL_ESRGAN_SETUP.md`. The app automatically uses Real-ESRGAN when the dependencies and model weights are available; otherwise it reports that it is using the local fallback. Model downloads are separate and may be large. No model is bundled in this ZIP.

## Vercel deployment
Vercel can host the frontend, but it cannot run this local GPU model as a persistent backend. For the local-first workflow, run the backend on the Windows PC and use the website locally. A public Vercel deployment will need a separately hosted processing service or a secure user-controlled local-agent connection. Do not expose the local backend directly to the public internet.

## API
- `GET /api/health`
- `POST /api/enhance` multipart fields: `file`, `quality` (`1080p`, `4k`, `8k`)

Generated results are returned as PNG downloads. Uploaded images are processed in memory and are not saved permanently by the backend.


## Supported image uploads

The uploader accepts browser image files (`image/*`) and validates the actual file contents on the backend instead of trusting the filename or MIME type. Supported formats include JPEG/JPG, PNG, WEBP, GIF (first frame), BMP, TIFF/TIF, ICO, HEIC/HEIF, and AVIF. HEIC/HEIF and AVIF support is provided by the optional Pillow plugins in `backend/requirements.txt`. Upload limit: 50 MB.

Uploads are decoded and converted to RGB for processing; the original uploaded file is not overwritten. Some specialist camera RAW formats (for example CR2, NEF, ARW, DNG) and vector SVG files are not included in this raster-photo workflow. Convert those to TIFF or PNG first.


## Manual Photo Editor (new)
- Manual brightness, contrast, saturation and sharpness sliders.
- Gentle skin smoothing and texture cleanup sliders (general image processing, not precise acne/spot detection).
- Optional local AI background removal and replacement with a solid color or another image.
- Background removal is optional and requires `backend/requirements-background.txt`; install with `pip install -r requirements-background.txt`. The first run may download the rembg model files.
- All editing requests run against the local FastAPI backend.

### Important limitations
Skin smoothing and texture cleanup are global, conservative image adjustments; they do not guarantee flawless skin or selectively remove every pimple. For best natural results, use low values. Background removal requires the optional rembg CPU package/model.


## Live Manual Editor update
- Manual controls now update a downscaled live preview automatically after a short debounce; there is no Apply button.
- The live preview uses a dedicated `/api/edit-preview` endpoint and does not replace the original uploaded file.
- Final full-resolution editing and export remain separate from the quick preview.
- Brightness, contrast, saturation, and sharpness slider ranges are restrained to reduce accidental clipping and over-saturation.
- Responsive editor layout supports narrow phone screens, tablets, and desktop browsers, with larger touch targets.
- On phones, controls stack vertically and previews preserve the full image aspect ratio.


## Auto-fit image workspace update
- The preview now fills the available workspace without cropping the photo (`object-fit: contain`).
- Portrait, landscape, and square images are automatically scaled to fit the canvas while preserving their aspect ratio.
- The original pixel dimensions are shown on the preview.
- The same fit behavior applies to the live edited preview.
