# llms/kimi_lc.py
import os
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

def build_kimi_llm():
    """
    Build and return a Kimi (Moonshot AI) LLM instance
    """
    return ChatOpenAI(
        model=os.getenv("KIMI_MODEL", "kimi-k2-0905-preview"),
        openai_api_key=os.getenv("KIMI_API_KEY"),
        openai_api_base=os.getenv("KIMI_BASE_URL", "https://api.moonshot.ai/v1"),
        temperature=0.1,
        max_tokens=512,
    )