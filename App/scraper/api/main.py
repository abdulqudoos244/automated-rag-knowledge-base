from fastapi import FastAPI
from pydantic import BaseModel

from App.scraper.knowledge_base.generator import generate_answer

# -------------------------
# Create FastAPI App
# -------------------------

app = FastAPI(
    title="Automated RAG Knowledge Base API",
    description="Product question answering API using RAG",
    version="1.0.0"
)


# -------------------------
# Request Model
# -------------------------

class QuestionRequest(BaseModel):
    question: str


# -------------------------
# Root Endpoint
# -------------------------

@app.get("/")
def home():
    return {
        "message": "RAG API is running successfully!"
    }


# -------------------------
# Ask Endpoint
# -------------------------

@app.post("/ask")
def ask_question(request: QuestionRequest):

    question = request.question.strip()

    if not question:
        return {
            "answer": "Please enter a question."
        }

    answer = generate_answer(question)

    return {
        "question": question,
        "answer": answer
    }