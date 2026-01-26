# llms/gemini_lc.py
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

load_dotenv()

def build_llm():
    """
    Build and return a ChatGoogleGenerativeAI instance optimized for speed
    """
    return ChatGoogleGenerativeAI(
        model=os.getenv("GEMINI_MODEL", "gemini-3-flash-preview"),  # Flash is faster
        google_api_key=os.getenv("GEMINI_API_KEY"),
        temperature=0.1,
        max_output_tokens=1024,  # Limit response length for speed
        convert_system_message_to_human=True
    )