def prompt_func(query, context):

    prompt = f""" # There are some rules you have to follow before answering: 
    
    Rule 1: Always see the context before going on the web search and then answer. Basically the flow should be like first
    search in the context then if you dont find the answer and you think that you can find it on web than answer from the web.
     
    Rule 2: If the think that the answer of query is something you can find on the web then go for it answer.
    
    Rule 3: Do not infer, assume, or add any information that is not stated in the context.
    first check the context and then if you dont find the answer, simply say that  "I can't answer based on the provided context.
    
    Rule 4: If you answered from the web. clearly mention that the source of this result is from web search.
    
    #Below the query and context both are provided.
    
    Query: {query}
    Context: {context}

    """

    return prompt
