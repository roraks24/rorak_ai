import logging

from groq import Groq

from backend.core.config import GROQ_API_KEY, GROQ_MODEL, RERANK_TOP_K
from backend.rag.prompts import prompt_func
from backend.services.reranker import rerank_func
from backend.services.retriever import retriev_func, context_func


logger = logging.getLogger(__name__)

client = Groq(api_key=GROQ_API_KEY)


def chat_func(query):

    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not configured. "
            "Chat is unavailable."
        )

    # Retrieve relevant documents
    try:
        results = retriev_func(query)
    except Exception:
        logger.exception("Retrieval failed for query: %s", query[:100])
        results = []

    # If no documents found, skip reranking and use empty context
    if not results:
        logger.info("No documents retrieved. Using general knowledge.")
        context = ""
    else:
        try:
            reranked_result = rerank_func(
                results,
                query,
                top_k=RERANK_TOP_K
            )

            reranked_documents = [
                item["document"]
                for item in reranked_result
            ]

            context = context_func(reranked_documents)
        except Exception:
            logger.exception("Reranking failed. Using raw retrieval results.")
            context = context_func(results)

    prompt = prompt_func(query, context)

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            temperature=0,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        answer = response.choices[0].message.content

        if not answer:
            logger.warning("LLM returned empty content.")
            answer = "I'm sorry, I couldn't generate a response. Please try again."

        return answer

    except Exception as e:
        logger.exception("Groq API call failed.")
        raise RuntimeError(
            f"Failed to generate response: {str(e)}"
        )
