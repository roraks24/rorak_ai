# Documents Directory

This directory is designated for PDF documents processed by the Rorak AI ingestion pipeline.

## 📖 How It Works

- **Cold Start Ingestion**: Any `.pdf` placed in this directory at application launch will be automatically ingested, split into chunks, and embedded into the local FAISS vector index.
- **Dynamic Uploads**: When documents are uploaded via the web UI or `POST /documents/upload`, they are validated, parsed, and embedded into the active index.
- **Privacy & Hygiene**: By default, `.gitignore` excludes `.pdf` files and `.faiss_index` caches to prevent accidental commitment of personal or sensitive data to version control.
