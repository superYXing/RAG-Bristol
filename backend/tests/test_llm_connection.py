"""
test_llm_connection.py - LLM API Connection Test

This script tests the connection to the LLM service (local Ollama
or cloud API) configured in the .env file:
- Validates OPENAI_API_KEY and LLM_BASE_URL environment variables
- Sends a simple "hello" request to verify connectivity
- Reports API response status and content

Run with:
    python test_llm_connection.py
"""

import os
import sys
from dotenv import load_dotenv

# 添加项目根目录到 sys.path，以便导入模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from langchain_openai import ChatOpenAI

def test_llm_connection():
    # 加载 .env 文件
    load_dotenv()
    
    # 获取环境变量
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("LLM_BASE_URL")
    
    if not api_key:
        print("错误: 未找到 OPENAI_API_KEY 环境变量。请检查 .env 文件。")
        return

    print(f"正在连接到: {base_url}")
    print(f"使用 Key: {api_key[:8]}******")

    try:
        # 初始化 ChatOpenAI
        llm = ChatOpenAI(
            openai_api_base=base_url,
            openai_api_key=api_key,
            model="qwen2.5:7b", 
            temperature=0.7
        )

        print("\n正在发送请求: 'hello'...")
        res = llm.invoke("hello")
        
        print("-" * 20)
        print("API 响应内容:")
        print(res.content)
        print("-" * 20)
        print("测试通过！成功连接到大模型。")
        
    except Exception as e:
        print(f"\n测试失败: {e}")
        print("请检查您的 API Key 和 Base URL 配置。")

if __name__ == "__main__":
    test_llm_connection()
