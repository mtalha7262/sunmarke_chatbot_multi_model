# rag/multi_agent.py
import os
import asyncio
import time
from typing import Dict, Any, AsyncGenerator, Optional
from langchain_core.prompts import ChatPromptTemplate

from llms.gemini_lc import build_llm as build_gemini
from llms.groq_lc import build_groq_llm
from llms.deepseek_lc import build_deepseek_llm  # Actually uses Deepseek
from rag.prompts import SYSTEM_GUARDRAIL, build_user_prompt
from rag.tools import sunmarke_rag_retrieve
from speech.tts_edge import tts_mp3_bytes
import base64

TOP_K = int(os.getenv("TOP_K", "4"))

# Updated labels to reflect actual models being used
MODEL_LABELS = {
    "gemini": "Gemini",
    "groq": "Groq",  # First Groq model
    "llama": "Deepseek",   # Second Groq model (was "deepseek")
}


def extract_answer_text(result) -> str:
    """Extract text from various LLM response formats"""
    answer = ""
    
    if hasattr(result, 'content'):
        content = result.content
        
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get('type') == 'text':
                    answer = item.get('text', '')
                    break
                elif isinstance(item, str):
                    answer = item
                    break
        elif isinstance(content, str):
            answer = content
        else:
            answer = str(content)
    else:
        answer = str(result)
    
    if not isinstance(answer, str):
        answer = str(answer)
    
    return answer.strip()


def query_single_model(model_name: str, llm, user_prompt: str, start_time: float) -> Dict[str, Any]:
    """Query a single LLM model and return results with timing"""
    try:
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_GUARDRAIL),
            ("human", "{input}"),
        ])
        
        chain = prompt | llm
        result = chain.invoke({"input": user_prompt})
        answer = extract_answer_text(result)
        
        if not answer:
            answer = "I'm sorry, but I don't have that information available."
        
        # Generate TTS
        audio_b64 = None
        try:
            audio_bytes = tts_mp3_bytes(answer)
            audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
        except Exception as e:
            print(f"TTS error for {model_name}: {e}")
        
        elapsed = time.time() - start_time
        
        return {
            "model": model_name,
            "model_label": MODEL_LABELS.get(model_name, model_name),
            "answer": answer,
            "audio_base64": audio_b64,
            "success": True,
            "error": None,
            "elapsed_time": round(elapsed, 2)
        }
    except Exception as e:
        elapsed = time.time() - start_time
        error_msg = str(e)
        print(f"Error with {model_name}: {error_msg}")
        
        return {
            "model": model_name,
            "model_label": MODEL_LABELS.get(model_name, model_name),
            "answer": f"Error generating response from {model_name}",
            "audio_base64": None,
            "success": False,
            "error": error_msg,
            "elapsed_time": round(elapsed, 2)
        }


def initialize_models() -> Dict[str, Optional[Any]]:
    """
    Initialize all available models in priority order:
    1. Gemini (Google)
    2. Groq (First Groq model)
    3. Deepseek (Second Groq model - replacing paid DeepSeek)
    
    Returns:
        Dict mapping model names to LLM instances (or None if unavailable)
    """
    models = {}
    
    # Priority 1: Gemini
    try:
        models["gemini"] = build_gemini()
        print("✅ Gemini initialized")
    except Exception as e:
        print(f"⚠️ Gemini unavailable: {e}")
        models["gemini"] = None
    
    # Priority 2: Groq (main Groq model)
    try:
        models["groq"] = build_groq_llm()
        print("✅ Groq initialized")
    except Exception as e:
        print(f"⚠️ Groq unavailable: {e}")
        models["groq"] = None
    
    # Priority 3: Deepseek (alternative Groq model, replacing DeepSeek)
    try:
        models["llama"] = build_deepseek_llm()  # Uses Groq's Llama model
        print("✅ Deepseek initialized")
    except Exception as e:
        print(f"⚠️ Deepseek unavailable: {e}")
        models["llama"] = None
    
    # Filter out None values
    available_models = {k: v for k, v in models.items() if v is not None}
    
    if not available_models:
        raise RuntimeError(
            "No LLM models available. Please check your API keys in .env file.\n"
            "Required: GOOGLE_API_KEY, GROQ_API_KEY, DEEPSEEK_API_KEY_G"
        )
    
    print(f"📊 Available models: {list(available_models.keys())}")
    return available_models


async def answer_question_multi_model_streaming(question: str) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Stream responses as each model completes (true real-time streaming)
    
    Yields events:
      - {"type": "context", "context": str, "metas": list}
      - {"type": "model_response", "model": str, "data": {...}}
      - {"type": "error", "message": str}
    """
    
    # 1) Retrieve context once
    try:
        loop = asyncio.get_event_loop()
        tool_result = await loop.run_in_executor(
            None, lambda: sunmarke_rag_retrieve.invoke({"query": question, "k": TOP_K})
        )
        
        if isinstance(tool_result, dict):
            context = tool_result.get("context", "")
            metas = tool_result.get("metas", [])
        else:
            context = str(tool_result)
            metas = []
        
        # Send context
        yield {
            "type": "context",
            "context": context,
            "metas": metas
        }
        
    except Exception as e:
        yield {
            "type": "error",
            "message": f"RAG retrieval error: {str(e)}"
        }
        return
    
    # 2) Build prompt once
    user_prompt = build_user_prompt(question=question, context=context)
    
    # 3) Initialize available models
    try:
        models = initialize_models()
    except Exception as e:
        yield {
            "type": "error",
            "message": f"Model initialization error: {str(e)}"
        }
        return
    
    # 4) Query all available models in parallel using asyncio tasks
    start_time = time.time()
    loop = asyncio.get_event_loop()
    
    # Create a queue for streaming results
    result_queue = asyncio.Queue()
    
    async def model_worker(model_name: str, llm):
        """Worker that runs model query and puts result in queue"""
        try:
            # Run the blocking LLM call in executor
            result = await loop.run_in_executor(
                None, 
                query_single_model, 
                model_name, 
                llm, 
                user_prompt, 
                start_time
            )
            await result_queue.put(("success", model_name, result))
        except Exception as e:
            print(f"Exception for {model_name}: {e}")
            error_result = {
                "model": model_name,
                "model_label": MODEL_LABELS.get(model_name, model_name),
                "answer": f"Failed to get response from {model_name}",
                "audio_base64": None,
                "success": False,
                "error": str(e),
                "elapsed_time": round(time.time() - start_time, 2),
            }
            await result_queue.put(("error", model_name, error_result))
    
    # Start all model workers and wait for them in background
    tasks = [model_worker(name, llm) for name, llm in models.items()]
    # FIX: Don't use create_task(gather), just use gather directly
    gather_task = asyncio.gather(*tasks, return_exceptions=True)
    
    # Stream results as they arrive
    completed = 0
    total_models = len(models)
    
    while completed < total_models:
        try:
            # Wait for next result with timeout
            status, model_name, result = await asyncio.wait_for(
                result_queue.get(), 
                timeout=60.0
            )
            
            # Stream this model's response immediately
            yield {
                "type": "model_response",
                "model": model_name,
                "data": result
            }
            
            completed += 1
            
        except asyncio.TimeoutError:
            print(f"Timeout waiting for model responses")
            break
        except Exception as e:
            print(f"Error in streaming loop: {e}")
            break
    
    # Wait for all tasks to complete
    try:
        await gather_task
    except Exception as e:
        print(f"Error waiting for tasks: {e}")