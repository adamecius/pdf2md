#!/usr/bin/env python3
import os
import sys

print("🔍 GLM OCR Backend Test")
print("=" * 40)

try:
    import glmocr  # noqa: F401
    print("✅ glmocr SDK is installed")
except Exception as exc:
    print(f"❌ ERROR: glmocr SDK is not available ({exc})")
    sys.exit(1)

api_key = os.getenv("ZHIPU_API_KEY")
if api_key:
    print("✅ ZHIPU_API_KEY is set")
else:
    print("⚠️  ZHIPU_API_KEY is not set")
    print("   Export it before running end-to-end OCR tests.")

print("\n🚀 GLM OCR backend basic checks completed!")
print("=" * 40)
