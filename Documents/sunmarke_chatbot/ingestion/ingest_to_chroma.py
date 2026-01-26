# import os
# from typing import List

# from langchain_community.document_loaders import TextLoader
# from langchain_text_splitters import RecursiveCharacterTextSplitter
# from langchain_huggingface import HuggingFaceEmbeddings
# from langchain_community.vectorstores import Chroma

# PARSED_DIR = "data/parsed_content"
# VECTOR_DB_DIR = "data/vector_db"


# def infer_category(filename: str) -> str:
#     name = filename.lower()
#     if "admissions" in name or "admission" in name:
#         return "admissions"
#     if "fee" in name or "tuition" in name:
#         return "fees"
#     if "curriculum" in name or "learning" in name:
#         return "curriculum"
#     if "facility" in name or "campus" in name:
#         return "facilities"
#     if "uniform" in name or "timings" in name or "calendar" in name or "policies" in name:
#         return "parents"
#     return "general"


# def load_documents() -> List:
#     docs = []
#     if not os.path.exists(PARSED_DIR):
#         print(f"Warning: {PARSED_DIR} does not exist.")
#         return docs
        
#     for file in os.listdir(PARSED_DIR):
#         if not file.endswith("_clean.txt"):
#             continue

#         path = os.path.join(PARSED_DIR, file)
#         loader = TextLoader(path, encoding="utf-8")
#         loaded = loader.load()

#         for d in loaded:
#             d.metadata["source"] = file
#             d.metadata["category"] = infer_category(file)

#         docs.extend(loaded)

#     return docs


# def main() -> None:
#     os.makedirs(VECTOR_DB_DIR, exist_ok=True)

#     documents = load_documents()
#     print(f"Loaded {len(documents)} documents")

#     if not documents:
#         print("No documents found to ingest.")
#         return

#     splitter = RecursiveCharacterTextSplitter(
#         chunk_size=800,
#         chunk_overlap=150,
#         separators=["\n\n", "\n", ". ", " "],
#     )

#     chunks = splitter.split_documents(documents)
#     print(f"Created {len(chunks)} chunks")

#     embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

#     vectorstore = Chroma.from_documents(
#         documents=chunks,
#         embedding=embeddings,
#         persist_directory=VECTOR_DB_DIR,
#     )
#     # vectorstore.persist() # Chroma 0.4+ persists automatically

#     print(f"✅ Ingestion complete. Vector DB saved to {VECTOR_DB_DIR}")


# if __name__ == "__main__":
#     main()


# import os
# from typing import List

# from langchain_community.document_loaders import TextLoader
# from langchain_text_splitters import RecursiveCharacterTextSplitter
# from langchain_huggingface import HuggingFaceEmbeddings
# from langchain_chroma import Chroma
# from dotenv import load_dotenv

# load_dotenv()

# PARSED_DIR = "data/parsed_content"
# VECTOR_DB_DIR = os.getenv("VECTOR_DB_DIR", "data/vector_db")


# def infer_category(filename: str) -> str:
#     name = filename.lower()
#     if "admissions" in name or "admission" in name:
#         return "admissions"
#     if "fee" in name or "tuition" in name:
#         return "fees"
#     if "curriculum" in name or "learning" in name:
#         return "curriculum"
#     if "facility" in name or "campus" in name:
#         return "facilities"
#     if "uniform" in name or "timings" in name or "calendar" in name or "policies" in name:
#         return "parents"
#     return "general"


# def load_documents() -> List:
#     docs = []
#     if not os.path.exists(PARSED_DIR):
#         print(f"Warning: {PARSED_DIR} does not exist.")
#         return docs
        
#     for file in os.listdir(PARSED_DIR):
#         if not file.endswith("_clean.txt"):
#             continue

#         path = os.path.join(PARSED_DIR, file)
#         loader = TextLoader(path, encoding="utf-8")
#         loaded = loader.load()

#         for d in loaded:
#             d.metadata["source"] = file
#             d.metadata["category"] = infer_category(file)

#         docs.extend(loaded)

#     return docs


# def main() -> None:
#     # Delete old database if it exists
#     if os.path.exists(VECTOR_DB_DIR):
#         print(f"Removing old vector DB at {VECTOR_DB_DIR}...")
#         import shutil
#         shutil.rmtree(VECTOR_DB_DIR)
    
#     os.makedirs(VECTOR_DB_DIR, exist_ok=True)

#     documents = load_documents()
#     print(f"Loaded {len(documents)} documents")

#     if not documents:
#         print("No documents found to ingest.")
#         return

#     splitter = RecursiveCharacterTextSplitter(
#         chunk_size=800,
#         chunk_overlap=150,
#         separators=["\n\n", "\n", ". ", " "],
#     )

#     chunks = splitter.split_documents(documents)
#     print(f"Created {len(chunks)} chunks")

#     # Use HuggingFace embeddings (runs locally, no rate limits)
#     print("Loading embedding model...")
#     embeddings = HuggingFaceEmbeddings(
#         model_name=os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
#         model_kwargs={'device': 'cpu'},  # Use 'cuda' if you have GPU
#         encode_kwargs={'normalize_embeddings': True}
#     )

#     print("Creating vector database...")
#     vectorstore = Chroma.from_documents(
#         documents=chunks,
#         embedding=embeddings,
#         persist_directory=VECTOR_DB_DIR,
#     )

#     print(f"✅ Ingestion complete. Vector DB saved to {VECTOR_DB_DIR}")


# if __name__ == "__main__":
#     main()



# ingestion/ingest_to_pinecone.py
import os
import time
from typing import List

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_cohere import CohereEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec
from dotenv import load_dotenv

load_dotenv()

PARSED_DIR = "data/parsed_content"


def infer_category(filename: str) -> str:
    name = filename.lower()
    if "admissions" in name or "admission" in name:
        return "admissions"
    if "fee" in name or "tuition" in name:
        return "fees"
    if "curriculum" in name or "learning" in name:
        return "curriculum"
    if "facility" in name or "campus" in name:
        return "facilities"
    if "uniform" in name or "timings" in name or "calendar" in name or "policies" in name:
        return "parents"
    return "general"


def load_documents() -> List:
    docs = []
    if not os.path.exists(PARSED_DIR):
        print(f"Warning: {PARSED_DIR} does not exist.")
        return docs
        
    for file in os.listdir(PARSED_DIR):
        if not file.endswith("_clean.txt"):
            continue

        path = os.path.join(PARSED_DIR, file)
        loader = TextLoader(path, encoding="utf-8")
        loaded = loader.load()

        for d in loaded:
            d.metadata["source"] = file
            d.metadata["category"] = infer_category(file)

        docs.extend(loaded)

    return docs


def main() -> None:
    # Initialize Pinecone
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    index_name = os.getenv("PINECONE_INDEX_NAME")
    
    # Initialize Cohere embeddings
    print("Initializing Cohere embeddings...")
    embeddings = CohereEmbeddings(
        cohere_api_key=os.getenv("COHERE_API_KEY"),
        model=os.getenv("COHERE_MODEL", "embed-english-v3.0")     # 1024 dimensions, free tier
    )
    
    # Check if index exists
    existing_indexes = pc.list_indexes().names()
    
    if index_name in existing_indexes:
        print(f"Index '{index_name}' already exists.")
        index_info = pc.describe_index(index_name)
        
        # Check if dimension matches (Cohere embed-english-v3.0 = 1024)
        if index_info.dimension != 1024:
            print(f"⚠️ Index dimension mismatch. Deleting and recreating...")
            pc.delete_index(index_name)
            time.sleep(5)
            
            print(f"Creating index '{index_name}' with dimension 1024...")
            pc.create_index(
                name=index_name,
                dimension=1024,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1")
            )
            time.sleep(10)
        else:
            print("Dimension matches. Clearing existing data...")
            try:
                index = pc.Index(index_name)
                stats = index.describe_index_stats()
                if stats.get('total_vector_count', 0) > 0:
                    index.delete(delete_all=True)
                    time.sleep(5)
            except Exception as e:
                print(f"Note: {e}")
    else:
        print(f"Creating index '{index_name}'...")
        pc.create_index(
            name=index_name,
            dimension=1024,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1")
        )
        time.sleep(10)

    # Load and process documents
    documents = load_documents()
    print(f"Loaded {len(documents)} documents")

    if not documents:
        print("No documents found to ingest.")
        return

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=150,
        separators=["\n\n", "\n", ". ", " "],
    )

    chunks = splitter.split_documents(documents)
    print(f"Created {len(chunks)} chunks")

    # Process in batches
    BATCH_SIZE = 96  # Cohere free tier: 100 calls/min
    total_chunks = len(chunks)
    
    print(f"\nUploading {total_chunks} chunks to Pinecone...")
    
    vectorstore = None
    
    for i in range(0, total_chunks, BATCH_SIZE):
        batch_num = (i // BATCH_SIZE) + 1
        total_batches = (total_chunks + BATCH_SIZE - 1) // BATCH_SIZE
        
        end_idx = min(i + BATCH_SIZE, total_chunks)
        batch = chunks[i:end_idx]
        
        print(f"📦 Batch {batch_num}/{total_batches} ({len(batch)} chunks)...", end=" ", flush=True)
        
        try:
            if i == 0:
                vectorstore = PineconeVectorStore.from_documents(
                    documents=batch,
                    embedding=embeddings,
                    index_name=index_name
                )
            else:
                vectorstore.add_documents(batch)
            
            print("✅")
            
            # Wait between batches for rate limits (except last batch)
            if end_idx < total_chunks:
                print("⏳ Waiting 65s for rate limit...", end=" ", flush=True)
                time.sleep(65)
                print("✅")
                
        except Exception as e:
            print(f"\n❌ Error: {e}")
            print("⏳ Waiting 2 minutes...", end=" ", flush=True)
            time.sleep(120)
            print("retrying...", end=" ", flush=True)
            
            try:
                if i == 0:
                    vectorstore = PineconeVectorStore.from_documents(
                        documents=batch,
                        embedding=embeddings,
                        index_name=index_name
                    )
                else:
                    vectorstore.add_documents(batch)
                print("✅")
            except Exception as retry_error:
                print(f"\n❌ Retry failed: {retry_error}")
                print("⚠️ Skipping this batch...")

    print(f"\n🎉 Ingestion complete!")
    
    # Verify upload
    time.sleep(2)
    index = pc.Index(index_name)
    stats = index.describe_index_stats()
    print(f"📊 Index stats: {stats.get('total_vector_count', 0)} vectors stored")


if __name__ == "__main__":
    main()