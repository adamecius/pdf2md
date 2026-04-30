#!/usr/bin/env python3
if __name__ != "__main__":
    import pytest
    pytest.skip("integration script; requires external backend dependencies", allow_module_level=True)

import subprocess
import sys

print("🔍 PaddleOCR Backend Test")
print("=" * 40)

# 1. Check PaddleOCR installation
try:
    check = subprocess.run(
        ["python", "-c", "import paddleocr; print('paddleocr import: OK')"],
        check=True,
        text=True,
        capture_output=True,
    )
    print(f"✅ {check.stdout.strip()}")
except subprocess.CalledProcessError:
    print("❌ ERROR: paddleocr import failed")
    print("   Make sure you are in the (paddleocr-backend) environment")
    sys.exit(1)

# 2. Check GPU availability in paddle
try:
    gpu_check = subprocess.run(
        ["python", "-c", "import paddle; print('CUDA available:', paddle.device.is_compiled_with_cuda())"],
        capture_output=True,
        text=True,
        check=False,
    )
    print(f"🔋 {gpu_check.stdout.strip()}")
except Exception:
    print("⚠️  Could not check GPU (paddle not available)")

print("\n🚀 PaddleOCR backend is ready to run!")
print("To run a smoke test, execute:")
print("   python chatgpt_test.py")
print("=" * 40)
