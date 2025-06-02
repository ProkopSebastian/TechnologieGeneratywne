from langchain_core.prompts import PromptTemplate
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_community.document_loaders import JSONLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.chains import RetrievalQA
from langchain_openai import ChatOpenAI
import os
from dotenv import load_dotenv
import json
from logger import get_logger

# Config 
load_dotenv()

JSON_PATH = "shared_data/biedronka_offers.json"

# Load and preprocess
loader = JSONLoader(
    file_path=JSON_PATH,
    jq_schema='.[]',  # adjust depending on structure
    text_content=False
)
raw_docs = loader.load()

# Flatten and stringify JSON if needed
for doc in raw_docs:
    doc.page_content = str(doc.metadata) + " " + str(doc.page_content)

# Split into chunks 
splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
docs = splitter.split_documents(raw_docs)

# Embed and index 
embedding = OpenAIEmbeddings()
vectorstore = FAISS.from_documents(docs, embedding)

# Prompt and QA chain 
prompt = PromptTemplate(
    input_variables=["context", "question"],
    template="""
You are a JSON API generator that creates a meal plan using only the products listed below.

Respond only with a raw JSON object matching this exact structure:

{{
  "meal": [
    {{
      "day": 1,
      "name": "Meal Name",
      "content": "Short description of the dish.",
      "preparation": "Step-by-step preparation instructions.",
      "protein": 0,
      "carbohydrates": 0,
      "fats": 0,
      "ingredients": [
        {{
          "name": "Product name from list",
          "quantity": "e.g. 100g",
          "description": "Short product description",
          "price": 0.00
        }}
      ]
    }}
  ],
  "shopping_list": [
    {{
      "name": "Product name from list",
      "quantity": "Total quantity across meals",
      "description": "Short product description",
      "price": 0.00
    }}
  ],
  "status": "success"
}}

Rules:
- Include exactly 3 meals (breakfast, lunch, dinner)
- Set "day": 1 for all meals
- Use only products from the list below
- All numerical fields (protein, carbohydrates, fats, price) must be numbers (not strings)
- Ensure no duplicated entries in "shopping_list"
- Do not wrap the output in markdown or quotes. Respond only with pure JSON text.

Here are the available products:

{context}

Question: {question}
"""
)

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
retriever = vectorstore.as_retriever()
qa_chain = RetrievalQA.from_chain_type(llm=llm, retriever=retriever, chain_type_kwargs={"prompt": prompt})

rag_logger = get_logger("app-rag")

# Ask a question 
def ask_rag(question: str) -> dict:
    rag_logger.info(f'Rag question: {question}')
    response = qa_chain.invoke({"query": question})
    rag_logger.info(f'Rag Response: {response["result"]}')
    
    try:
        return json.loads(response["result"])
    except json.JSONDecodeError:
        return {"status": "error", "message": "Could not parse JSON response", "raw": response["result"]}