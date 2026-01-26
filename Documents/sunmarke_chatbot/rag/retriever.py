# # rag/retriever.py
# from typing import Tuple, List
# import os
# import warnings

# from langchain_huggingface import HuggingFaceEmbeddings
# from langchain_community.vectorstores import Chroma

# VECTOR_DB_DIR = os.getenv("VECTOR_DB_DIR", "data/vector_db")


# class RAGRetriever:
#     def __init__(self):
#         self.embeddings = HuggingFaceEmbeddings(
#             model_name=os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
#         )

#         if not os.path.isdir(VECTOR_DB_DIR):
#             warnings.warn(
#                 f"Vector DB directory not found at '{VECTOR_DB_DIR}'. Run ingestion first:\n"
#                 f"  python ingestion/ingest_to_chroma.py",
#                 RuntimeWarning,
#             )
#             self.vdb = None
#             return

#         self.vdb = Chroma(
#             persist_directory=VECTOR_DB_DIR,
#             embedding_function=self.embeddings,
#         )

#     def retrieve(self, query: str, k: int = 6) -> Tuple[str, List[dict]]:
#         if not self.vdb or not query.strip():
#             return "", []

#         docs = self.vdb.similarity_search(query, k=k)
#         if not docs:
#             return "", []

#         context = "\n\n---\n\n".join(d.page_content for d in docs).strip()
#         metas = [d.metadata for d in docs]
#         return context, metas


# # rag/retriever.py
# from typing import Tuple, List
# import os
# import warnings

# from langchain_community.vectorstores import Chroma
# from langchain_google_genai import GoogleGenerativeAIEmbeddings

# VECTOR_DB_DIR = os.getenv("VECTOR_DB_DIR", "data/vector_db")

# class RAGRetriever:
#     def __init__(self):
#         # Uses Gemini embeddings API (no local model)
#         self.embeddings = GoogleGenerativeAIEmbeddings(
#             model=os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001"),
#             # If you prefer explicit key instead of GOOGLE_API_KEY env:
#             google_api_key=os.getenv("GEMINI_API_KEY"),
#         )

#         self.vdb = Chroma(
#             persist_directory=os.getenv("VECTOR_DB_DIR", "data/vector_db"),
#             embedding_function=embeddings
#         )
#         self.vdb = None
#         return

#         self.vdb = Chroma(
#             persist_directory=VECTOR_DB_DIR,
#             embedding_function=self.embeddings,
#         )

#     def retrieve(self, query: str, k: int = 6) -> Tuple[str, List[dict]]:
#         if not self.vdb or not query.strip():
#             return "", []

#         docs = self.vdb.similarity_search(query, k=k)
#         if not docs:
#             return "", []

#         context = "\n\n---\n\n".join(d.page_content for d in docs).strip()
#         metas = [d.metadata for d in docs]
#         return context, metas


# rag/retriever.py
import os
from typing import Tuple, List

from langchain_cohere import CohereEmbeddings
from langchain_pinecone import PineconeVectorStore
from dotenv import load_dotenv

load_dotenv()


class RAGRetriever:
    def __init__(self):
        # Initialize Cohere embeddings
        self.embeddings = CohereEmbeddings(
            cohere_api_key=os.getenv("COHERE_API_KEY"),
            model=os.getenv("COHERE_MODEL", "embed-english-v3.0")
        )
        
        # Connect to Pinecone
        self.vdb = PineconeVectorStore(
            index_name=os.getenv("PINECONE_INDEX_NAME"),
            embedding=self.embeddings
        )
    
    def retrieve(self, query: str, k: int = 6) -> Tuple[str, List[dict]]:
        """
        Retrieve top k relevant documents.
        
        Returns:
            Tuple of (context_string, list_of_metadata)
        """
        results = self.vdb.similarity_search(query, k=k)
        
        # Build context string
        context = "\n\n".join([doc.page_content for doc in results])
        
        # Extract metadata
        metas = [doc.metadata for doc in results]
        
        return context, metas