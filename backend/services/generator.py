import logging
import time
from typing import Optional

from groq import Groq

from backend.core.config import GROQ_API_KEY, GROQ_MODEL, RERANK_TOP_K
from backend.rag.prompts import prompt_func, general_prompt_func
from backend.services.reranker import rerank_func
from backend.services.retriever import retriev_func, context_func


logger = logging.getLogger(__name__)

# Fallback response for ungrounded queries
NO_CONTEXT_FALLBACK_ANSWER = "I couldn't find this information in the uploaded document."

# Initialize Groq client
client: Optional[Groq] = None
if GROQ_API_KEY:
    client = Groq(api_key=GROQ_API_KEY)
else:
    logger.warning("Groq client not initialized (GROQ_API_KEY is missing).")


def _call_groq_completion(prompt: str) -> Optional[str]:
    """Execute chat completion call to Groq API."""
    if client is None:
        raise RuntimeError("GROQ_API_KEY is not configured.")

    t0 = time.perf_counter()
    logger.info("Calling Groq API (model: %s)...", GROQ_MODEL)

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        temperature=0.2,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    duration_ms = (time.perf_counter() - t0) * 1000
    logger.info("Groq API call completed in %.2f ms", duration_ms)

    if not response.choices or not response.choices[0].message:
        return None

    return response.choices[0].message.content


def chat_func(query: str) -> str:
    """
    Execute AI generation:
    1. If document context is available in vector store, retrieve and rerank for grounded answering.
    2. If no documents exist, respond helpfully as general AI knowledge assistant (greetings, explanations, questions).
    3. Call Groq LLM with retry on empty response.
    """
    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not configured. Chat generation is unavailable."
        )

    t_total_start = time.perf_counter()

    # Step 1: Retrieval
    t0 = time.perf_counter()
    try:
        results = retriev_func(query)
    except Exception:
        logger.exception("Retrieval failed for query: %.60s", query)
        results = []
    t_retrieval_ms = (time.perf_counter() - t0) * 1000

    # Step 2: Prompt selection (Grounded vs General)
    if results:
        # Grounded RAG mode
        t0 = time.perf_counter()
        try:
            reranked_results = rerank_func(
                results,
                query,
                top_k=RERANK_TOP_K
            )
            reranked_documents = [item["document"] for item in reranked_results]
            context = context_func(reranked_documents)
        except Exception:
            logger.exception("Reranking failed. Falling back to raw retrieval results.")
            reranked_documents = results[:RERANK_TOP_K]
            context = context_func(reranked_documents)
        t_rerank_ms = (time.perf_counter() - t0) * 1000

        if context and context.strip():
            prompt = prompt_func(query, context)
        else:
            prompt = general_prompt_func(query)
    else:
        # General Assistant mode (no document uploaded / vector store empty)
        t_rerank_ms = 0.0
        prompt = general_prompt_func(query)

    # Step 3: LLM Generation with 1 retry on empty response
    answer = None
    try:
        raw_answer = _call_groq_completion(prompt)
        if raw_answer and raw_answer.strip():
            answer = raw_answer.strip()
        else:
            logger.warning("LLM returned empty content on first attempt. Retrying once...")
            time.sleep(0.5)
            retry_raw = _call_groq_completion(prompt)
            if retry_raw and retry_raw.strip():
                answer = retry_raw.strip()
                logger.info("LLM retry succeeded with valid content.")
            else:
                logger.error("LLM returned empty content after retry.")
                raise RuntimeError("LLM returned an empty response. Please try again.")

    except Exception as e:
        if isinstance(e, RuntimeError):
            raise
        logger.exception("Groq API request failed.")
        raise RuntimeError("Failed to generate response from AI provider. Please try again.")

    total_duration_ms = (time.perf_counter() - t_total_start) * 1000
    logger.info(
        "Chat request completed in %.2f ms (Retrieval: %.2f ms, Rerank: %.2f ms, Total: %.2f ms)",
        total_duration_ms, t_retrieval_ms, t_rerank_ms, total_duration_ms
    )

    return answer
