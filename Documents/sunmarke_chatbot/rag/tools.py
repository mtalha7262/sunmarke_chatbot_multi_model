# rag/tools.py
from typing import Dict, Any
from langchain_core.tools import tool

from rag.retriever import RAGRetriever

_retriever = RAGRetriever()

@tool("sunmarke_rag_retrieve")
def sunmarke_rag_retrieve(query: str, k: int = 6) -> Dict[str, Any]:
    """
    Retrieve relevant context from the Sunmarke vector DB.
    Returns: { "context": str, "metas": list }
    """
    try:
        context, metas = _retriever.retrieve(query=query, k=k)
        return {"context": context, "metas": metas}
    except Exception as e:
        print(f"Retrieval error: {e}")
        return {"context": "", "metas": []}