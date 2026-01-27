# rag/agent.py
import os
from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from llms.gemini_lc import build_llm
from rag.prompts import SYSTEM_GUARDRAIL, build_user_prompt
from rag.tools import sunmarke_rag_retrieve

TOP_K = int(os.getenv("TOP_K", "6"))

def answer_question(question: str) -> Dict[str, Any]:
    """
    Returns:
      {
        "answer": str,
        "metas": list[dict],
        "context": str
      }
    """
    llm = build_llm()

    # 1) retrieve context (via tool)
    tool_result = sunmarke_rag_retrieve.invoke({"query": question, "k": TOP_K})
    
    # Handle both dict and string returns from tool
    if isinstance(tool_result, dict):
        context = tool_result.get("context", "")
        metas = tool_result.get("metas", [])
    else:
        context = str(tool_result)
        metas = []

    # 2) build prompt with context
    user_prompt = build_user_prompt(question=question, context=context)

    # 3) get answer directly from LLM
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_GUARDRAIL),
        ("human", "{input}"),
    ])
    
    chain = prompt | llm
    result = chain.invoke({"input": user_prompt})
    
    # Extract text from AIMessage - handle multiple response formats
    answer = ""
    
    if hasattr(result, 'content'):
        content = result.content
        
        # If content is a list (like from Gemini)
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get('type') == 'text':
                    answer = item.get('text', '')
                    break
                elif isinstance(item, str):
                    answer = item
                    break
        # If content is a string
        elif isinstance(content, str):
            answer = content
        else:
            answer = str(content)
    else:
        answer = str(result)
    
    # Ensure answer is a string and strip whitespace
    if not isinstance(answer, str):
        answer = str(answer)
    
    return {
        "answer": answer.strip(),
        "metas": metas,
        "context": context
    }