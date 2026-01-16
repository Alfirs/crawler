#!/bin/bash
# Dev-тест для генерации карусели

set -e

echo "=== Dev Test для Instagram Carousel Generator ==="

# Проверяем переменные окружения
if [ -z "$NEUROAPI_API_KEY" ]; then
    echo "❌ ОШИБКА: NEUROAPI_API_KEY не установлен"
    exit 1
fi

if [ -z "$NEUROAPI_TEXT_MODEL" ]; then
    export NEUROAPI_TEXT_MODEL="gpt-5-mini"
fi

if [ -z "$NEUROAPI_IMAGE_MODEL" ]; then
    export NEUROAPI_IMAGE_MODEL="gpt-image-1"
fi

if [ -z "$NEUROAPI_BASE_URL" ]; then
    export NEUROAPI_BASE_URL="https://neuroapi.host"
fi

if [ -z "$USE_AI_BACKGROUNDS" ]; then
    export USE_AI_BACKGROUNDS="true"
fi

echo "✅ ENV переменные установлены:"
echo "   TEXT_MODEL=$NEUROAPI_TEXT_MODEL"
echo "   IMAGE_MODEL=$NEUROAPI_IMAGE_MODEL"
echo "   BASE_URL=$NEUROAPI_BASE_URL"
echo "   USE_AI_BACKGROUNDS=$USE_AI_BACKGROUNDS"

# Запускаем сервер в фоне
echo ""
echo "=== Запуск сервера ==="
uvicorn app.min_app:app --host 127.0.0.1 --port 8000 &
SERVER_PID=$!
sleep 3

# Проверяем что сервер запустился
if ! curl -s http://127.0.0.1:8000/health > /dev/null; then
    echo "❌ Сервер не запустился"
    kill $SERVER_PID 2>/dev/null || true
    exit 1
fi

echo "✅ Сервер запущен (PID: $SERVER_PID)"

# Тестовый запрос
echo ""
echo "=== Тестовый запрос ==="
echo "Создаём тестовое изображение для обложки..."
TEST_IMG=$(mktemp)
convert -size 1080x1350 xc:blue -pointsize 72 -fill white -gravity center -annotate +0+0 "Test Cover" "$TEST_IMG" 2>/dev/null || \
    echo "⚠️  ImageMagick не установлен, используем заглушку"

if [ ! -f "$TEST_IMG" ]; then
    # Создаём простую заглушку через Python
    python3 -c "
from PIL import Image
img = Image.new('RGB', (1080, 1350), color='blue')
img.save('$TEST_IMG', 'PNG')
"
fi

RESPONSE=$(curl -X POST http://127.0.0.1:8000/generate \
    -F "cover_image=@$TEST_IMG" \
    -F "title=5 ошибок целеполагания" \
    -F "slides_count=3" \
    -F "bg_prompt=modern office, people planning, dynamic composition" \
    -F "watermark_text=@alfirs" \
    -w "\nHTTP_CODE:%{http_code}" \
    -o /tmp/carousel_test.zip 2>&1)

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
echo "HTTP Code: $HTTP_CODE"

if [ "$HTTP_CODE" != "200" ]; then
    echo "❌ Ошибка генерации:"
    echo "$RESPONSE"
    kill $SERVER_PID 2>/dev/null || true
    rm -f "$TEST_IMG"
    exit 1
fi

echo "✅ Карусель сгенерирована: /tmp/carousel_test.zip"

# Проверяем содержимое ZIP
echo ""
echo "=== Проверка результата ==="
unzip -l /tmp/carousel_test.zip | head -10

# Проверяем логи на наличие правильных вызовов
echo ""
echo "=== Проверка логов ==="
echo "Последние 100 строк лога сервера:"
echo "Проверяем что в логах есть [Image API] Включено изображение: True"
echo "Проверяем что в логах есть [image_provider] generated background ok"
echo "Проверяем что в логах есть [render_content] ... ai_bg=yes"

# Останавливаем сервер
kill $SERVER_PID 2>/dev/null || true
rm -f "$TEST_IMG"

echo ""
echo "=== Тест завершён ==="

