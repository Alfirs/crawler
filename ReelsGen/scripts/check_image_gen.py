"""
Тестовый скрипт для проверки генерации изображений без сервера
"""
import asyncio
import io
import os
import sys

# Добавляем путь к проекту
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from PIL import Image
from app.services.image_provider import generate_image_bytes
from app.services.utils_io import cover_fit, CANVAS_SIZE, make_run_dir, slugify


async def main():
    prompt = "angry couple arguing, interior, dramatic, comic illustration, no text"
    
    print(f"[check] Starting image generation...")
    print(f"[check] Prompt: {prompt}")
    
    try:
        raw = await generate_image_bytes(prompt, width=1080, height=1350)
        print(f"[check] ✅ Got bytes: {len(raw)}")
        
        img = Image.open(io.BytesIO(raw)).convert("RGBA")
        print(f"[check] Image opened: {img.size} mode={img.mode}")
        
        img = cover_fit(img, CANVAS_SIZE)
        print(f"[check] Image processed: {img.size} mode={img.mode}")
        
        out_root = os.path.join(project_root, "app", "static", "outputs")
        run_dir = make_run_dir(os.path.abspath(out_root), "debug-image-gen")
        out_path = os.path.join(run_dir, "check.png")
        
        img.save(out_path, "PNG")
        print(f"[check] ✅ Saved to: {out_path}")
        print(f"[check] SUCCESS!")
        
        return 0
    except Exception as e:
        print(f"[check] ❌ ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)


