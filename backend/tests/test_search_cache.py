import sys
import os
import time
import subprocess
import requests
import json
import random
import string

# Path to python executable
PYTHON_EXE = sys.executable
# Path to app.py
APP_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'app.py'))

def start_server():
    print(f"Starting server: {PYTHON_EXE} {APP_PATH}")
    process = subprocess.Popen(
        [PYTHON_EXE, APP_PATH],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.path.dirname(os.path.dirname(APP_PATH))
    )
    return process

def wait_for_server(url, timeout=30):
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            requests.get(url)
            return True
        except requests.exceptions.ConnectionError:
            time.sleep(1)
    return False

def generate_random_query():
    return "".join(random.choices(string.ascii_letters, k=10))

def test_search_cache():
    base_url = "http://localhost:8000"
    search_url = f"{base_url}/api/search"
    
    query = "Cache Test " + generate_random_query()
    print(f"\nQuery: {query}")
    
    # 1. First Request (Cache Miss)
    t0 = time.time()
    resp1 = requests.post(search_url, json={"query": query})
    t1 = time.time()
    
    if resp1.status_code != 200:
        print(f"First request failed: {resp1.text}")
        return
        
    duration1 = t1 - t0
    print(f"First Request Duration: {duration1:.4f}s")
    results1 = resp1.json().get("results", [])
    print(f"Results Count: {len(results1)}")
    
    # 2. Second Request (Cache Hit expected)
    t2 = time.time()
    resp2 = requests.post(search_url, json={"query": query})
    t3 = time.time()
    
    if resp2.status_code != 200:
        print(f"Second request failed: {resp2.text}")
        return
        
    duration2 = t3 - t2
    print(f"Second Request Duration: {duration2:.4f}s")
    results2 = resp2.json().get("results", [])
    
    # Verify results identity
    # Note: RAG retrieval might be non-deterministic if not cached, 
    # but if cached, it should be exactly identical.
    # However, JSON serialization might change order if not careful, but usually dicts preserve order in recent Python.
    
    # Compare result IDs
    ids1 = [r.get("id") for r in results1]
    ids2 = [r.get("id") for r in results2]
    
    if ids1 == ids2:
        print("SUCCESS: Results match.")
    else:
        print("FAIL: Results do not match.")
        print(f"IDs 1: {ids1}")
        print(f"IDs 2: {ids2}")

    # Verify speedup (only if first request took significant time, e.g. > 0.1s)
    # If DB is empty, retrieval is fast, so cache overhead might make it slower or equal.
    # But usually Redis is faster than Embedding + Vector Search + Rerank.
    if duration1 > 0.2:
        if duration2 < duration1 * 0.5:
            print("SUCCESS: Significant speedup detected.")
        else:
            print("WARNING: No significant speedup. (Maybe Redis overhead or fast retrieval)")
    else:
        print("INFO: First request was too fast to measure speedup reliably.")

if __name__ == "__main__":
    server_process = None
    try:
        try:
            requests.get("http://localhost:8000/docs")
            print("Server already running.")
        except:
            server_process = start_server()
            if not wait_for_server("http://localhost:8000/docs"):
                print("Failed to start server.")
                sys.exit(1)
                
        test_search_cache()
        
    finally:
        if server_process:
            print("Stopping server...")
            server_process.kill()
