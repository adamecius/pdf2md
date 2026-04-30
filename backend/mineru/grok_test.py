#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

print("🔍 MinerU Backend Test")
print("=" * 40)

# 1. Check MinerU installation
try:
    version = subprocess.check_output(["mineru", "--version"], text=True).strip()
    print(f"✅ MinerU is installed → {version}")
except FileNotFoundError:
    print("❌ ERROR: 'mineru' command not found!")
    print("   Make sure you are in the (mineru-backend) environment")
    print("   Run: conda activate mineru-backend")
    sys.exit(1)
except subprocess.CalledProcessError:
    print("❌ MinerU command failed")
    sys.exit(1)

# 2. Check GPU (optional but useful)
try:
    gpu_check = subprocess.run(
        ["python", "-c", "import torch; print('CUDA available:', torch.cuda.is_available())"],
        capture_output=True, text=True, check=False
    )
    print(f"🔋 {gpu_check.stdout.strip()}")
except Exception:
    print("⚠️  Could not check GPU (torch not available)")

print("\n🚀 MinerU backend is ready to run!")
print("To test with your own PDF, run:")
print("   python test_mineru.py /path/to/your/document.pdf")
print("=" * 40)
