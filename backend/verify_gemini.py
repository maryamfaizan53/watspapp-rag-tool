import asyncio
import os
from dotenv import load_dotenv
load_dotenv('.env', override=True)

from app.services import llm

async def verify_gemini():
    print(f"Testing Gemini with model: {os.environ.get('GEMINI_MODEL')}")
    prompt = "Reply with only the word 'SUCCESS' if you can read this."
    answer = await llm.safe_generate(prompt)
    print(f"Gemini Response: {answer}")

if __name__ == "__main__":
    import sys
    sys.path.append(os.getcwd())
    asyncio.run(verify_gemini())
