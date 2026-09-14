import json
import os

from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS


# -------------------------
# Load chunks
# -------------------------

with open("data/chunks.json", "r", encoding="utf-8") as file:
    chunks = json.load(file)


# -------------------------
# Convert chunks to Documents
# -------------------------

documents = []

for i, chunk in enumerate(chunks):

    document = Document(
        page_content=chunk["text"],
        metadata={
            "chunk_id": i,
            "product_index": chunk["product_index"],   # <-- asli product ka index, ab reliable hai
            "source": "AYS Online"
        }
    )

    documents.append(document)


# -------------------------
# Load embedding model
# -------------------------

print("Loading embedding model...")

embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)


# -------------------------
# Create FAISS vector store
# -------------------------

print("Creating FAISS vector store...")

vector_store = FAISS.from_documents(
    documents,
    embeddings
)


# -------------------------
# Save vector store
# -------------------------

os.makedirs("data/faiss_index", exist_ok=True)

vector_store.save_local("data/faiss_index")


print("\nVector store created successfully!")
print(f"Documents stored: {len(documents)}")
print("Saved to: data/faiss_index")