from langchain_core.prompts import PromptTemplate
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_community.document_loaders import JSONLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.chains import RetrievalQA
from langchain_openai import ChatOpenAI
import os
from dotenv import load_dotenv

# Config 
load_dotenv()

JSON_PATH = "../shared_data/biedronka_offers.json"

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
You are a smart shopping assistant. Use the following offer information to answer the question.

{context}

Question: {question}
Answer:"""
)

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
retriever = vectorstore.as_retriever()
qa_chain = RetrievalQA.from_chain_type(llm=llm, retriever=retriever, chain_type_kwargs={"prompt": prompt})

# Ask a question 
question = "What is the best deal?"
answer = qa_chain.invoke({"query": question})
print("Answer:", answer["result"])
