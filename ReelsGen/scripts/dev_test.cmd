@echo off
REM Dev-тест для генерации карусели (Windows)

echo === Dev Test для Instagram Carousel Generator ===

REM Проверяем переменные окружения
if "%NEUROAPI_API_KEY%"=="" (
    echo ❌ ОШИБКА: NEUROAPI_API_KEY не установлен
    exit /b 1
)

if "%NEUROAPI_TEXT_MODEL%"=="" set NEUROAPI_TEXT_MODEL=gpt-5-mini
if "%NEUROAPI_IMAGE_MODEL%"=="" set NEUROAPI_IMAGE_MODEL=gpt-image-1
if "%NEUROAPI_BASE_URL%"=="" set NEUROAPI_BASE_URL=https://neuroapi.host
if "%USE_AI_BACKGROUNDS%"=="" set USE_AI_BACKGROUNDS=true

echo ✅ ENV переменные установлены:
echo    TEXT_MODEL=%NEUROAPI_TEXT_MODEL%
echo    IMAGE_MODEL=%NEUROAPI_IMAGE_MODEL%
echo    BASE_URL=%NEUROAPI_BASE_URL%
echo    USE_AI_BACKGROUNDS=%USE_AI_BACKGROUNDS%

echo.
echo === Запуск сервера ===
start /B uvicorn app.min_app:app --host 127.0.0.1 --port 8000
timeout /t 3 /nobreak >nul

echo ✅ Сервер должен быть запущен

echo.
echo === Тестовый запрос ===
echo Создаём тестовое изображение для обложки...

python -c "from PIL import Image; img = Image.new('RGB', (1080, 1350), color='blue'); img.save('test_cover.png', 'PNG')"

curl -X POST http://127.0.0.1:8000/generate ^
    -F "cover_image=@test_cover.png" ^
    -F "title=5 ошибок целеполагания" ^
    -F "slides_count=3" ^
    -F "bg_prompt=modern office, people planning, dynamic composition" ^
    -F "watermark_text=@alfirs" ^
    -o carousel_test.zip

if %ERRORLEVEL% NEQ 0 (
    echo ❌ Ошибка генерации
    del test_cover.png 2>nul
    exit /b 1
)

echo ✅ Карусель сгенерирована: carousel_test.zip

echo.
echo === Тест завершён ===
del test_cover.png 2>nul

