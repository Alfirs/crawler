# scripts/test_env_loader.py
from app.env_loader import load_env
import os, tempfile

content = b"""
# обычная строка
NEUROAPI_BASE_URL=https://neuroapi.host/v1

# export + кавычки + инлайн-коммент
export NEUROAPI_API_KEY="sk-xxx" # comment

# битая строка с NUL
BROKEN\x00KEY=value

# без '='
JUSTTEXT

# пробелы и табы
APP_MODE = "prod"
"""

with tempfile.NamedTemporaryFile(delete=False, mode='wb') as f:
    f.write(content)
    path = f.name

load_env(path)
assert os.getenv("NEUROAPI_BASE_URL") == "https://neuroapi.host/v1"
assert os.getenv("NEUROAPI_API_KEY") == "sk-xxx"
assert os.getenv("APP_MODE") == "prod"
assert os.getenv("BROKENKEY") is None  # должен быть пропущен
print("OK - env_loader test passed")

# Cleanup
os.unlink(path)
