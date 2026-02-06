# debug_env.py
import os
from dotenv import load_dotenv

load_dotenv()

print("GITHUB_TOKEN:", os.getenv("GITHUB_TOKEN"))
print("OPENAI_API_KEY:", os.getenv("OPENAI_API_KEY"))
