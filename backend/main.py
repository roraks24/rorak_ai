from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routes import chat, documents, health


app = FastAPI(
    title="Rorak",
    description="rorak.ai v1 - General LLM and Document RAG Assistant",
    version="1.0.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "name": "Rorak",
        "version": "1.0.0",
        "status": "running"
    }


app.include_router(chat.router)
app.include_router(documents.router)
app.include_router(health.router)