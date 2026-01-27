# llms/groq_lc.py
import os
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

def build_groq_llm():
    """
    Build and return a Groq LLM instance (replacing Kimi)
    """
    return ChatOpenAI(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        openai_api_key=os.getenv("GROQ_API_KEY"),
        openai_api_base="https://api.groq.com/openai/v1",
        temperature=0.1,
        max_tokens=1024,
        streaming=True,  # Enable streaming for faster responses
    )
