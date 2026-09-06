import asyncio
from google import genai
import os
from dotenv import load_dotenv

load_dotenv("backend/.env")

async def test():
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    try:
        res = client.models.embed_content(model="text-embedding-004", contents="test")
        print("Success:", res.embeddings[0].values[:5])
    except Exception as e:
        print("Failed:", e)

asyncio.run(test())
