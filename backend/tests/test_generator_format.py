"""
test_generator_format.py - RAG Generator Output Format Test

This script validates the output format of the RAG generator:
- Verifies that the first chunk contains __SOURCES__ JSON prefix
- Tests streaming response format and structure
- Validates citation metadata parsing

Run with:
    python test_generator_format.py
"""

import sys
import os
import asyncio
import json

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 修复 Windows 下 asyncio 事件循环关闭的报错问题
if sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from core.generator import rag_generator

async def test_generator_stream():
    # Mock docs
    docs = [
        {"content": "Content 1", "metadata": {"title": "Title 1", "url": "url1"}, "date": "2023-01-01", "score": 0.9, "rerank_score": 1.0},
        {"content": "Content 2", "metadata": {"title": "Title 2", "url": "url2"}, "date": "2023-01-02", "score": 0.8, "rerank_score": 0.9},
        {"content": "Content 3", "metadata": {"title": "Title 3", "url": "url3"}, "date": "2023-01-03", "score": 0.7, "rerank_score": 0.8},
        {"content": "Content 4", "metadata": {"title": "Title 4", "url": "url4"}, "date": "2023-01-04", "score": 0.6, "rerank_score": 0.7},
    ]
    
    print("Testing generate_stream...")
    first_chunk = True
    async for chunk in rag_generator.generate_stream("test query", docs):
        if first_chunk:
            print(f"First chunk: {chunk!r}")
            if chunk.startswith("__SOURCES__:"):
                json_part = chunk.split("__SOURCES__:", 1)[1].strip()
                try:
                    data = json.loads(json_part)
                    print(f"Successfully parsed sources JSON. Count: {len(data)}")
                    print(f"First source id: {data[0]['id']}")
                except json.JSONDecodeError as e:
                    print(f"JSON Parse Error: {e}")
            else:
                print("Error: First chunk does not start with __SOURCES__:")
            first_chunk = False
        else:
            # print(f"Chunk: {chunk}")
            pass
            
if __name__ == "__main__":
    asyncio.run(test_generator_stream())
