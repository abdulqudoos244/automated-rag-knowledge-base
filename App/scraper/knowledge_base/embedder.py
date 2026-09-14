import json

from sentence_transformers import SentenceTransformer


# -------------------------
# Load chunks
# -------------------------

input_file = "data/chunks.json"

with open(input_file, "r", encoding="utf-8") as file:
    chunks = json.load(file)


# -------------------------
# Load embedding model
# -------------------------

print("Loading embedding model...")

model = SentenceTransformer("all-MiniLM-L6-v2")


# -------------------------
# Generate embeddings
# -------------------------

print("Generating embeddings...")

embeddings = model.encode(chunks)


# -------------------------
# Prepare data
# -------------------------

embedding_data = []

for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):

    embedding_data.append({
        "id": i,
        "text": chunk,
        "embedding": embedding.tolist()
    })


# -------------------------
# Save embeddings
# -------------------------

output_file = "data/embeddings.json"

with open(output_file, "w", encoding="utf-8") as file:
    json.dump(
        embedding_data,
        file,
        indent=2,
        ensure_ascii=False
    )


# -------------------------
# Result
# -------------------------

print("\nEmbeddings created successfully!")
print(f"Chunks processed: {len(chunks)}")
print(f"Embedding size: {len(embeddings[0])}")
print(f"Saved to: {output_file}")