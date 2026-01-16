"""
Тестовая генерация изображения через NeuroAPI (dall-e-3)
Автор: Алексей / 2025

Цель — проверить, что .env читается и генерация работает.
"""

import os
import base64
from openai import OpenAI
from dotenv import load_dotenv, find_dotenv

# === 1. Загрузка .env ===
env_path = find_dotenv()
if not env_path:
    raise SystemExit("❌ Файл .env не найден. Убедись, что он в корне проекта.")
load_dotenv(env_path)

api_key = os.getenv("NEUROAPI_API_KEY")
if not api_key:
    raise SystemExit("❌ Переменная NEUROAPI_API_KEY не найдена в .env")

print("✅ Ключ загружен:", api_key[:8] + "..." + api_key[-4:])

# === 2. Подключение к NeuroAPI ===
client = OpenAI(
    base_url="https://neuroapi.host/v1",
    api_key=api_key,
)

print("🔗 Подключено к NeuroAPI (модель dall-e-3)")

# === 3. Промт для теста ===
prompt = """
Создай минималистичный слайд Instagram в бело-зелёной гамме.
Текст на русском: "5 ошибок предпринимателей".
Формат квадратный, размер 1024x1024.
Стиль — чистый, без людей, без логотипов.
Используй один зелёный акцент (#2f6f4a) и крупный шрифт без засечек.
"""

# === 4. Генерация изображения ===
try:
    res = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024",
        n=1
    )
except Exception as e:
    raise SystemExit(f"❌ Ошибка при запросе: {e}")

# === 5. Сохранение результата ===
b64_data = res.data[0].b64_json
img_bytes = base64.b64decode(b64_data)

os.makedirs("output", exist_ok=True)
output_path = os.path.join("output", "test_dalle.jpg")

with open(output_path, "wb") as f:
    f.write(img_bytes)

print(f"✅ Сохранено изображение: {output_path}")
print("🎉 Проверка завершена успешно.")
