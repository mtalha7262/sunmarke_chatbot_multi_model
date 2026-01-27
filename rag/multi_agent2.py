# rag/multi_agent.py
import os
import asyncio
import time
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from langchain_core.prompts import ChatPromptTemplate

from llms.gemini_lc import build_llm as build_gemini
# from llms.kimi_lc import build_kimi_llm
from llms.groq_lc import build_groq_llm
from llms.deepseek_lc import build_deepseek_llm
from rag.prompts import SYSTEM_GUARDRAIL, build_user_prompt
from rag.tools import sunmarke_rag_retrieve
from speech.tts_edge import tts_mp3_bytes
import base64


TOP_K = int(os.getenv("TOP_K", "4"))


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


def query_single_model(model_name: str, llm, user_prompt: str) -> Dict[str, Any]:
    """Query a single LLM model"""
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
        
        return {
            "model": model_name,
            "answer": answer,
            "success": True,
            "error": None
        }
    except Exception as e:
        print(f"Error with {model_name}: {e}")
        return {
            "model": model_name,
            "answer": f"Error generating response from {model_name}",
            "success": False,
            "error": str(e)
        }


def answer_question_multi_model(question: str) -> Dict[str, Any]:
    #"kimi": {"answer": str, "success": bool, "error": str},

    """
    Query all 3 models simultaneously and return their responses
    
    Returns:
      {
        "question": str,
        "context": str,
        "metas": list,
        "responses": {
          "gemini": {"answer": str, "success": bool, "error": str},
          "groq": {"answer": str, "success": bool, "error": str},
          "deepseek": {"answer": str, "success": bool, "error": str}
        }
      }
    """
    # 1) Retrieve context once (shared across all models)
    tool_result = sunmarke_rag_retrieve.invoke({"query": question, "k": TOP_K})
    
    if isinstance(tool_result, dict):
        context = tool_result.get("context", "")
        metas = tool_result.get("metas", [])
    else:
        context = str(tool_result)
        metas = []
    
    # 2) Build prompt once
    user_prompt = build_user_prompt(question=question, context=context)
    
    # 3) Initialize all models
    models = {
        "gemini": build_gemini(),
        # "kimi": build_kimi_llm(),
        "groq": build_groq_llm(),
        "deepseek": build_deepseek_llm()
    }
    
    # 4) Query all models in parallel
    responses = {}
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        future_to_model = {
            executor.submit(query_single_model, name, llm, user_prompt): name
            for name, llm in models.items()
        }
        
        for future in as_completed(future_to_model):
            model_name = future_to_model[future]
            try:
                result = future.result()
                responses[model_name] = result
            except Exception as e:
                print(f"Exception for {model_name}: {e}")
                responses[model_name] = {
                    "model": model_name,
                    "answer": f"Failed to get response from {model_name}",
                    "success": False,
                    "error": str(e)
                }
    
    return {
        "question": question,
        "context": context,
        "metas": metas,
        "responses": responses
    }