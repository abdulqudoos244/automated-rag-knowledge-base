# Automated RAG Knowledge Base

A Retrieval-Augmented Generation (RAG) system that scrapes an e-commerce product catalog, builds a searchable knowledge base, and answers natural-language questions about products (price, specifications, features, comparisons) through a FastAPI service.

Built as an end-to-end pipeline: **scrape → parse → chunk → embed → retrieve → generate**.

## Features

- 🕷️ **Web crawler** — discovers and collects product URLs from a live e-commerce site
- 📄 **Structured parser** — extracts product name, price, price history, description, and specifications from raw HTML
- 🧩 **Hybrid retrieval** — fast rule-based keyword/attribute matching (brand, model, capacity, etc.) with a FAISS semantic-search fallback for open-ended queries
- 🤖 **Answer generation** — deterministic answers (no LLM, zero hallucination risk) for structured questions, product comparisons, and any confidently-identified product; a local LLM (via Ollama) is used only for genuinely open-ended, fuzzy queries where no exact product match exists
- 🚀 **FastAPI service** — a simple `/ask` endpoint for question answering
- ✅ **114 automated tests** (pytest) covering retrieval logic, answer generation, chunking, document building, and HTML parsing

## Architecture

```
crawler.py   → discovers product URLs
    │
    ▼
parser.py    → scrapes each product page (name, price, specs, description)
    │
    ▼
builder.py   → formats each product into a text document
    │
    ▼
chunker.py   → splits long documents into fixed-size chunks (tracks product_index)
    │
    ▼
vector_store.py → embeds chunks and builds a FAISS index
    │
    ▼
retriever.py → given a question, finds the most relevant product(s)
    │           (rule-based matching first, FAISS semantic search as fallback)
    ▼
generator.py → formats an answer (regex extraction for structured questions,
    │           LLM for open-ended ones)
    ▼
main.py      → FastAPI app exposing POST /ask (at App/scraper/api/main.py)
```

## Tech Stack

- **Python 3.11+**
- **BeautifulSoup4** — HTML parsing
- **LangChain + FAISS** — vector storage and semantic search
- **sentence-transformers** (`all-MiniLM-L6-v2`) — embeddings
- **Ollama** (`qwen2.5:1.5b-instruct`) — local LLM for open-ended answers
- **FastAPI** — API layer
- **pytest** — testing

## Project Structure

```
automated-rag-knowledge-base/
├── App/
│   └── scraper/
│       ├── crawler.py
│       ├── parser.py
│       ├── pipeline.py
│       ├── api/
│       │   └── main.py
│       └── knowledge_base/
│           ├── builder.py
│           ├── chunker.py
│           ├── vector_store.py
│           ├── retriever.py
│           └── generator.py
├── tests/
│   ├── test_builder.py
│   ├── test_chunker.py
│   ├── test_parser.py
│   ├── test_retriever.py
│   └── test_generator.py
├── .github/
│   └── workflows/
│       ├── tests.yml
│       └── update-knowledge-base.yml
├── streamlit_app.py
├── requirements.txt
└── README.md
```

## Setup

1. **Clone the repo and create a virtual environment**

   ```bash
   git clone https://github.com/abdulqudoos244/automated-rag-knowledge-base.git
   cd automated-rag-knowledge-base
   python -m venv venv
   venv\Scripts\activate      # Windows
   source venv/bin/activate   # macOS/Linux
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Install and run Ollama** (for open-ended question answering)

   ```bash
   ollama pull qwen2.5:1.5b-instruct
   ```

## Automation

The knowledge base is **not** built manually. A scheduled GitHub Actions workflow (`.github/workflows/update-knowledge-base.yml`) runs the full pipeline (crawl → parse → build → chunk → embed) **every Monday** and commits the refreshed data — including the rebuilt FAISS index — straight back to the repository. No human runs the scraper, and no manual step is needed after a refresh.

- `data/products.json`, `data/knowledge_base.json`, `data/chunks.json`, `data/product_urls.json`, and `data/faiss_index/` are all version-controlled, so every automated refresh shows up as a commit ("Automated weekly knowledge base refresh") with a real diff of what changed on the store.
- The pipeline is incremental: `parser.py` skips products it has already scraped, so only genuinely new products are fetched on each run — the first run is the slow one, every run after that is fast.
- You can also trigger a refresh on demand from the **Actions** tab (`workflow_dispatch`) instead of waiting for the weekly schedule — useful for demos.
- After pulling the latest commit, the API/Streamlit app can be started immediately — the committed FAISS index is already in sync with the latest data.

## Usage

### 1. Build the knowledge base

Run the pipeline in order (each step reads the previous step's output from `data/`):

```bash
python App/scraper/crawler.py
python App/scraper/parser.py
python App/scraper/knowledge_base/builder.py
python App/scraper/knowledge_base/chunker.py
python App/scraper/knowledge_base/vector_store.py
```

### 2. Ask questions from the command line

```bash
python App/scraper/knowledge_base/generator.py
```

### 3. Or run the API

```bash
uvicorn App.scraper.api.main:app --reload
```

Then send a request:

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the price of the Haier HSU-18HFPAB?"}'
```

## Testing

```bash
pytest tests/ -v
```

All 114 tests run against mocked data — no live network calls, no FAISS index, and no LLM required. They're safe to run anytime.

## Known Limitations

- The retriever prioritizes rule-based keyword matching over semantic search; FAISS is only used as a fallback when no keyword match is found.
- The crawler and parser are tailored to one site's HTML structure (WooCommerce-based) and would need selector updates for other sites.
- `qwen2.5:1.5b-instruct` is a small local model chosen for free inference — answer quality for genuinely open-ended questions (no exact product match) is limited compared to larger models.
- **No price-range or superlative queries.** Phrases like "under 100000", "cheapest", or "most expensive" are not parsed as constraints — the system falls through to a generic keyword/LLM search instead, which can produce an irrelevant or unverified answer rather than an explicit "not supported" message. Supporting this would require adding numeric range parsing and price-based sorting to the retriever.
- **No capacity range queries.** A query like "washing machines between 8 and 10 kg" only picks up the number immediately adjacent to the unit (10 kg), silently ignoring the "between X and Y" range and the lower bound.

## Future Improvements

- [ ] Add price-range ("under X", "between X and Y") and superlative ("cheapest", "most expensive") query support
- [ ] Support capacity range queries (e.g. "8 to 10 kg") instead of a single exact value
- [ ] Add a re-ranking step to blend keyword and semantic search scores
- [ ] Swap `langchain-community`'s FAISS integration for the standalone `langchain-faiss` package
- [ ] Add caching for repeated queries
- [ ] Containerize with Docker for easier deployment

## Author

**Abdul Qudoos**
GitHub: [abdulqudoos244](https://github.com/abdulqudoos244)
LinkedIn: [abdul-qudoos](https://www.linkedin.com/in/abdul-qudoos-b680b133a/)