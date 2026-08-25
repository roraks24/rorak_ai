from backend.rag.prompts import prompt_func
from backend.services.reranker import rerank_func
from backend.services.retriever import retriev_func, context_func
from backend.core.config import GROQ_API_KEY, GROQ_MODEL, RERANK_TOP_K
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

client = Groq(api_key=GROQ_API_KEY)

def chat_func(query):

    results = retriev_func(query)

    reranked_result = rerank_func(
        results,
        query,
        top_k= RERANK_TOP_K
    )

    reranked_documents = [
        item["document"]
        for item in reranked_result
    ]

    context = context_func(reranked_documents)

    prompt = prompt_func(query, context)


    response = client.chat.completions.create(
        model= GROQ_MODEL,
        temperature=0,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    answer = response.choices[0].message.content

    return answer










