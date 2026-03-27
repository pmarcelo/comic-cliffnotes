from google import genai
from core import config

print("🔑 Loaded API Key from config. Attempting to contact Gemini...")

try:
    # Initialize the modern client
    client = genai.Client(api_key=config.GEMINI_API_KEY)
    
    # Send a tiny, cheap ping to the model
    response = client.models.generate_content(
        model=config.TARGET_MODEL,
        contents="Please reply with exactly: 'API Connection Successful!'"
    )
    
    print("\n✅ SUCCESS! Gemini responded:")
    print(f"🤖 {response.text}")
    
except Exception as e:
    print(f"\n❌ Connection Failed: {e}")