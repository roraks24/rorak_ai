from fastapi import FastAPI


app = FastAPI(
    title="Rorak",
    description="Rorak V1 - General LLM, Document RAG, and Web-Assisted AI Assistant",
    version="1.0.0"
)


@app.get("/")
def root():
    return {
        "name": "Rorak",
        "version": "1.0.0",
        "status": "running"
    }
