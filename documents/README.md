# documents/

Runtime storage for uploaded files and the local FAISS index. Everything in this directory except this README and `.gitkeep` is ignored by git and excluded from Docker images.

```text
documents/
├── <document_id>/original/<filename>   # original uploaded file
└── .faiss_index/                        # persisted vector index
```

Files are written here by `POST /documents/upload` and removed by `DELETE /documents/{id}`. In Docker Compose this directory is a named volume. Do not place files here manually — use the API or the web client.
