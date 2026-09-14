import json
import os


# -------------------------
# Chunk documents
# -------------------------

def chunk_documents(documents, chunk_size=500):

    chunks = []

    for product_index, document in enumerate(documents):

        words = document.split()

        for i in range(0, len(words), chunk_size):

            chunk_words = words[i:i + chunk_size]
            chunk = " ".join(chunk_words)

            if chunk.strip():
                chunks.append({
                    "text": chunk,
                    "product_index": product_index
                })

    return chunks


# -------------------------
# Run as a script
# -------------------------

if __name__ == "__main__":

    input_file = "data/knowledge_base.json"

    with open(input_file, "r", encoding="utf-8") as file:
        documents = json.load(file)

    chunks = chunk_documents(documents, chunk_size=500)

    os.makedirs("data", exist_ok=True)

    output_file = "data/chunks.json"

    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(chunks, file, indent=4, ensure_ascii=False)

    print("Chunking completed successfully!")
    print(f"Documents processed: {len(documents)}")
    print(f"Chunks created: {len(chunks)}")
    print(f"Saved to: {output_file}")