import os
import requests

API_KEY = os.environ.get("OPENROUTER_API_KEY")
if not API_KEY:
    raise SystemExit("OPENROUTER_API_KEY not set")

headers = {
    "Authorization": f"Bearer {API_KEY}",
}

resp = requests.get("https://openrouter.ai/api/v1/models", headers=headers, timeout=30)
print("status", resp.status_code)
if resp.status_code != 200:
    print(resp.text)
    raise SystemExit()

data = resp.json().get("data", [])
free_allowed = []
for model in data:
    pricing = model.get("pricing") or {}
    request_price = pricing.get("request", "1")
    prompt_price = pricing.get("prompt", "1")
    allowed = model.get("allowance", {}).get("is_allowed")
    model_id = model.get("id")
    if request_price in (0, "0") and prompt_price in (0, "0") and allowed:
        free_allowed.append(model_id)

print("free allowed models:")
for mid in free_allowed:
    print(mid)
