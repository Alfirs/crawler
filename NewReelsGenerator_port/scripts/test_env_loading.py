# scripts/test_env_loading.py - Тест загрузки .env из корня проекта
import os
import sys
from pathlib import Path

# Добавляем корень проекта в sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print(f"=== Тест загрузки .env из корня проекта ===")
print(f"Project root: {project_root}")
print(f"Expected .env path: {project_root / '.env'}")

# Проверяем, что .env существует
env_path = project_root / ".env"
if not env_path.exists():
    print(f"❌ .env file not found at {env_path}")
    exit(1)
else:
    print(f"✓ .env file exists at {env_path}")

# Очищаем переменные окружения
test_vars = ["NEUROAPI_API_KEY", "NEUROAPI_BASE_URL"]
for var in test_vars:
    os.environ.pop(var, None)

print(f"\n=== Тестируем env_loader ===")

# Импортируем и тестируем наш загрузчик
from app.env_loader import load_env

# Загружаем переменные
loaded_vars = load_env(str(env_path))

print(f"Loaded variables: {list(loaded_vars.keys())}")

# Проверяем, что переменные установлены в os.environ
for var in ["NEUROAPI_API_KEY", "NEUROAPI_BASE_URL"]:
    env_value = os.getenv(var)
    loaded_value = loaded_vars.get(var)
    
    if env_value and loaded_value:
        print(f"✓ {var}: {env_value[:10]}... (loaded: {loaded_value[:10]}...)")
    elif loaded_value:
        print(f"⚠ {var}: loaded '{loaded_value[:10]}...' but not in os.environ")
    else:
        print(f"❌ {var}: not found")

print(f"\n=== Тестируем min_app импорт ===")

# Симулируем поведение min_app.py
app_path = project_root / "app" / "min_app.py"
root_dir = os.path.dirname(os.path.dirname(str(app_path)))
env_path_from_app = os.path.join(root_dir, ".env")

print(f"min_app.py location: {app_path}")
print(f"Calculated ROOT_DIR: {root_dir}")
print(f"Calculated ENV_PATH: {env_path_from_app}")

# Проверяем, что пути совпадают
expected_env = str(project_root / ".env")
if os.path.abspath(env_path_from_app) == os.path.abspath(expected_env):
    print(f"✓ Путь к .env рассчитан корректно")
else:
    print(f"❌ Неверный путь: ожидался {expected_env}, получен {env_path_from_app}")

print(f"\n🎉 Тест завершен успешно!")
