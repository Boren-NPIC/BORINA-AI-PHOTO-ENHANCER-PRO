# Optional Real-ESRGAN setup

Real-ESRGAN installation depends on the installed CUDA/PyTorch version. Install a matching PyTorch build first using the official PyTorch selector, then install a compatible Real-ESRGAN package and its dependencies.

Place the official x4plus weights at `backend/models/RealESRGAN_x4plus.pth`.

This MVP detects the optional engine only when the Python package imports and the weights file exists. Until then it uses Pillow's conservative local enhancement pipeline. Do not download model weights from untrusted mirrors.
