from openai import OpenAI
from dotenv import load_dotenv
import base64, os

load_dotenv()  # <-- добавили

api_key = os.getenv("NEUROAPI_API_KEY")
if not api_key:
    raise SystemExit("❌ Нет NEUROAPI_API_KEY в .env")

client = OpenAI(
    base_url="https://neuroapi.host/v1",
    api_key=api_key
)

print("🔗 Using NeuroAPI (dall-e-3)")

prompt = """
Создай минималистичный слайд Instagram (1080x1080) с белым фоном,
зелёным акцентом #2f6f4a и текстом на русском:
"5 ошибок предпринимателей".
Шрифт жирный без засечек, текст в центре, аккуратная композиция.
"""

res = client.images.generate(
    model="dall-e-3",
    prompt=prompt,
    size="1024x1024",
    n=1
)

b64 = res.data[0].b64_json
os.makedirs("output", exist_ok=True)
path = "output/test_dalle.jpg"
with open(path, "wb") as f:
    f.write(base64.b64decode(b64))

print(f"✅ Сохранено: {path}")
