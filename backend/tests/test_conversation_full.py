import os
import sys
import asyncio
import json
from dotenv import load_dotenv

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.retriever import RAGRetriever
from core.generator import rag_generator

async def test_full_conversation():
    # Load environment variables
    load_dotenv()
    
    print("=" * 50)
    print("STARTING END-TO-END RAG CONVERSATION TEST")
    print("=" * 50)

    # 1. Define User Query
    # query = "How do I pay my accommodation fees?"
    # Using a query likely to have data if 'cafes' was the only thing indexed, 
    # but let's assume 'cafes.md' is indexed from previous context.
    # Or 'accommodation' related if available.
    # Let's use a query that matches the 'cafes.md' file we know exists/was used for testing:
    # "Where can I find cafes on campus?"
    query = "Where can I find cafes on campus?"
    
    print(f"\n[User]: {query}")

    # 2. Retrieval Phase
    print("\n" + "-" * 20 + " Phase 1: Retrieval " + "-" * 20)
    retriever = RAGRetriever()
    
    # Check if vector store has data
    from core.vector_store import vector_store
    count = vector_store.collection.count()
    print(f"Vector Store Document Count: {count}")
    
    if count == 0:
        print("WARNING: Vector store is empty. Retrieval will likely return nothing.")
        print("Please run ingest tests or offline_index.py first.")
    
    docs = await retriever.retrieve(query)
    
    print(f"\nRetrieved {len(docs)} documents after Reranking & Filtering.")
    
    for i, doc in enumerate(docs):
        title = doc['metadata'].get('title', 'No Title')
        source = doc['metadata'].get('url', 'No URL')
        score = doc.get('rerank_score', doc.get('score', 'N/A'))
        print(f"  [{i+1}] Title: {title}")
        print(f"      Source: {source}")
        print(f"      Score: {score}")
        print(f"      Preview: {doc['content'][:100].replace(chr(10), ' ')}...")

    # 3. Generation Phase
    print("\n" + "-" * 20 + " Phase 2: Generation " + "-" * 20)
    
    full_answer = ""
    sources_data = []

    print("[Assistant]: ", end="", flush=True)
    
    async for chunk in rag_generator.generate_stream(query, docs):
        # Check for Sources block
        if chunk.startswith("__SOURCES__:"):
            json_part = chunk.split("__SOURCES__:", 1)[1].strip()
            try:
                sources_data = json.loads(json_part)
                # Don't print sources JSON to user stream, but store for debug
            except json.JSONDecodeError:
                print(f"\n[Error parsing sources]: {chunk}")
        else:
            # Print answer stream
            print(chunk, end="", flush=True)
            full_answer += chunk

    print("\n")
    
    # 4. Validation & Summary
    print("\n" + "-" * 20 + " Phase 3: Summary " + "-" * 20)
    
    # Check Sources
    if sources_data:
        print(f"Sources returned to frontend ({len(sources_data)}):")
        for s in sources_data:
            print(f"  - ID: {s['id']}, Content Preview: {s['content'][:50]}...")
    else:
        print("No __SOURCES__ block received.")

    # Check Answer
    if len(full_answer) > 0:
        print(f"Generated Answer Length: {len(full_answer)} chars")
    else:
        print("No answer generated.")

    print("\n" + "=" * 50)
    print("TEST COMPLETE")
    print("=" * 50)

if __name__ == "__main__":
    # Fix for Windows Event Loop Policy
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(test_full_conversation())
