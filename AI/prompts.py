from langchain.prompts import PromptTemplate

search_query_prompt = PromptTemplate(
    input_variables=["user_request"],
    template=(
        "Rewrite the following user request as a short, effective recipe search query (3–6 words):\n"
        "User request: {user_request}\n"
        "Search query:"
    )
)