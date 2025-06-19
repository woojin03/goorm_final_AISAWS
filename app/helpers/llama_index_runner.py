# app/helpers/llama_index_runner.py

import json
from typing import Union
from llama_index.core import VectorStoreIndex, Document
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.ollama import Ollama
from llama_index.core.settings import Settings

# ✅ 전역 설정
Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")

#deepseek-coder:6.7b
#gemma3:4b
custom_llm = Ollama(
    model="gemma3:4b",
    base_url="http://localhost:11434",
    request_timeout=600
)
Settings.llm = custom_llm

def run_llama_index_analysis(log_texts: list[Union[str, dict]], prompt: str) -> str:
    docs = [
        Document(text=json.dumps(log, ensure_ascii=False, indent=2)) if isinstance(log, dict)
        else Document(text=log)
        for log in log_texts
    ]

    index = VectorStoreIndex.from_documents(docs)
    query_engine = index.as_query_engine(response_mode="compact", llm=custom_llm)
    response = query_engine.query(prompt)

    return str(response).strip()
