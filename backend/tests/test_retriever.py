import asyncio
import sys
import os
import json

# Add backend directory to sys.path so 'core' module can be imported
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.retriever import rag_retriever

async def main():
    query = "exam schedule"
    print(f"Running test retrieval for query: '{query}'")
    
    results = await rag_retriever.retrieve(query)
    
    print("\nResults found:", len(results))
    for i, doc in enumerate(results):
        print(f"\n[{i+1}] Score: {doc.get('score')} | Rerank Score: {doc.get('rerank_score')}")
        print(f"Title: {doc['metadata'].get('title')}")
        print(f"Content Preview: {doc['content'][:100]}...")

if __name__ == "__main__":
    asyncio.run(main())
