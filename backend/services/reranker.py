from sentence_transformers import CrossEncoder

from backend.core.config import RERANKER_MODEL


reranker = CrossEncoder(RERANKER_MODEL)


def rerank_func(documents, query, top_k=3):

    pairs = [
        (query, document.page_content)
        for document in documents
    ]

    scores = reranker.predict(pairs)

    ranked_documents = sorted(
        zip(documents, scores),
        key=lambda x: x[1],
        reverse=True
    )

    return [
        {
            "document": document,
            "score": float(score)
        }
        for document, score in ranked_documents[:top_k]
    ]