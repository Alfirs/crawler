from dotenv import load_dotenv
import os
from openai import OpenAI
import sys

# Load env from root
load_dotenv('../../.env')

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
api_key = os.getenv("GEMINI_API_KEY")

print(f"Checking API Key: {api_key[:5]}... (length={len(api_key) if api_key else 0})")

if not api_key:
    print("❌ API Key not found!")
    sys.exit(1)

client = OpenAI(api_key=api_key, base_url=GEMINI_BASE_URL)

try:
    print("Sending request to Gemini...")
    response = client.chat.completions.create(
        model="gemini-2.0-flash-exp", # Using a known model or the one in services
        messages=[{"role": "user", "content": "Just say 'TOKEN_OK'"}],
        max_tokens=10
    )
    print("Response:", response.choices[0].message.content)
    print("✅ TOKEN IS WORKING!")
except Exception as e:
    print(f"❌ Error: {e}")
