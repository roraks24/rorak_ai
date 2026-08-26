from backend.rag import vector_store as vector_store_module
from backend.core.config import RETRIEVAL_K


def retriev_func(query):

    if vector_store_module.vector_store is None:
        return []

    retriever = vector_store_module.vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={
            "k": RETRIEVAL_K
        }
    )

    results = retriever.invoke(query)

    return results


def context_func(results):

    context = []

    for i, document in enumerate(results, start=1):

        context.append(
            f"""---Chunk {i}---

Source: {document.metadata.get("source", "Unknown")}
Page: {document.metadata.get("page_label", "Unknown")}
Content: {document.page_content}"""
        )

    return "\n\n".join(context)