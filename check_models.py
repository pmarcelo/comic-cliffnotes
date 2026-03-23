from google import genai
import os
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

print("🔍 Checking available models for your API Key...")
for m in client.models.list():
    print(f" -> {m.name}")