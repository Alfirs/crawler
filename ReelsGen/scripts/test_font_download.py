#!/usr/bin/env python3
"""
Тестирование загрузки шрифтов с Google Fonts
"""
import requests

def test_google_fonts_download():
    # Тестируем разные URL для загрузки Inter
    test_urls = [
        "https://fonts.google.com/download?family=Inter",
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap",
        "https://github.com/rsms/inter/releases/download/v3.19/Inter-3.19.zip"
    ]
    
    for i, url in enumerate(test_urls, 1):
        try:
            print(f"[{i}] Тестируем URL: {url}")
            
            response = requests.get(url, timeout=10)
            print(f"Status: {response.status_code}")
            print(f"Content-Type: {response.headers.get('Content-Type', 'Unknown')}")
            print(f"Content-Length: {len(response.content)} bytes")
            
            # Проверяем первые байты
            if len(response.content) > 0:
                first_bytes = response.content[:10]
                print(f"Первые байты: {first_bytes}")
                
                # Проверяем тип файла
                if response.content.startswith(b'PK'):
                    print("[OK] Это ZIP файл")
                elif b'@font-face' in response.content[:1000]:
                    print("[OK] Это CSS с ссылками на шрифты")
                elif response.content.startswith(b'\x00\x01\x00\x00'):
                    print("[OK] Это TTF файл")
                else:
                    print("[?] Неизвестный тип файла")
            
            print("-" * 50)
            
        except Exception as e:
            print(f"[ERROR] Ошибка: {e}")
            print("-" * 50)

if __name__ == "__main__":
    test_google_fonts_download()
