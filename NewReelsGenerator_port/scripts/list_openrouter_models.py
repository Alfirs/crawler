import os
import json
import requests

api_key = os.getenv("OPENROUTER_API_KEY")
if not api_key:
    raise SystemExit("OPENROUTER_API_KEY not set")

resp = requests.get(
    "https://openrouter.ai/api/v1/models",
    headers={"Authorization": f"Bearer {api_key}"},
    timeout=30,
)
resp.raise_for_status()
models = resp.json().get("data", [])

print(f"Total models: {len(models)}")
for model in models:
    pricing = model.get("pricing") or {}
    prompt_cost = pricing.get("prompt")
    request_cost = pricing.get("request")
    allowance = model.get("allowance") or {}
    is_allowed = allowance.get("is_allowed")
    if is_allowed is None:
        user_caps = model.get("user_capabilities") or {}
        is_allowed = user_caps.get("allowed")
    print(
        json.dumps(
            {
                "id": model.get("id"),
                "prompt_cost": prompt_cost,
                "request_cost": request_cost,
                "allowed": is_allowed,
            },
            ensure_ascii=False,
        )
    )

