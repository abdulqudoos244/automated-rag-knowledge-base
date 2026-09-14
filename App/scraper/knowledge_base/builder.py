import json
import os


# -------------------------
# Build documents from products
# -------------------------

def build_documents(products):

    documents = []

    for product in products:

        document = f"""
Product Name: {product.get("name", "")}

Current Price: Rs. {product.get("price", "")}

Lowest Recorded Price: Rs. {product.get("price_low", "")}

Highest Recorded Price: Rs. {product.get("price_high", "")}

Description:
{product.get("description", "")}

Specifications:
"""

        specifications = product.get("specifications", {}) or {}

        for key, value in specifications.items():
            document += f"- {key}: {value}\n"

        document += f"""
Product URL:
{product.get("url", "")}
"""

        documents.append(document.strip())

    return documents


# -------------------------
# Run as a script
# -------------------------

if __name__ == "__main__":

    input_file = "data/products.json"

    with open(input_file, "r", encoding="utf-8") as file:
        products = json.load(file)

    documents = build_documents(products)

    os.makedirs("data", exist_ok=True)

    output_file = "data/knowledge_base.json"

    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(documents, file, indent=4, ensure_ascii=False)

    print("Knowledge Base created successfully!")
    print(f"Documents created: {len(documents)}")
    print(f"Saved to: {output_file}")







