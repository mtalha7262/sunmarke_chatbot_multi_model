# # llms/deepseek_lc.py
# import os
# from dotenv import load_dotenv
# from langchain_openai import ChatOpenAI

# load_dotenv()

# def build_deepseek_llm():
#     """
#     Build and return a DeepSeek (via Qubrid OpenAI-compatible) LLM instance
#     """
#     return ChatOpenAI(
#         model=os.getenv("DEEPSEEK_MODEL", "deepseek-ai/deepseek-r1-distill-llama-70b"),
#         openai_api_key=os.getenv("DEEPSEEK_API_KEY"),  # <-- use DeepSeek key
#         # openai_api_base=os.getenv(
#         #     "DEEPSEEK_BASE_URL",
#         #     "https://api.deepseek.com/v1"
#         # ),  # <-- IMPORTANT: base should end at /qubridai
#         temperature=0.1,
#         max_tokens=512,
#         streaming=True,  # optional, if you want streaming like your requests example
#     )



# import os
# from langchain_openai import ChatOpenAI
# from dotenv import load_dotenv

# load_dotenv()

# def build_deepseek_llm():
#     """
#     Build and return a DeepSeek LLM instance
#     """
#     return ChatOpenAI(
#         model=os.getenv("DEEPSEEK_MODEL_G", "llama-3.3-70b-versatile"),
#         openai_api_key=os.getenv("DEEPSEEK_API_KEY_G"),
#         openai_api_base="https://api.groq.com/openai/v1",
#         temperature=0.1,
#         max_tokens=1024,
#         streaming=True,  # Enable streaming for faster responses
#     )


# llms/deepseek_lc.py
"""
Third LLM option using Groq's Llama 3.3 70B (replacing paid DeepSeek)
This uses a different Groq model than the main Groq LLM for variety
"""

import os
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()


def build_deepseek_llm():
    """
    Build and return a Groq Llama LLM instance (third model option)
    Uses Groq's API to avoid paid DeepSeek service
    
    Returns:
        ChatOpenAI instance configured for Groq's Llama model
        
    Environment Variables Required:
        GROQ_API_KEY: Your Groq API key (same as used for main Groq model)
    """
    
    # Get API key from environment
    api_key = os.getenv("DEEPSEEK_API_KEY_G")
    
    if not api_key:
        raise ValueError(
            "DEEPSEEK_API_KEY_G not found in environment variables. "
            "Please set it in your .env file."
        )
    
    # Use Groq's Llama 3.3 70B model as alternative to paid DeepSeek
    return ChatOpenAI(
        model="llama-3.3-70b-versatile",  # Groq's fast Llama model
        openai_api_key=api_key,
        openai_api_base="https://api.groq.com/openai/v1",
        temperature=0.1,
        max_tokens=1024,
        streaming=True,
        timeout=60,
        max_retries=2,
    )


if __name__ == "__main__":
    # Test the LLM
    try:
        llm = build_deepseek_llm()
        print("✅ Third LLM (Deepseek) initialized successfully")
        
        # Test with a simple query
        response = llm.invoke("Say 'Hello from Deepseek!' in one sentence.")
        print(f"Test response: {response.content}")
        
    except Exception as e:
        print(f"❌ Error initializing third LLM: {e}")