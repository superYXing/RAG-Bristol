"""
test_summarize_api.py - Summarization API Endpoint Test

This script tests the /api/summarize endpoint which generates
LLM-powered summaries from retrieved documents:
- Starts the FastAPI server automatically
- Sends mock documents to the summarize endpoint
- Validates streaming response format and content
- Tests error handling for malformed requests

Run with:
    python test_summarize_api.py
"""

import sys
import os
import time
import subprocess
import requests
import json
import signal

# Path to python executable
PYTHON_EXE = sys.executable
# Path to app.py
APP_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'app.py'))

def start_server():
    print(f"Starting server: {PYTHON_EXE} {APP_PATH}")
    # Start the server in a subprocess
    process = subprocess.Popen(
        [PYTHON_EXE, APP_PATH],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.path.dirname(os.path.dirname(APP_PATH)) # Run from project root
    )
    return process

def wait_for_server(url, timeout=30):
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            requests.get(url)
            # If we get a response (even 404), the server is up
            return True
        except requests.exceptions.ConnectionError:
            time.sleep(1)
    return False

def test_summarize_endpoint():
    base_url = "http://localhost:8000"
    summarize_url = f"{base_url}/api/summarize"
    
    # Wait for server to be ready (api/search or just root)
    # Since we don't have a root endpoint defined in snippet, maybe try /docs or assume up if connectable
    
    print("\n[Test] Normal summary request")
    docs = [
        {
            "content": "Bristol University opens at 9am. The library closes at 10pm.",
            "metadata": {"title": "Library Hours", "url": "http://bristol.ac.uk/library"},
            "score": 0.9,
            "date": "2023-10-01"
        },
        {
            "content": "Students can borrow up to 20 books.",
            "metadata": {"title": "Borrowing Rules", "url": "http://bristol.ac.uk/library/borrow"},
            "score": 0.85,
            "date": "2023-10-02"
        }
    ]
    query = "What are the library hours and borrowing limits?"
    
    try:
        response = requests.post(
            summarize_url,
            json={"query": query, "docs": docs},
            stream=True
        )
        
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            full_response = ""
            print("Streaming response:")
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    full_response += decoded_line
                    # print(decoded_line) # Optional: print each chunk
            print(f"\nFull response length: {len(full_response)}")
            print(f"Preview: {full_response[:200]}...")
            
            if "__SOURCES__" in full_response:
                print("SUCCESS: Sources found in response.")
            else:
                print("WARNING: No sources found in response.")
        else:
            print(f"FAILED: {response.text}")
            
    except Exception as e:
        print(f"Request failed: {e}")

    # Test empty docs
    print("\n[Test] Empty docs request")
    try:
        response = requests.post(
            summarize_url,
            json={"query": "test", "docs": []},
            stream=True
        )
        print(f"Status Code: {response.status_code}")
        content = response.text
        print(f"Content: {content}")
        if "未找到相关通知" in content or "No relevant" in content:
            print("SUCCESS: Handled empty docs correctly.")
        else:
            print("WARNING: Unexpected response for empty docs.")
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    # Check if server is already running
    server_process = None
    try:
        requests.get("http://localhost:8000/docs")
        print("Server appears to be already running.")
    except requests.exceptions.ConnectionError:
        print("Server not running, starting it...")
        server_process = start_server()
        if not wait_for_server("http://localhost:8000/docs"):
            print("Timeout waiting for server to start.")
            if server_process:
                server_process.kill()
            sys.exit(1)
        print("Server started.")

    try:
        test_summarize_endpoint()
    finally:
        if server_process:
            print("Stopping server...")
            server_process.kill()
            # Also try to terminate properly
            # server_process.terminate() 
