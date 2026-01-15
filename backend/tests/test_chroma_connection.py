import os
import sys
import time
from dotenv import load_dotenv

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.vector_store import vector_store

def test_chroma_connection():
    load_dotenv()
    
    print("-" * 30)
    print("Testing ChromaDB Connection and Vector Search...")
    print("-" * 30)
    
    if not vector_store.client:
        print("ERROR: Vector Store is initialized in Mock mode. Cannot test ChromaDB.")
        return

    # 0. 重置 Collection 以确保使用新的 cosine 距离度量 (仅测试用)
    try:
        vector_store.client.delete_collection(vector_store.collection_name)
        print(f"Deleted existing collection '{vector_store.collection_name}' to apply new settings.")
        # 重新初始化
        vector_store._ensure_collection()
    except Exception:
        pass # 如果不存在则忽略

    # 1. 准备测试数据
    test_chunks = [
        {
            "content": "It is a normal part of life that you may have a complaint.  We view complaints positively as they help us learn how to do things better. You will not be treated differently in any part of your university life if you make a complaint.",
            "metadata": {"title": "Campus Life", "url": "https://bristol.ac.uk/campus", "date": "2023-10-01"}
        },
        {
            "content": "Find something to eat or drink on campus. Visit one of our Source cafés and bars for locally-sourced and sustainable food and drink. Source is our in-house catering brand and we care about the food we produce and we care about you, our customers. Pop along to your nearest Source to share our passion for excellent food.",
            "metadata": {"title": "Accommodation", "url": "https://bristol.ac.uk/accommodation", "date": "2023-10-02"}
        }
    ]

    print(f"\n1. Adding {len(test_chunks)} test documents...")
    try:
        # 使用 batch_size=1 测试分批处理逻辑
        ids = vector_store.add_documents(test_chunks)
        print(f"   Successfully added documents. IDs: {ids}")
    except Exception as e:
        print(f"   ERROR adding documents: {e}")
        return

    # 2. 测试检索
    query = "complaint and angry"
    print(f"\n2. Searching for: '{query}'")
    print("   (Note: Score is Cosine Similarity, range [-1, 1]. Higher is better.)")
    
    try:
        # search returns a list of hits
        hits = vector_store.search(query, limit=2)
        
        if not hits:
            print("   No results returned (empty list).")
        else:
            print(f"   Found {len(hits)} results:")
            for i, hit in enumerate(hits):
                score = hit['score']
                distance = 1 - score
                content = hit['content']
                print(f"\n   --- Result [{i+1}] ---")
                print(f"   Score (Similarity): {score:.4f}")
                print(f"   Distance (Cosine):  {distance:.4f}")
                print(f"   Metadata: {hit['metadata']}")
                print(f"   Content: {content}")
                
            # 动态验证
            expected_keyword = "complaint"
            found = any(expected_keyword in hit['content'].lower() for hit in hits)
            
            if found:
                print(f"\n   SUCCESS: Found expected keyword '{expected_keyword}' in top results.")
            else:
                print(f"\n   WARNING: Did not find expected keyword '{expected_keyword}' in top results.")

    except Exception as e:
        print(f"   ERROR during search: {e}")
        return

    print("\n" + "-" * 30)
    print("ChromaDB Test Completed.")
    print("-" * 30)

if __name__ == "__main__":
    test_chroma_connection()
